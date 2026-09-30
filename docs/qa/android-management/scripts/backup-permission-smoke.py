"""Opt-in real macOS permission denial on a newly owned backup directory."""

import argparse
import asyncio
import errno
import json
import os
import runpy
import stat
import tempfile
from pathlib import Path
from uuid import uuid4

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


async def exercise(output):
    workspace = Path(tempfile.mkdtemp(prefix='autoflow-backup-permission-'))
    report = {'workspace': str(workspace), 'status': 'started'}
    output.write_text(json.dumps(report))
    paths = AppPaths.from_data_dir(workspace)
    process = client = sessions = device = None
    backup_root = paths.workspace / 'android-backups'
    original_flags = None
    runtime = MacAndroidRuntime(android_runtime_root(), paths.workspace)
    expect = H['expect']
    try:
        process, client = await H['start_server'](workspace)
        sessions = create_session_factory(paths.database)
        repository = SqlAlchemyDeviceRepository(sessions)
        image = json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]['Id']
        expect(await client.post(BASE + '/images', json={'id': image, 'name': 'Permission QA base', 'reference': 'redroid/redroid:13.0.0_64only-latest'}), 201)
        identifier = str(uuid4())
        created = expect(await client.post('/api/v1/android/devices', json={'deviceId': identifier, 'name': 'Permission QA source', 'imageId': image, 'width': 720, 'height': 1280, 'dpi': 320, 'cpu': 1, 'memoryMb': 1024, 'allowUnknownDiskEstimate': True, 'start': True}), 202)
        device = repository.get(identifier)
        device = await H['wait_device'](repository, identifier, created['operation']['id'])
        report.update(deviceId=identifier, imageId=image, containerId=device['containerId'], volumeId=device['volumeId'])
        probe = '/data/local/tmp/autoflow-permission-probe'
        value = 'permission-qa-' + identifier
        await docker('exec', device['containerId'], 'sh', '-c', 'printf %s "$1" > "$2"', 'qa', value, probe)
        device = await H['operate'](client, repository, identifier, 'stop')
        backup_root.mkdir(mode=0o700, parents=True)
        assert backup_root.resolve().is_relative_to(workspace.resolve())
        original_flags = backup_root.stat().st_flags
        os.chflags(backup_root, original_flags | stat.UF_IMMUTABLE)
        try:
            (backup_root / 'permission-probe').mkdir()
        except OSError as error:
            assert error.errno in {errno.EPERM, errno.EACCES}, error
            report['filesystemDenialErrno'] = error.errno
        else:
            raise AssertionError('macOS did not deny directory mutation')

        request_id = str(uuid4())
        body = {'requestId': request_id, 'deviceId': identifier, 'expectedRevision': public_device_revision(device['generation'])}
        refused = expect(await client.post(BASE + '/backups', json=body), 503)
        assert refused['error']['code'] == 'ANDROID_BACKUP_RESULT_UNKNOWN', refused
        receipt = expect(await client.get(BASE + '/operations/by-request/' + request_id), 200)
        assert receipt['state'] == 'needs_verification' and receipt['resultCode'] == 'BACKUP_RESULT_UNKNOWN', receipt
        assert expect(await client.get(BASE + '/backups'), 200) == []
        assert list(backup_root.iterdir()) == []
        report.update(refusedResponse=refused, receipt=receipt, noPublishedBackup=True, noStaging=True)

        os.chflags(backup_root, original_flags)
        original_flags = None
        replay = expect(await client.post(BASE + '/backups', json=body), 409)
        assert replay['error']['code'] == 'ANDROID_BACKUP_REQUEST_REPLAYED', replay
        backup = expect(await client.post(BASE + '/backups', json={**body, 'requestId': str(uuid4())}), 201)
        assert backup['state'] == 'available' and backup['bytes'] > 0
        report.update(replayProtected=True, permissionRestoredBackup=backup)
        device = await H['operate'](client, repository, identifier, 'start')
        assert (await docker('exec', device['containerId'], 'cat', probe)).decode() == value
        report['sourceProbePreserved'] = True
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', errorType=type(error).__name__)
        raise
    finally:
        try:
            if original_flags is not None:
                os.chflags(backup_root, original_flags)
            report['permissionRestrictionRemoved'] = not bool(backup_root.exists() and backup_root.stat().st_flags & stat.UF_IMMUTABLE)
            if device is not None:
                device = await H['operate'](client, repository, device['deviceId'], 'delete')
                containers, volumes = await verify(device, runtime.workspace_id)
                assert not containers and not volumes
                from autoflow.application.android.backups import AndroidBackupService

                resources = AndroidResourceRepository(sessions)
                service = AndroidBackupService(resources, paths.workspace)
                for backup in resources.list('backup'):
                    assert backup['workspaceId'] == str(paths.workspace.resolve())
                    service.delete(backup['id'])
                report['cleanup'] = {'containersAndVolumes': 0, 'backups': len(resources.list('backup')), 'ownedDeviceId': device['deviceId']}
        except BaseException as error:
            report.update(status='cleanup_failed', cleanupErrorType=type(error).__name__)
            raise
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
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    asyncio.run(exercise(arguments.output))
