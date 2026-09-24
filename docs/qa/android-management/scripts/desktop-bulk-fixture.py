"""Create/clean two owned stopped devices for real desktop bulk acceptance."""
import argparse
import asyncio
import json
import runpy
import tempfile
from pathlib import Path
from uuid import uuid4

from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.filesystem.android_paths import android_runtime_root
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android.mac_runtime import MacAndroidRuntime, docker
from autoflow.providers.android.management import verify

ROOT = Path(__file__).resolve().parents[4]
HELPERS = runpy.run_path(str(ROOT / 'docs/qa/android-management/scripts/restore-interruption-smoke.py'))


async def exercise(action, output):
    if action == 'seed':
        report = {'kind': 'autoflow-owned-desktop-bulk-v1', 'workspace': tempfile.mkdtemp(prefix='autoflow-desktop-bulk-'), 'devices': [], 'status': 'seeding'}
        output.write_text(json.dumps(report, indent=2))
    else:
        report = json.loads(output.read_text())
        assert report['kind'] == 'autoflow-owned-desktop-bulk-v1'
    workspace = Path(report['workspace'])
    paths = AppPaths.from_data_dir(workspace)
    process, client = await HELPERS['start_server'](workspace)
    sessions = create_session_factory(paths.database)
    repository = SqlAlchemyDeviceRepository(sessions)
    runtime = MacAndroidRuntime(android_runtime_root(), paths.workspace)
    expect = HELPERS['expect']
    try:
        if action == 'seed':
            image = json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]['Id']
            report['imageId'] = image
            expect(await client.post('/api/v1/android/management/images', json={'id': image, 'name': 'Owned desktop acceptance base', 'reference': 'redroid/redroid:13.0.0_64only-latest'}), 201)
            for index in range(2):
                identifier = str(uuid4())
                report['devices'].append(identifier)
                output.write_text(json.dumps(report, indent=2))
                created = expect(await client.post('/api/v1/android/devices', json={'deviceId': identifier, 'name': f'QA批量验收{index + 1}', 'imageId': image, 'width': 720, 'height': 1280, 'dpi': 320, 'cpu': 1, 'memoryMb': 1024, 'allowUnknownDiskEstimate': True, 'start': False}), 202)
                row = await HELPERS['wait_device'](repository, identifier, created['operation']['id'])
                assert row['workspaceId'] == runtime.workspace_id
                assert (await runtime.inspect(row))['androidStatus'] == 'stopped'
            report['status'] = 'seeded_stopped'
        else:
            results = []
            for identifier in report['devices']:
                row = repository.get(identifier)
                assert row['workspaceId'] == runtime.workspace_id
                if not row.get('deleted'):
                    if row.get('control') == 'recovery_required':
                        await HELPERS['operate'](client, repository, identifier, 'recover')
                    await HELPERS['operate'](client, repository, identifier, 'delete')
                containers, volumes = await verify(repository.get(identifier), runtime.workspace_id)
                assert not containers and not volumes, (containers, volumes)
                results.append({'deviceId': identifier, 'runtimeState': 'missing'})
            report['cleanup'] = results
            report['status'] = 'cleaned'
    finally:
        await HELPERS['stop_server'](process, client)
        sessions.dispose()
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['seed', 'cleanup'])
    parser.add_argument('--allow-device-mutation', action='store_true', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(exercise(args.action, args.output))
