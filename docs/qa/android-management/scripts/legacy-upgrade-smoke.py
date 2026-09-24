"""Opt-in real old-version SQLite and temporary device forward upgrade."""

import argparse
import asyncio
import json
import os
import runpy
import secrets
import signal
import sqlite3
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.filesystem.android_paths import android_runtime_root
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android.mac_runtime import MacAndroidRuntime, docker, run
from autoflow.providers.android.management import verify

ROOT = Path(__file__).resolve().parents[4]
H = runpy.run_path(str(ROOT / 'docs/qa/android-management/scripts/restore-interruption-smoke.py'))
BASE = '/api/v1/android'


async def old_server(workspace, checkout):
    token = secrets.token_hex(32)
    env = {**os.environ, 'PYTHONPATH': str(checkout / 'apps/backend/src'), 'AUTOFLOW_INSTANCE_TOKEN': token, 'AUTOFLOW_HOST_TOKEN': secrets.token_hex(32)}
    with (workspace / 'old-sidecar.log').open('ab') as log:
        process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'autoflow', '--instance-id', str(uuid4()), '--data-dir', str(workspace), '--port', '0', cwd=checkout / 'apps/backend', env=env, stdout=asyncio.subprocess.PIPE, stderr=log, start_new_session=True)
    client = None
    try:
        line = await asyncio.wait_for(process.stdout.readline(), 45)
        assert line.startswith(b'AUTOFLOW_READY '), line
        port = json.loads(line.removeprefix(b'AUTOFLOW_READY '))['port']
        client = httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', headers={'x-autoflow-token': token}, timeout=180, trust_env=False)
        for _ in range(100):
            try:
                if (await client.get(BASE + '/environment')).status_code == 200:
                    return process, client
            except httpx.ConnectError:
                pass
            await asyncio.sleep(.1)
        raise TimeoutError('Old sidecar readiness')
    except BaseException:
        if client:
            await client.aclose()
        if process.returncode is None:
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()
        raise


def revision(database):
    with sqlite3.connect(database) as connection:
        return connection.execute('SELECT version_num FROM alembic_version').fetchone()[0]


async def exercise(output, checkout):
    old_commit = (await run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], 5)).decode().strip()
    assert old_commit == 'a92f0688f206d4339ff4468c1871f3ccdd6816dc'
    workspace = Path(tempfile.mkdtemp(prefix='autoflow-legacy-upgrade-'))
    paths = AppPaths.from_data_dir(workspace)
    report = {'status': 'started', 'workspace': str(workspace), 'oldCommit': old_commit}
    output.write_text(json.dumps(report))
    process = client = sessions = device = None
    expect = H['expect']
    runtime = MacAndroidRuntime(android_runtime_root(), paths.workspace)
    try:
        process, client = await old_server(workspace, checkout)
        report['oldMigrationHead'] = revision(paths.database)
        assert report['oldMigrationHead'] == '0019_recording_commands'
        sessions = create_session_factory(paths.database)
        repository = SqlAlchemyDeviceRepository(sessions)
        image = json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]['Id']
        profile_id = str(uuid4())
        profile = expect(await client.put(BASE + '/profiles/' + profile_id, json={'id': profile_id, 'revision': 0, 'name': 'Legacy upgrade QA', 'imageId': image, 'cpu': 1, 'memoryMb': 1024}), 200)
        body = {'batchId': str(uuid4()), 'name': 'Legacy temporary QA', 'profileId': profile_id, 'profileRevision': profile['revision'], 'quantity': 1, 'instanceType': 'temporary', 'start': True, 'width': 720, 'height': 1280, 'locale': 'zh-CN', 'timezone': 'Asia/Shanghai'}
        batch = expect(await client.post(BASE + '/batches', json=body), 202)
        device_id = batch['items'][0]['deviceId']
        async with asyncio.timeout(180):
            while True:
                batch = next(item for item in expect(await client.get(BASE + '/batches'), 200) if item['id'] == body['batchId'])
                if batch['state'] == 'succeeded':
                    break
                assert batch['state'] not in {'failed', 'cancelled'}, batch
                await asyncio.sleep(.5)
        device = repository.get(device_id)
        assert device['instanceType'] == 'temporary', device
        snapshot_keys = ('deviceId', 'containerId', 'volumeId', 'imageId', 'instanceType', 'creationConfig')
        snapshot = {key: device.get(key) for key in snapshot_keys}
        probe, value = '/data/local/tmp/autoflow-legacy-probe', 'legacy-' + device_id
        await docker('exec', device['containerId'], 'sh', '-c', 'printf %s "$1" > "$2"', 'qa', value, probe)
        device = await H['operate'](client, repository, device_id, 'stop')
        report.update(imageId=image, deviceBefore=snapshot, oldBatch=batch)
        await H['stop_server'](process, client)
        process = client = None
        process, client = await H['start_server'](workspace)
        report['newMigrationHead'] = revision(paths.database)
        assert report['newMigrationHead'] == 'am01_management_operations'
        upgraded = repository.get(device_id)
        assert {key: upgraded.get(key) for key in snapshot_keys} == snapshot
        profiles = expect(await client.get(BASE + '/profiles'), 200)
        upgraded_profile = next(item for item in profiles if item['id'] == profile_id)
        assert upgraded_profile['revision'] == profile['revision'] and upgraded_profile['imageId'] == image
        device = await H['operate'](client, repository, device_id, 'start')
        assert (await docker('exec', device['containerId'], 'cat', probe)).decode() == value
        replay = await client.post(BASE + '/batches', json=body)
        report.update(deviceAfter={key: device.get(key) for key in snapshot_keys}, sourceProbePreserved=True, replayStatus=replay.status_code, replayBody=replay.json())
        expect(replay, 202)
        assert replay.json()['items'] == batch['items']
        refused = expect(await client.post(BASE + '/batches', json={**body, 'batchId': str(uuid4())}), 409)
        assert refused['error']['code'] == 'ANDROID_TEMPORARY_DISABLED', refused
        report.update(newTemporaryRejected=True, status='passed')
    except BaseException as error:
        report.update(status='failed', errorType=type(error).__name__, error=str(error)[:500])
        raise
    finally:
        try:
            if sessions:
                repository = SqlAlchemyDeviceRepository(sessions)
                for owned in repository.list():
                    device = await H['operate'](client, repository, owned['deviceId'], 'delete')
                    containers, volumes = await verify(device, runtime.workspace_id)
                    assert not containers and not volumes
                report['cleanupContainersAndVolumes'] = 0
        finally:
            if process and client:
                await H['stop_server'](process, client)
            if sessions:
                sessions.dispose()
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-device-mutation', action='store_true', required=True)
    parser.add_argument('--old-checkout', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(exercise(args.output, args.old_checkout))
