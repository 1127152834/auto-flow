import asyncio
import json
import runpy
import tempfile
from pathlib import Path
from uuid import uuid4

from autoflow.bootstrap.android import android_service
from autoflow.domain.android.management_models import public_device_revision
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android.mac_runtime import docker

root = Path('/Users/zhangtiancheng/.codex/worktrees/android-management-complete/autoflow')
folder = root / 'docs/qa/android-management/2026-09-24-bulk-actions'
folder.mkdir(exist_ok=True)
helpers = runpy.run_path(str(root / 'docs/qa/android-management/scripts/restore-interruption-smoke.py'))

async def main():
    data_dir = Path(tempfile.mkdtemp(prefix='autoflow-bulk-final-real-'))
    paths = AppPaths.from_data_dir(data_dir)
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    service = android_service(sessions, paths.workspace)
    process = client = None
    device_id = str(uuid4())
    created = False
    report = {'dataDir': str(data_dir), 'deviceId': device_id, 'status': 'started'}
    try:
        process, client = await helpers['start_server'](data_dir)
        image_id = json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]['Id']
        helpers['expect'](await client.post('/api/v1/android/management/images', json={'id': image_id, 'name': 'QA fixed cached base', 'reference': 'redroid/redroid:13.0.0_64only-latest'}), 201)
        creation = helpers['expect'](await client.post('/api/v1/android/devices', json={'deviceId': device_id, 'name': 'QA 批次取消与重启持久性', 'imageId': image_id, 'width': 720, 'height': 1280, 'dpi': 320, 'cpu': 1, 'memoryMb': 8192, 'start': False}), 202)
        created = True
        row = await helpers['wait_device'](service.repository, device_id, creation['operation']['id'])
        assert row['androidStatus'] == 'stopped'
        request = {'requestId': str(uuid4()), 'action': 'start', 'items': [{'deviceId': device_id, 'expectedRevision': public_device_revision(row['generation'])}]}
        batch = helpers['expect'](await client.post('/api/v1/android/management/bulk-operations', json=request), 202)
        batch_url = '/api/v1/android/management/bulk-operations/' + batch['id']
        async with asyncio.timeout(90):
            while True:
                batch = helpers['expect'](await client.get(batch_url), 200)
                if batch['items'][0]['state'] == 'waiting_capacity':
                    break
                assert batch['items'][0]['state'] in {'queued', 'waiting_device'}, batch
                await asyncio.sleep(.25)
        report['waiting'] = batch
        action = {'requestId': str(uuid4()), 'action': 'cancelPending'}
        cancelled = helpers['expect'](await client.post(batch_url + '/actions', json=action), 200)
        assert cancelled['state'] == 'cancelled'
        report['cancelled'] = cancelled
        for _ in range(10):
            await asyncio.sleep(.25)
            assert helpers['expect'](await client.get(batch_url), 200)['state'] == 'cancelled'
        await helpers['stop_server'](process, client)
        process = client = None
        process, client = await helpers['start_server'](data_dir)
        replay = helpers['expect'](await client.post(batch_url + '/actions', json=action), 200)
        assert replay == cancelled
        observed = await service.runtime.inspect(service.repository.get(device_id))
        assert observed['androidStatus'] == 'stopped'
        report.update(afterRestart=replay, deviceState=observed['androidStatus'], status='passed')
    finally:
        if created and client is not None:
            await helpers['operate'](client, service.repository, device_id, 'delete')
            observed = await service.runtime.verify_deleted(service.repository.get(device_id))
            assert observed['androidStatus'] == 'missing'
            report['cleanup'] = {'state': observed['androidStatus'], 'passed': True}
        if process is not None:
            await helpers['stop_server'](process, client)
        sessions.dispose()
        (folder / 'real-cancel-restart.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'deviceId': device_id, 'state': replay['state'], 'cleanup': report['cleanup']}))

asyncio.run(main())
