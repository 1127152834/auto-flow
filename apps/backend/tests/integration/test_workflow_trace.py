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
async def test_real_cloak_trace_survives_browser_close(trace_store, tmp_path, monkeypatch):
    executable = os.environ.get('AUTOFLOW_B1_CLOAK_EXECUTABLE')
    if not executable:
        pytest.skip('requires installed CloakBrowser')
    from autoflow.providers.browser.workflow_session import launch_workflow_session

    monkeypatch.setenv('CLOAKBROWSER_BINARY_PATH', executable)
    monkeypatch.setenv('CLOAKBROWSER_CACHE_DIR', str(tmp_path / 'cache'))
    service, repository, save, client = trace_store
    command = {'fingerprintSeed': 12345, 'expertArgs': [], 'locale': 'zh-CN', 'timezone': 'Asia/Shanghai', 'colorScheme': 'light', 'geoip': False, 'humanize': False, 'humanPreset': 'default', 'extensionPaths': [], 'licenseKey': None, 'browserVersion': '145.0.7632.109.2', 'releaseChannel': 'stable', 'headless': True}
    async def webpage(reader, writer):
        await reader.read(4096)
        body = b'<button id="b" onclick="this.textContent=\'done\';console.log(\'trace-click\');setTimeout(()=>{throw Error(\'trace-error\')},0)">click</button>'
        writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: ' + str(len(body)).encode() + b'\r\nConnection: close\r\n\r\n' + body)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
    async with await asyncio.start_server(webpage, '127.0.0.1', 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with launch_workflow_session(command) as browser:
            await browser.start_trace(save)
            page = browser.current_page()._raw
            await page.goto(f'http://127.0.0.1:{port}/')
            await page.click('#b')
            await browser.trace.execution({'type': 'execution:node_complete', 'nodeId': 'click', 'executionId': 'exec-1', 'success': True}, browser)
            assert await page.inner_text('#b') == 'done'
    service.finish('trace-run', status='completed', cleanup_completed=True)
    data = client.get('/api/workflow-runs/trace-run/trace').json()
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
    finally:
        await manager.stop('trace-worker')
