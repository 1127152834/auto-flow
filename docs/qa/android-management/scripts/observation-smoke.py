"""Opt-in real TCP/API and ReDroid observation measurements; counters never replace IO."""
import argparse
import asyncio
import json
import platform
import runpy
import secrets
import socket
import statistics
import tempfile
import time
from collections import Counter
from contextvars import ContextVar
from itertools import pairwise
from pathlib import Path
from uuid import uuid4

import httpx
import uvicorn
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.providers.android.mac_runtime import docker

ROOT = Path(__file__).resolve().parents[4]
HELPERS = runpy.run_path(str(ROOT / 'docs/qa/android-management/scripts/restore-interruption-smoke.py'))


def intervals(events, identifiers):
    result = {}
    for identifier in identifiers:
        rows = [row for row in events if row['deviceId'] == identifier and row['task'] == 'android-observations']
        starts = [row['start'] for row in rows]
        result[identifier] = {'count': len(rows), 'startIntervalsSeconds': [round(b - a, 4) for a, b in pairwise(starts)], 'durationsSeconds': [round(row['end'] - row['start'], 4) for row in rows]}
    return result


async def exercise(output):
    workspace = Path(tempfile.mkdtemp(prefix='autoflow-observation-real-'))
    token = secrets.token_hex(32)
    app = create_app(Settings(data_dir=str(workspace), instance_id=str(uuid4()), instance_token=token, host_token=secrets.token_hex(32)))
    service = app.state.android_service
    observations = app.state.android_observations
    runtime = service.runtime
    original_inspect = runtime.inspect
    route = ContextVar('qa_route', default=None)
    probes = []
    devices = []
    report = {'status': 'started', 'workspace': str(workspace), 'platform': platform.platform(), 'machine': platform.machine(), 'measurements': [], 'cleanup': []}

    @app.middleware('http')
    async def record_route(request, call_next):
        reset = route.set(request.url.path)
        try:
            return await call_next(request)
        finally:
            route.reset(reset)

    async def counted_inspect(device):
        task = asyncio.current_task()
        entry = {'deviceId': device['deviceId'], 'task': task.get_name() if task else None, 'route': route.get(), 'start': time.perf_counter()}
        probes.append(entry)
        try:
            return await original_inspect(device)
        finally:
            entry['end'] = time.perf_counter()

    runtime.inspect = counted_inspect
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    sock.listen(socket.SOMAXCONN)
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning', timeout_graceful_shutdown=1))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    client = httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', headers={'x-autoflow-token': token}, timeout=180, trust_env=False)
    expect = HELPERS['expect']
    try:
        async with asyncio.timeout(45):
            while not server.started:
                assert not serving.done(), 'server exited before readiness'
                await asyncio.sleep(.1)
        image = json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]['Id']
        report['imageId'] = image
        expect(await client.post('/api/v1/android/management/images', json={'id': image, 'name': 'Observation cached base', 'reference': 'redroid/redroid:13.0.0_64only-latest'}), 201)
        for scale in (1, 5):
            while len(devices) < scale:
                identifier = str(uuid4())
                devices.append(identifier)
                result = expect(await client.post('/api/v1/android/devices', json={'deviceId': identifier, 'name': f'QA observation {len(devices)}', 'imageId': image, 'width': 720, 'height': 1280, 'dpi': 320, 'cpu': 1, 'memoryMb': 1024, 'start': True}), 202)
                row = await HELPERS['wait_device'](service.repository, identifier, result['operation']['id'])
                assert row['androidStatus'] == 'ready', row['androidStatus']
            async with asyncio.timeout(35):
                while not all((item := observations.get(identifier)) and item.runtime_state == 'ready' and not item.stale for identifier in devices):
                    await asyncio.sleep(.25)
            start = time.perf_counter()
            latencies = []
            for _ in range(20):
                before = time.perf_counter()
                page = expect(await client.get('/api/v1/android/management/devices?limit=50'), 200)
                latencies.append((time.perf_counter() - before) * 1000)
                assert page['total'] == scale
                assert all(item['runtimeState'] == 'ready' and not item['stale'] for item in page['items'])
                await asyncio.sleep(.25)
            last_client_read = time.perf_counter()
            await asyncio.sleep(max(0, 18 - (time.perf_counter() - start)))
            end = time.perf_counter()
            window = [row for row in probes if start <= row['start'] < end and 'end' in row]
            inline = [row for row in window if row['route'] == '/api/v1/android/management/devices']
            background_after_reads = [row for row in window if row['task'] == 'android-observations' and row['start'] > last_client_read]
            assert not inline, inline
            assert background_after_reads
            cadence = intervals(window, devices)
            assert all(row['count'] >= 2 for row in cadence.values()), cadence
            for row in cadence.values():
                assert all(gap >= 2.9 for gap in row['startIntervalsSeconds']), row
            rows = [service.repository.get(identifier) for identifier in devices]
            memory = (await docker('stats', '--no-stream', '--format', '{{json .}}', *(row['containerId'] for row in rows), timeout=30)).decode().splitlines()
            values = sorted(latencies)
            report['measurements'].append({'scale': scale, 'windowSeconds': round(end - start, 4), 'configuration': {'memoryMbEach': 1024, 'cpuEach': 1}, 'apiSamples': len(values), 'apiMinMs': round(values[0], 3), 'apiMedianMs': round(statistics.median(values), 3), 'apiP95Ms': round(values[18], 3), 'apiMaxMs': round(values[-1], 3), 'inlineInspectCount': len(inline), 'observerCallsAfterClientReadsStop': len(background_after_reads), 'observerCadence': cadence, 'allProbeSources': dict(Counter(row['task'] for row in window)), 'dockerMemory': [json.loads(line) for line in memory]})
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps({'scale': scale, 'status': 'measured', 'observerCounts': {identifier: row['count'] for identifier, row in cadence.items()}, 'inlineInspectCount': 0}), flush=True)
        preview_start = time.perf_counter()
        previews = await asyncio.gather(*(client.get(f'/api/v1/android/devices/{identifier}/preview') for identifier in devices[:2]))
        assert all(response.status_code == 200 and response.content.startswith(b'\x89PNG\r\n\x1a\n') for response in previews)
        report['twoRealPreviews'] = {'bytes': [len(response.content) for response in previews], 'elapsedSeconds': round(time.perf_counter() - preview_start, 4), 'note': 'Two direct real HTTP requests; frontend concurrency ceiling is separately tested.'}
        for identifier in devices:
            await HELPERS['operate'](client, service.repository, identifier, 'stop')
        async with asyncio.timeout(35):
            while not all((item := observations.get(identifier)) and item.runtime_state == 'stopped' for identifier in devices):
                await asyncio.sleep(.25)
        start = time.perf_counter()
        await asyncio.sleep(45)
        end = time.perf_counter()
        stopped = intervals([row for row in probes if start <= row['start'] < end and 'end' in row], devices)
        assert all(row['count'] >= 2 and all(gap >= 14.9 for gap in row['startIntervalsSeconds']) for row in stopped.values()), stopped
        report['stoppedCadence'] = {'windowSeconds': round(end - start, 4), 'devices': stopped}
        report['status'] = 'passed'
    finally:
        for identifier in devices:
            try:
                row = service.repository.get(identifier)
                assert row['workspaceId'] == runtime.workspace_id
                await HELPERS['operate'](client, service.repository, identifier, 'delete')
                observed = await runtime.verify_deleted(service.repository.get(identifier))
                assert observed['androidStatus'] == 'missing'
                report['cleanup'].append({'deviceId': identifier, 'state': 'missing'})
            except Exception as error:  # noqa: BLE001 - clean every owned fixture before surfacing failures.
                report['cleanup'].append({'deviceId': identifier, 'error': str(error)[:400]})
                report['status'] = 'cleanup_failed'
        await client.aclose()
        server.should_exit = True
        await serving
        sock.close()
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    assert report['status'] == 'passed', report['status']
    print(json.dumps({'status': report['status'], 'cleaned': len(report['cleanup']), 'workspace': str(workspace)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-device-mutation', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_device_mutation:
        parser.error('--allow-device-mutation is required for owned real test devices')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(exercise(args.output))
