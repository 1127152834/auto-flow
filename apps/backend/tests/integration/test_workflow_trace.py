from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.workflow_runs import workflow_runs_router
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.runs import WorkflowRunStart
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifactStore
from autoflow.providers.browser.workflow_trace import TRACE_MIME, WorkflowTrace


@pytest.fixture
def trace_store(tmp_path):
    database = tmp_path / 'test.sqlite3'
    migrate_database(database)
    factory = create_session_factory(database)
    repository = SqlAlchemyWorkflowRuns(factory)
    service = WorkflowRunService(repository)
    service.start(WorkflowRunStart('trace-run', 'flow', 'doc', '追踪测试', {'nodes': []}, {}, 'profile', {}, 'run'))
    store = WorkflowArtifactStore(tmp_path, repository)
    async def save(name, content, mime):
        writer = store.writer(run_id='trace-run', node_id='__trace__', execution_id=None, purpose='diagnostic')
        path = await writer.write_bytes(name=name, content=content, mime_type=mime)
        relative = Path(path).relative_to(tmp_path).as_posix()
        return next(row.artifact_id for row in repository.list_artifacts('trace-run', cursor=0, limit=200) if row.relative_path == relative)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflow_runs_router(service, tmp_path))
    with TestClient(app) as client:
        yield service, repository, save, client
    factory.dispose()


@pytest.mark.asyncio
async def test_trace_partial_index_pagination_integrity_and_run_ownership(trace_store, tmp_path):
    service, repository, save, client = trace_store
    trace = WorkflowTrace(SimpleNamespace(tracing=SimpleNamespace(start=AsyncMock(side_effect=RuntimeError('unavailable')))), save)
    await trace.start()
    trace.MAX_EVENTS = 2
    trace._record('console', message='证据一')
    trace._record('console', message='证据二')
    trace._record('exception', message='超限')
    await trace.finish()
    await trace.finish()  # cannot duplicate an archive or index
    service.finish('trace-run', status='failed', cleanup_completed=True, error='实际网页失败')
    response = client.get('/api/workflow-runs/trace-run/trace?limit=1')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['runStatus'] == 'failed' and data['status'] == 'partial'
    assert data['total'] == 2 and data['nextCursor'] == 1
    assert data['archiveId'] is None
    assert any('启动失败' in gap for gap in data['gaps'])
    assert client.get('/api/workflow-runs/trace-run/trace?cursor=1').json()['events'][0]['message'] == '证据二'
    assert client.get('/api/workflow-runs/trace-run/trace?kind=exception').json()['total'] == 0
    assert client.get('/api/workflow-runs/trace-run/trace?projectId=other').status_code == 404
    artifacts = repository.list_artifacts('trace-run', cursor=0, limit=200)
    assert len(artifacts) == 1 and artifacts[0].purpose == 'diagnostic'
    path = tmp_path / artifacts[0].relative_path
    path.write_text('{}')
    assert client.get('/api/workflow-runs/trace-run/trace').status_code == 422
    path.unlink()
    assert client.get('/api/workflow-runs/trace-run/trace').status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('enhanced', [False, True])
async def test_real_cloak_trace_survives_browser_close(trace_store, tmp_path, monkeypatch, enhanced):
    executable = os.environ.get('AUTOFLOW_B1_CLOAK_EXECUTABLE')
    if not executable:
        pytest.skip('requires installed CloakBrowser')
    from autoflow.providers.browser.workflow_session import launch_workflow_session

    monkeypatch.setenv('CLOAKBROWSER_BINARY_PATH', executable)
    monkeypatch.setenv('CLOAKBROWSER_CACHE_DIR', str(tmp_path / 'cache'))
    service, repository, save, client = trace_store
    command = {'fingerprintSeed': 12345, 'expertArgs': [], 'locale': 'zh-CN', 'timezone': 'Asia/Shanghai', 'colorScheme': 'light', 'geoip': False, 'humanize': False, 'humanPreset': 'default', 'extensionPaths': [], 'licenseKey': None, 'browserVersion': '145.0.7632.109.2', 'releaseChannel': 'stable', 'headless': True}
    async def webpage(reader, writer):
        request = await reader.read(4096)
        body = b'<button id="b" onclick="this.textContent=\'done\';console.log(\'trace-click\');setTimeout(()=>{throw Error(\'trace-error\')},0)">click</button>'
        if enhanced:
            body += b'<script src="/actual.js"></script><script>debugger; window.inlineTraceProof = 42</script>'
            if b'GET /actual.js ' in request:
                body = b'window.externalTraceProof = "actual-source";'
        writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: ' + str(len(body)).encode() + b'\r\nConnection: close\r\n\r\n' + body)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
    async with await asyncio.start_server(webpage, '127.0.0.1', 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with launch_workflow_session(command) as browser:
            await browser.start_trace(save, enhanced=enhanced)
            page = browser.current_page()._raw
            await page.goto(f'http://127.0.0.1:{port}/', timeout=5000)
            await page.click('#b')
            await browser.trace.execution({'type': 'execution:node_complete', 'nodeId': 'click', 'executionId': 'exec-1', 'success': True}, browser)
            assert await page.inner_text('#b') == 'done'
            if enhanced:
                assert await page.evaluate('window.externalTraceProof') == 'actual-source'
                async with asyncio.timeout(4):
                    while not any(row.get('sourceId') and row.get('url', '').endswith('/actual.js') for row in browser.trace.events):
                        await asyncio.sleep(.02)
    service.finish('trace-run', status='completed', cleanup_completed=True)
    data = client.get('/api/workflow-runs/trace-run/trace').json()
    if enhanced:
        source_rows = [row for row in data['events'] if row.get('sourceId')]
        assert source_rows, data
        contents = [client.get(f"/api/workflow-runs/trace-run/artifacts/{row['sourceId']}").content for row in source_rows]
        assert any(b'window.externalTraceProof = "actual-source";' in content for content in contents)
        assert any(b'window.inlineTraceProof = 42' in content for content in contents)
    else:
        assert not any(row['kind'] == 'source' for row in data['events'])
    assert data['archiveId'], data
    assert {'execution', 'network', 'console', 'exception'} <= {event['kind'] for event in data['events']}
    assert any(event.get('message') == 'trace-click' for event in data['events'])
    shot = next(event['snapshotId'] for event in data['events'] if event.get('snapshotId'))
    assert client.get(f'/api/workflow-runs/trace-run/artifacts/{shot}').content.startswith(b'\x89PNG')
    archive = repository.get_artifact('trace-run', data['archiveId'])
    with ZipFile(tmp_path / archive.relative_path) as zipped:
        assert any(name.endswith('.trace') for name in zipped.namelist())
    assert all(row.purpose == 'diagnostic' for row in repository.list_artifacts('trace-run', cursor=0, limit=200))
    # A new service instance reads persisted data; no browser or old in-memory collector required.
    manifest = next(row for row in repository.list_artifacts('trace-run', cursor=0, limit=200) if row.mime_type == TRACE_MIME)
    assert json.loads((tmp_path / manifest.relative_path).read_bytes())['traceId'] == data['traceId']


@pytest.mark.asyncio
@pytest.mark.parametrize('stop_early', [False, True])
async def test_real_worker_flushes_trace_before_process_cleanup(tmp_path, monkeypatch, stop_early):
    executable = os.environ.get('AUTOFLOW_B1_CLOAK_EXECUTABLE')
    if not executable:
        pytest.skip('requires installed CloakBrowser')
    from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager

    monkeypatch.setenv('PYTHONPATH', str(Path(__file__).parents[2] / 'src'))
    events = []
    manager = WorkflowWorkerManager(tmp_path, on_event=events.append, termination_timeout=.5)
    config = {'fingerprintSeed': 12345, 'expertArgs': [], 'locale': 'zh-CN', 'timezone': 'Asia/Shanghai', 'colorScheme': 'light', 'geoip': False, 'humanize': False, 'humanPreset': 'default', 'extensionPaths': [], 'licenseKey': None, 'browserVersion': '145.0.7632.109.2', 'releaseChannel': 'stable', 'headless': True}
    document = {'nodes': [
        {'id': 'open', 'data': {'moduleType': 'open_page', 'config': {'url': 'data:text/html,<h1>Trace worker</h1>', 'openMode': 'current_tab'}}},
        {'id': 'next', 'data': {'moduleType': 'wait_element' if stop_early else 'get_element_info', 'config': {'selector': '#missing' if stop_early else 'h1', 'attribute': 'text', 'variableName': 'value', 'timeout': 60}}},
    ], 'edges': [{'id': 'e', 'source': 'open', 'target': 'next'}], 'variables': []}
    if not stop_early:
        document['traceMode'] = 'enhanced'
        document['nodes'][0]['data']['config']['url'] += '<script>window.workerTraceProof=17</script>'
        previous = 'next'
        for node_id, module_type, extra in [
            ('mark', 'trace_mark', {'variableName': 'marker'}),
            ('capture', 'capture_diagnostics', {'variableName': 'diagnostic'}),
            ('segment', 'save_trace_segment', {'startMarker': '{marker[id]}', 'variableName': 'segment'}),
        ]:
            document['nodes'].append({'id': node_id, 'data': {'moduleType': module_type, 'config': {'diagnosticName': node_id, **extra}}})
            document['edges'].append({'id': node_id, 'source': previous, 'target': node_id})
            previous = node_id
    payload = {**config, 'runId': 'trace-worker', 'workflowId': 'flow', 'profileId': 'test-profile', 'artifactRoot': str(tmp_path / 'artifacts'), 'requiresBrowser': True, 'document': document}
    try:
        await manager.start('trace-worker', 'test-profile', Path(executable), payload)
        async with asyncio.timeout(15):
            while not any(event.get('type') == 'execution:node_start' and event.get('nodeId') == 'next' for event in events):
                await asyncio.sleep(.02)
        if stop_early:
            await manager.stop('trace-worker')
        else:
            async with asyncio.timeout(15):
                while manager.active_processes():
                    await asyncio.sleep(.02)
        assert manager.active_processes() == []
        index = next(event for event in events if event.get('type') == 'artifact:registered' and event.get('mimeType') == TRACE_MIME)
        manifest = json.loads((tmp_path / 'artifacts' / index['relativePath']).read_bytes())
        assert manifest['archiveId'], manifest
        assert any(event.get('nodeId') == 'open' and event.get('snapshotId') for event in manifest['events'])
        assert all(event.get('executionId') for event in manifest['events'] if event['kind'] == 'execution')
        if not stop_early:
            source_ids = {event['sourceId'] for event in manifest['events'] if event.get('sourceId')}
            source_files = [tmp_path / 'artifacts' / event['relativePath'] for event in events
                            if event.get('type') == 'artifact:registered' and event.get('artifactId') in source_ids]
            assert any(b'window.workerTraceProof=17' in path.read_bytes() for path in source_files)
            for node_id in ('mark', 'capture', 'segment'):
                assert any(event.get('type') == 'execution:node_complete' and event.get('nodeId') == node_id and event.get('success') for event in events), events
            diagnostic = next(event for event in manifest['events'] if event['kind'] == 'diagnostic')
            assert diagnostic['snapshotId'] and diagnostic['domId'] and not diagnostic['gaps']
            segment_artifact = next(event for event in events if event.get('type') == 'artifact:registered' and '/segment-' in event.get('relativePath', ''))
            segment = json.loads((tmp_path / 'artifacts' / segment_artifact['relativePath']).read_bytes())
            assert segment['events'][0]['kind'] == 'mark'
            assert any(event['kind'] == 'diagnostic' for event in segment['events'])
            assert not any(event.get('nodeId') == 'open' for event in segment['events'])
    finally:
        await manager.stop('trace-worker')


@pytest.mark.asyncio
async def test_diagnostic_marker_sensitivity_and_disabled_or_missing_segment():
    from autoflow.application.workflows.executors.diagnostics import TraceMarkExecutor
    from autoflow.domain.workflows.execution import ExecutionContext
    context = ExecutionContext(variables={'secret': 'not-for-evidence'}, sensitive_variables={'secret'})
    result = await TraceMarkExecutor().execute({'diagnosticName': '标记', 'correlation': '{secret}'}, context)
    assert result.success and result.data['correlation'] == '[敏感值]'
    assert not (await TraceMarkExecutor().execute({'diagnosticName': ''}, context)).success
    trace = WorkflowTrace(SimpleNamespace(), AsyncMock(return_value='artifact'), enabled=False)
    await trace.start()
    with pytest.raises(ValueError, match='TRACE_NOT_ENABLED'):
        await trace.collect('save_trace_segment', {'startMarker': '', 'diagnosticName': '片段'}, {}, None)
    trace.enabled = True
    with pytest.raises(ValueError, match='startMarker'):
        await trace.collect('save_trace_segment', {'startMarker': 'other-trace:1', 'diagnosticName': '片段'}, {}, None)


@pytest.mark.asyncio
async def test_multiple_browser_manifests_merge_by_time_without_losing_identity(trace_store):
    _, _, save, client = trace_store
    # Archive order differs from event order, and both browsers have page-1.
    for identity, times in [('first', [2, 4]), ('second', [1, 3])]:
        manifest = {'schemaVersion': 1, 'traceId': identity, 'status': 'saved', 'archiveId': f'zip-{identity}',
                    'gaps': [], 'events': [
                        {'id': f'{identity}:{i}', 'kind': 'console', 'timeMs': i,
                         'timestamp': f'2026-09-26T00:00:0{time}+00:00', 'pageId': 'page-1', 'message': identity}
                        for i, time in enumerate(times)]}
        await save(f'trace/{identity}/index.json', json.dumps(manifest).encode(), TRACE_MIME)
    data = client.get('/api/workflow-runs/trace-run/trace?limit=3').json()
    assert data['total'] == 4 and data['nextCursor'] == 3 and data['archiveId'] is None
    assert [row['id'] for row in data['events']] == ['second:0', 'first:0', 'second:1']
    assert len(data['sessions']) == 2 and data['gaps'] == []
    tail = client.get('/api/workflow-runs/trace-run/trace?cursor=3').json()
    assert tail['events'][0]['traceId'] == 'first'
    selected = client.get('/api/workflow-runs/trace-run/trace?traceId=second').json()
    assert selected['total'] == 2 and selected['archiveId'] == 'zip-second'
    assert client.get('/api/workflow-runs/trace-run/trace?evidenceId=first:1').json()['events'][0]['traceId'] == 'first'
    assert client.get('/api/workflow-runs/trace-run/trace?traceId=other').status_code == 404


@pytest.mark.asyncio
async def test_source_capacity_dedup_and_failure_are_explicit():
    save = AsyncMock(return_value='js-artifact')
    trace = WorkflowTrace(SimpleNamespace(), save, enhanced=True)
    trace.MAX_SOURCE = 8
    trace.MAX_SOURCE_TOTAL = 8
    for url, value in [('/one', b'abc'), ('/two', b'abc'), ('/large', b'0123456789'), ('/total', b'123456')]:
        trace._source(AsyncMock(return_value=value), 'page-1', url, 'response')
    await asyncio.gather(*trace.source_tasks)
    assert save.await_count == 1
    assert [row.get('sourceId') for row in trace.events] == ['js-artifact', 'js-artifact', None, None]
    assert all(row['gaps'] for row in trace.events[2:])
    trace.source_count = 100
    read = AsyncMock(return_value=b'last')
    trace._source(read, 'page-1', '/limit', 'response')
    read.assert_not_called()
    assert any('100' in gap for gap in trace.gaps)


def test_trace_mode_survives_document_and_run_projection():
    from autoflow.domain.workflows.document import WorkflowDraft
    from autoflow.domain.workflows.errors import WorkflowDocumentError
    from autoflow.domain.workflows.models import WorkflowError
    from autoflow.domain.workflows.run_validation import prepare_run
    from tests.fixtures.workflows import workflow_payload
    payload = workflow_payload()
    for mode in ('off', 'standard', 'enhanced'):
        payload['content']['traceMode'] = mode
        prepared = prepare_run(payload)
        assert prepared.document['content']['traceMode'] == mode
        assert WorkflowDraft.from_payload(payload['content']).to_payload()['traceMode'] == mode
    payload['content']['traceMode'] = 'unknown'
    with pytest.raises(WorkflowError):
        prepare_run(payload)
    with pytest.raises(WorkflowDocumentError, match='追踪模式'):
        WorkflowDraft.from_payload(payload['content'])
