"""Opt-in real disk admission for creation, copies, retained data, and restore."""
import argparse
import asyncio
import hashlib
import json
import runpy
import tempfile
from pathlib import Path
from uuid import uuid4

from autoflow.application.android.backups import AndroidBackupService
from autoflow.application.android.management import AndroidManagement
from autoflow.domain.android.management_models import public_device_revision
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.filesystem.android_paths import android_runtime_root
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android.mac_runtime import MacAndroidRuntime, docker
from autoflow.providers.android.management import verify

ROOT = Path(__file__).resolve().parents[4]
H = runpy.run_path(str(ROOT / 'docs/qa/android-management/scripts/restore-interruption-smoke.py'))
BASE = '/api/v1/android/management'


async def terminal(repository, identifier, operation_id, state='succeeded'):
    async with asyncio.timeout(180):
        while True:
            row = repository.get(identifier)
            op = row.get('operation') or {}
            if op.get('id') == operation_id and op.get('state') in {'succeeded', 'failed', 'needs_verification', 'interrupted'}:
                assert op['state'] == state, row
                return row
            await asyncio.sleep(.2)


async def exercise(output):
    workspace = Path(tempfile.mkdtemp(prefix='autoflow-create-disk-'))
    report = {'workspace': str(workspace), 'status': 'started', 'checks': []}
    output.write_text(json.dumps(report))
    process, client = await H['start_server'](workspace)
    paths = AppPaths.from_data_dir(workspace)
    sessions = create_session_factory(paths.database)
    repository = SqlAlchemyDeviceRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    runtime = MacAndroidRuntime(android_runtime_root(), paths.workspace)
    expect = H['expect']

    async def operation(identifier, action, *, confirmed=False, delete_data=False, state='succeeded'):
        body = {'requestId': str(uuid4()), 'action': action, 'deleteData': delete_data}
        if confirmed:
            body['allowUnknownDiskEstimate'] = True
        accepted = expect(await client.post(f'/api/v1/android/devices/{identifier}/operations', json=body), 202)
        return await terminal(repository, identifier, accepted['operation']['id'], state)

    async def batch(body, state):
        accepted = expect(await client.post('/api/v1/android/batches', json=body), 202)
        return await wait_batch(accepted['id'], state)

    async def wait_batch(identifier, state):
        async with asyncio.timeout(180):
            while True:
                page = expect(await client.get('/api/v1/android/batches'), 200)
                row = next(item for item in page if item['id'] == identifier)
                if row['state'] in {'succeeded', 'failed', 'partially_failed', 'cancelled'}:
                    assert row['state'] == state, row
                    return row
                await asyncio.sleep(.2)

    try:
        image = json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]['Id']
        report['imageId'] = image
        expect(await client.post(BASE + '/images', json={'id': image, 'name': 'Disk admission QA', 'reference': 'redroid/redroid:13.0.0_64only-latest'}), 201)
        config = {'deviceId': str(uuid4()), 'name': 'Unconfirmed QA', 'imageId': image, 'width': 720, 'height': 1280, 'dpi': 320, 'cpu': 1, 'memoryMb': 1024, 'start': False}
        accepted = expect(await client.post('/api/v1/android/devices', json=config), 202)
        denied = await terminal(repository, config['deviceId'], accepted['operation']['id'], 'failed')
        durable = expect(await client.get(BASE + '/operations/by-request/' + config['deviceId']), 200)
        assert durable['resultCode'] == 'ANDROID_DISK_ESTIMATE_UNKNOWN', durable
        containers, volumes = await verify(denied, runtime.workspace_id)
        assert not containers and not volumes
        replay = expect(await client.post('/api/v1/android/devices', json={**config, 'allowUnknownDiskEstimate': False}), 202)
        assert replay['operation']['id'] == accepted['operation']['id']
        expect(await client.post('/api/v1/android/devices', json={**config, 'allowUnknownDiskEstimate': True}), 409)
        report['checks'].append('unconfirmed create failed; zero containers/volumes; false replay unchanged; true conflict')

        source_config = {**config, 'deviceId': str(uuid4()), 'name': 'Confirmed disk QA', 'start': True, 'allowUnknownDiskEstimate': True}
        accepted = expect(await client.post('/api/v1/android/devices', json=source_config), 202)
        source = await terminal(repository, source_config['deviceId'], accepted['operation']['id'])
        source_id = source['deviceId']
        probe = '/data/local/tmp/autoflow-create-disk-probe'
        value = 'owned-disk-admission-' + source_id
        await docker('exec', source['containerId'], 'sh', '-c', 'printf %s "$1" > "$2"', 'qa', value, probe)
        source = await operation(source_id, 'delete')
        retained_volume = source['volumeId']
        assert source['dataRetained']
        denied = await operation(source_id, 'restore', state='failed')
        containers, volumes = await verify(denied, runtime.workspace_id)
        assert not containers and len(volumes) == 1 and denied['volumeId'] == retained_volume
        await operation(source_id, 'recover')
        source = await operation(source_id, 'restore', confirmed=True)
        assert source['volumeId'] == retained_volume
        assert (await docker('exec', source['containerId'], 'cat', probe)).decode() == value
        report['checks'].append('retained restore did not inherit creation confirmation; explicit current confirmation preserves same volume/probe')
        source = await operation(source_id, 'stop')
        backup = expect(await client.post(BASE + '/backups', json={'requestId': str(uuid4()), 'deviceId': source_id, 'expectedRevision': public_device_revision(source['generation'])}), 201)
        stored = resources.get('backup', backup['id'])
        backup_dir = Path(stored['path'])
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in backup_dir.iterdir()}
        refused_restore_id = str(uuid4())
        refused_restore = expect(await client.post(BASE + f"/backups/{backup['id']}/restore", json={'requestId': refused_restore_id, 'newName': 'Unconfirmed restore'}), 409)
        assert refused_restore['error']['code'] == 'ANDROID_DISK_ESTIMATE_UNKNOWN', refused_restore
        refused_record = expect(await client.get(BASE + '/operations/by-request/' + refused_restore_id), 200)
        assert refused_record['state'] == 'failed' and refused_record['resultCode'] == 'ANDROID_DISK_ESTIMATE_UNKNOWN'
        refused_target = repository.get(refused_record['targetId'])
        containers, volumes = await verify(refused_target, runtime.workspace_id)
        assert not containers and not volumes
        restored = expect(await client.post(BASE + f"/backups/{backup['id']}/restore", json={'requestId': str(uuid4()), 'newName': 'Confirmed restore', 'allowUnknownDiskEstimate': True}), 202)
        target = await operation(restored['deviceId'], 'start')
        assert target['deviceId'] != source_id and target['volumeId'] != retained_volume
        assert (await docker('exec', target['containerId'], 'cat', probe)).decode() == value
        assert hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in backup_dir.iterdir()}
        report['checks'].append('backup restore requires current confirmation; new device/volume probe matches; source archive hashes unchanged')

        profile_id = str(uuid4())
        profile = expect(await client.put('/api/v1/android/profiles/' + profile_id, json={'id': profile_id, 'revision': 0, 'name': 'Disk QA template', 'imageId': image, 'cpu': 1, 'memoryMb': 1024}), 200)
        body = {'batchId': str(uuid4()), 'name': 'Unconfirmed batch', 'profileId': profile_id, 'profileRevision': profile['revision'], 'quantity': 1, 'start': False}
        denied_batch = await batch(body, 'failed')
        denied_row = repository.get(denied_batch['items'][0]['deviceId'])
        containers, volumes = await verify(denied_row, runtime.workspace_id)
        assert not containers and not volumes
        expect(await client.post('/api/v1/android/batches/' + denied_batch['id'] + '/actions', json={'action': 'retry'}), 200)
        retried_denied = await wait_batch(denied_batch['id'], 'failed')
        containers, volumes = await verify(repository.get(retried_denied['items'][0]['deviceId']), runtime.workspace_id)
        assert not containers and not volumes
        report['checks'].append('retry of unconfirmed failed batch remains failed with no containers/volumes')
        confirmed_batch = await batch({**body, 'batchId': str(uuid4()), 'name': 'Confirmed batch', 'allowUnknownDiskEstimate': True}, 'succeeded')
        batch_source = repository.get(confirmed_batch['items'][0]['deviceId'])
        denied_copy = await batch({**body, 'batchId': str(uuid4()), 'name': 'Unconfirmed snapshot copy', 'sourceDeviceId': batch_source['deviceId']}, 'failed')
        containers, volumes = await verify(repository.get(denied_copy['items'][0]['deviceId']), runtime.workspace_id)
        assert not containers and not volumes
        copy_batch = await batch({**body, 'batchId': str(uuid4()), 'name': 'Confirmed snapshot copy', 'sourceDeviceId': batch_source['deviceId'], 'allowUnknownDiskEstimate': True}, 'succeeded')
        copied = repository.get(copy_batch['items'][0]['deviceId'])
        assert copied['volumeId'] != batch_source['volumeId'] and copied['androidStatus'] == 'stopped'
        report['checks'].append('batch default refuses with zero runtime objects; confirmed template and source snapshot create distinct stopped instances')
        report['batches'] = [denied_batch, retried_denied, confirmed_batch, denied_copy, copy_batch]
        source = await operation(source_id, 'start')
        assert (await docker('exec', source['containerId'], 'cat', probe)).decode() == value
        report['checks'].append('source probe preserved after backup restore and configuration copies')
        report['sourceId'], report['restoredId'] = source_id, target['deviceId']
        report['status'] = 'passed'
    except BaseException as error:
        report['status'], report['errorType'] = 'failed', type(error).__name__
        raise
    finally:
        await H['stop_server'](process, client)
        try:
            cleaned = []
            for row in repository.list():
                assert row['workspaceId'] == runtime.workspace_id
                manager = AndroidManagement(repository, runtime)
                if not row.get('deleted'):
                    if row['control'] == 'recovery_required':
                        manager.operate(row['deviceId'], {'requestId': str(uuid4()), 'action': 'recover', 'deleteData': False})
                        await manager.task
                    manager.operate(row['deviceId'], {'requestId': str(uuid4()), 'action': 'delete', 'deleteData': True})
                    await manager.task
                containers, volumes = await verify(repository.get(row['deviceId']), runtime.workspace_id)
                assert not containers and not volumes
                cleaned.append(row['deviceId'])
            backups = AndroidBackupService(resources, paths.workspace)
            for record in resources.list('backup'):
                assert record['workspaceId'] == str(paths.workspace.resolve())
                backups.delete(record['id'])
            report['cleanup'] = {'deviceIds': cleaned, 'containersAndVolumes': 0, 'backups': len(resources.list('backup'))}
        except BaseException as cleanup_error:
            report['status'], report['cleanupErrorType'] = 'cleanup_failed', type(cleanup_error).__name__
            raise
        finally:
            sessions.dispose()
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-device-mutation', action='store_true', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(exercise(args.output))
