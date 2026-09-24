"""Opt-in real pull and sidecar death after durable receipt, before HTTP completion."""
import argparse
import asyncio
import json
import os
import runpy
import secrets
import sys
import tempfile
from pathlib import Path
from threading import Event
from uuid import uuid4

import httpx
from autoflow.providers.android.mac_runtime import docker

ROOT = Path(__file__).resolve().parents[4]
HELPERS = runpy.run_path(str(ROOT / 'docs/qa/android-management/scripts/restore-interruption-smoke.py'))


def worker():
    from autoflow.__main__ import main
    from autoflow.application.android.images import AndroidImageService
    from autoflow.providers.android import mac_runtime

    original_save = AndroidImageService._save_registration
    original_docker = mac_runtime.docker
    marker = Path(os.environ['AUTOFLOW_QA_MARKER'])
    calls = Path(os.environ['AUTOFLOW_QA_PULL_CALLS'])

    def counted_docker(*args, **kwargs):
        if args[:1] == ('pull',):
            with calls.open('a') as stream:
                stream.write(args[1] + '\n')
        return original_docker(*args, **kwargs)

    def save_then_pause(self, image, receipt):
        original_save(self, image, receipt)
        if receipt and receipt['requestId'] == os.environ.get('AUTOFLOW_QA_PAUSE_REQUEST'):
            pending = marker.with_suffix('.pending')
            pending.write_text(json.dumps({'imageId': image['imageId'], 'requestId': receipt['requestId']}))
            pending.replace(marker)
            Event().wait(180)  # Supervisor kills this owned process at the persisted boundary.

    mac_runtime.docker = counted_docker
    AndroidImageService._save_registration = save_then_pause
    sys.argv.remove('--worker')
    main()


async def start(workspace, request_id, pause):
    token = secrets.token_hex(32)
    env = {**os.environ, 'AUTOFLOW_INSTANCE_TOKEN': token, 'AUTOFLOW_HOST_TOKEN': secrets.token_hex(32),
           'AUTOFLOW_QA_MARKER': str(workspace / 'receipt.json'), 'AUTOFLOW_QA_PULL_CALLS': str(workspace / 'pull-calls.txt'),
           'AUTOFLOW_QA_PAUSE_REQUEST': request_id if pause else ''}
    with (workspace / 'sidecar.log').open('ab') as log:
        process = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).resolve()), '--worker', '--instance-id', str(uuid4()), '--data-dir', str(workspace), '--port', '0', env=env, start_new_session=True, stdout=asyncio.subprocess.PIPE, stderr=log)
    client = None
    try:
        line = await asyncio.wait_for(process.stdout.readline(), 45)
        assert line.startswith(b'AUTOFLOW_READY '), line
        port = json.loads(line.removeprefix(b'AUTOFLOW_READY '))['port']
        client = httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', headers={'x-autoflow-token': token}, timeout=180, trust_env=False)
        async with asyncio.timeout(30):
            while True:
                try:
                    if (await client.get('/api/v1/android/management/images')).status_code == 200:
                        return process, client
                except httpx.ConnectError:
                    pass
                await asyncio.sleep(.1)
    except BaseException:
        await HELPERS['kill_owned_tree'](process)
        if client:
            await client.aclose()
        raise


async def exercise(output, leave_pending_for_desktop=False):
    workspace = Path(tempfile.mkdtemp(prefix='autoflow-image-pull-interruption-'))
    request_id = str(uuid4())
    metadata = json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]
    image = metadata['Id']
    reference = next(value for value in metadata['RepoDigests'] if value.startswith(('redroid/redroid@sha256:', 'docker.io/redroid/redroid@sha256:')))
    report = {'status': 'started', 'workspace': str(workspace), 'imageId': image, 'requestId': request_id, 'reference': reference, 'cleanup': 'not_run: owned workspace registration may remain; no image-content deletion permitted'}
    process = client = transfer = None
    expect = HELPERS['expect']
    try:
        process, client = await start(workspace, request_id, True)
        refused_id = str(uuid4())
        refused_body = {'requestId': refused_id, 'reference': reference}
        refused = expect(await client.post('/api/v1/android/management/image-pulls', json=refused_body), 409)
        assert refused['error']['code'] == 'ANDROID_DISK_ESTIMATE_UNKNOWN', refused
        refused_record = expect(await client.get(f'/api/v1/android/management/operations/by-request/{refused_id}'), 200)
        assert refused_record['state'] == 'failed' and refused_record['resultCode'] == 'ANDROID_DISK_ESTIMATE_UNKNOWN', refused_record
        assert not (workspace / 'pull-calls.txt').exists(), 'Unconfirmed preflight dispatched docker pull'
        refused_replay = expect(await client.post('/api/v1/android/management/image-pulls', json=refused_body), 202)
        assert refused_replay['state'] == 'failed' and refused_replay['operationId'] == refused_record['operationId'], refused_replay
        changed_confirmation = expect(await client.post('/api/v1/android/management/image-pulls', json={**refused_body, 'allowUnknownDiskEstimate': True}), 409)
        assert changed_confirmation['error']['code'] == 'ANDROID_OPERATION_IDEMPOTENCY_CONFLICT', changed_confirmation
        report['unconfirmedPreflight'] = {'state': refused_record['state'], 'resultCode': refused_record['resultCode'], 'actualDockerPullCalls': 0, 'replayPreserved': True, 'changedConfirmationRejected': True}
        body = {'requestId': request_id, 'reference': reference, 'allowUnknownDiskEstimate': True}
        transfer = asyncio.create_task(client.post('/api/v1/android/management/image-pulls', json=body))
        async with asyncio.timeout(150):
            while not (workspace / 'receipt.json').exists():
                if transfer.done():
                    raise AssertionError(('pull ended before receipt boundary', (await transfer).text[:400]))
                await asyncio.sleep(.01)
        receipt = json.loads((workspace / 'receipt.json').read_text())
        assert receipt == {'imageId': image, 'requestId': request_id}
        report['killedOwnedProcessGroups'] = await HELPERS['kill_owned_tree'](process)
        transport_result = (await asyncio.gather(transfer, return_exceptions=True))[0]
        assert isinstance(transport_result, httpx.TransportError), type(transport_result).__name__
        report['lostResponse'] = type(transport_result).__name__
        await client.aclose()
        process, client = await start(workspace, request_id, False)
        record = expect(await client.get(f'/api/v1/android/management/operations/by-request/{request_id}'), 200)
        assert record['state'] == 'needs_verification', record
        report['afterRestart'] = record
        history = expect(await client.get('/api/v1/android/management/operations?action=pull&state=needs_verification&limit=50'), 200)
        assert history['total'] == 1 and history['items'][0]['operationId'] == record['operationId'], history
        report['discoveredAfterRestart'] = history
        replay = expect(await client.post('/api/v1/android/management/image-pulls', json=body), 202)
        assert replay['operationId'] == record['operationId'] and replay['state'] == 'needs_verification'
        if leave_pending_for_desktop:
            assert (workspace / 'pull-calls.txt').read_text().splitlines() == [reference]
            report['actualDockerPullCalls'] = 1
            report['status'] = 'pending_desktop_verification'
            report['cleanup'] = 'Owned registration intentionally retained for desktop verification; no devices or image content created.'
            return
        verified = expect(await client.post(f"/api/v1/android/management/operations/{record['operationId']}/verify", json={'requestId': request_id}), 200)
        assert verified['state'] == 'succeeded' and verified['resultCode'] == 'IMAGE_PULL_VERIFIED', verified
        report['verified'] = verified
        history = expect(await client.get('/api/v1/android/management/operations?action=pull&state=needs_verification&limit=50'), 200)
        assert history['total'] == 0 and not history['items'], history
        report['unknownHistoryAfterVerify'] = history
        assert (workspace / 'pull-calls.txt').read_text().splitlines() == [reference]
        report['actualDockerPullCalls'] = 1
        after = json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]['Id']
        assert after == image
        report['originalTagUnchanged'] = True
        page = expect(await client.get('/api/v1/android/management/images'), 200)
        assert len(page['items']) == 1 and page['items'][0]['imageId'] == image
        registered = page['items'][0]
        removed = expect(await client.request('DELETE', f"/api/v1/android/management/images/{registered['id']}", json={'requestId': str(uuid4()), 'expectedRevision': registered['revision'], 'deleteContent': False}), 200)
        assert removed['state'] == 'unregistered'
        report['cleanup'] = 'Only owned workspace registration removed; existing image content retained; no devices created.'
        report['status'] = 'passed'
    except BaseException as error:
        report['status'] = 'failed'
        report['errorType'] = type(error).__name__
        raise
    finally:
        if process and client:
            await HELPERS['stop_server'](process, client)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if '--worker' in sys.argv:
        worker()
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument('--allow-image-pull', action='store_true')
        parser.add_argument('--output', type=Path, required=True)
        parser.add_argument('--leave-pending-for-desktop', action='store_true')
        args = parser.parse_args()
        if not args.allow_image_pull:
            parser.error('--allow-image-pull is required for the owned-workspace real pull')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(exercise(args.output, args.leave_pending_for_desktop))
