"""Project webhook uses the real runtime, worker, SQLite and loopback HTTP/SSE."""
from __future__ import annotations

import asyncio
import json
import os
import socket
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from sqlalchemy import select

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.project_run_events import project_run_events_router
from autoflow.adapters.http.workflow_runs import workflow_trigger_router
from autoflow.application.project_runs.events import ProjectRunEvents
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.bootstrap.workflows import PendingWorkflowRunCommands
from autoflow.domain.workflows.catalog import runnable_module_types
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.workflows import (
    SqlAlchemyWorkflowDocuments,
    SqlAlchemyWorkflowRepository,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from tests.integration.test_project_data_worker import (
    _dispatcher,
    _NoBrowserResources,
    _studio_payload,
)
from tests.integration.test_project_run_start import setup, start_payload


@pytest.mark.asyncio
@pytest.mark.parametrize('scenario', ['deliver', 'nested', 'lost_response', 'stop', 'timeout'])
async def test_project_webhook_real_network_delivery_and_cleanup(tmp_path: Path, scenario: str):
    assert 'webhook_trigger' in runnable_module_types()
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    document = _studio_payload(automation.workflow_id)
    document.update(schemaVersion=3, nodes=[
        {'id': 'hook', 'type': 'webhook_trigger', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'webhook_trigger', 'config': {
            'webhookId': 'project-hook', 'method': 'POST', 'timeout': 1 if scenario == 'timeout' else 30,
            'validateHeaders': '{"X-Hook-Check":"fixture-secret"}', 'validateParams': '{"key":"fixture-query"}',
            'responseBody': '{"accepted":true}', 'responseStatus': 202,
        }}},
        {'id': 'after', 'type': 'print_log', 'position': {'x': 150, 'y': 0}, 'data': {'moduleType': 'print_log', 'config': {'logMessage': '收到:{webhook_name}'}}},
    ], edges=[{'id': 'next', 'source': 'hook', 'target': 'after'}], variables=[])
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    child_id = None
    if scenario == 'nested':
        child = {**document, 'id': str(uuid4()), 'projectId': project.project_id, 'name': 'Webhook子流程'}
        child_id = documents.create(child, client_request_id=str(uuid4())).id
        document = {**document, 'nodes': [{
            'id': 'call', 'type': 'run_workflow_file', 'position': {'x': 0, 'y': 0},
            'data': {'moduleType': 'run_workflow_file', 'config': {'workflowFile': child_id}},
        }], 'edges': []}
    documents.update(
        automation.workflow_id, document, expected_revision=1, client_request_id=str(uuid4()))
    runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
    coordinator._core = runtime
    frozen = os.environ.get('AUTOFLOW_TEST_PROJECT_WORKER')
    manager = ProjectWorkflowWorkerManager(tmp_path / 'worker',
        **({'command': (str(Path(frozen).resolve(strict=True)), '--project-workflow-worker')} if frozen else {}))
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, manager, resources)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflow_trigger_router(PendingWorkflowRunCommands(), project_interactions=dispatcher.interactions))
    app.include_router(project_run_events_router(ProjectRunEvents(factory)))
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    sock.listen()
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        batch, _, _ = coordinator.start(project.project_id, automation.automation_id, str(uuid4()), start_payload(automation))
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        running = await dispatcher.dispatch(run.run_id, expected_status_revision=run.status_revision, execution_generation=run.execution_generation)
        async with asyncio.timeout(15):
            while not server.started or not dispatcher.interactions.has_webhook('project-hook'):
                assert not dispatcher.query_run(run.run_id).terminal
                await asyncio.sleep(.01)
        assert dispatcher.interactions.pending() == []  # Webhook never becomes a UI dialog.
        base = f'/api/v1/projects/{project.project_id}/tasks/{task.task_id}'
        url = '/api/triggers/webhook/project-hook?key=fixture-query'
        headers = {'X-Hook-Check': 'fixture-secret', 'Authorization': 'private-authorization', 'Cookie': 'private-cookie'}
        async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', trust_env=False) as client:
            if scenario in {'deliver', 'nested'}:
                assert (await client.get(url, headers=headers)).status_code == 404
                assert (await client.post(url, json={'name': '错误'})).status_code == 403
                assert (await client.post('/api/triggers/webhook/project-hook', headers=headers, json={})).status_code == 403
                assert (await client.post(url, headers=headers, content=b'x' * (1024 * 1024 + 1))).status_code == 413
                waiting = (await client.get(base + '/events')).json()
                assert 'fixture-secret' not in json.dumps(waiting)
                responses = await asyncio.gather(*[
                    client.post(url, headers=headers, json={'name': '项目触发'}) for _ in range(2)
                ])
                assert sorted(response.status_code for response in responses) == [202, 404]
                assert next(response for response in responses if response.status_code == 202).json() == {'accepted': True}
                assert (await client.post(url, headers=headers, json={'name': '再次触发'})).status_code == 404
            elif scenario == 'lost_response':
                _, writer = await asyncio.open_connection('127.0.0.1', port)
                body = json.dumps({'name': '项目触发'}, ensure_ascii=False).encode()
                request = f'POST {url} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nX-Hook-Check: fixture-secret\r\nConnection: close\r\n\r\n'.encode() + body
                writer.write(request)
                await writer.drain()
                writer.close()  # Request written, response deliberately not received.
                await writer.wait_closed()
            elif scenario == 'stop':
                await dispatcher.cancel(run.run_id, expected_status_revision=running.status_revision, execution_generation=running.execution_generation)
            await asyncio.wait_for(dispatcher.wait_idle(), 15)
            expected = {'deliver': 'succeeded', 'nested': 'succeeded', 'lost_response': 'succeeded', 'stop': 'cancelled', 'timeout': 'failed'}[scenario]
            assert dispatcher.query_run(run.run_id).status == expected
            assert (await client.post(url, headers=headers, json={})).status_code == 404
            persisted = (await client.get(base + '/events')).json()['items']
            if scenario in {'deliver', 'nested', 'lost_response'}:
                if scenario == 'nested':
                    waiting_event = next(e for e in persisted if e['kind'] == 'interaction' and e['payload']['type'] == 'execution:webhook_waiting')
                    assert waiting_event['payload']['executionContext']['scopes'] == [{'kind': 'workflow', 'id': child_id, 'name': 'Webhook子流程'}]
                values = {e['payload']['name']: e['payload']['value'] for e in persisted if e['kind'] == 'output'}
                assert values['webhook_data']['body'] == {'name': '项目触发'}
                assert 'authorization' not in values['webhook_data']['headers'] and 'cookie' not in values['webhook_data']['headers']
                assert any(e['kind'] == 'log' and e['payload'].get('message') == '收到:项目触发' for e in persisted)
                assert len([e for e in persisted if e['kind'] == 'interaction' and e['payload']['type'] == 'execution:command_applied']) == 1
                async with client.stream('GET', base + '/events/stream', headers={'Last-Event-ID': str(persisted[0]['sequence'])}) as response:
                    streamed = [json.loads(line[6:]) async for line in response.aiter_lines() if line.startswith('data: ')]
                assert streamed == persisted[1:]
                with factory() as session:
                    receipts = session.scalars(select(ProjectOperationRow).where(ProjectOperationRow.kind == 'workflowInteraction')).all()
                    assert len(receipts) == 1 and receipts[0].status == 'succeeded'
                    assert '项目触发' not in json.dumps(receipts[0].result)
            else:
                assert not any(e['nodeId'] == 'after' for e in persisted)
            assert 'private-authorization' not in json.dumps(persisted) and 'private-cookie' not in json.dumps(persisted)
        assert not manager.busy() and not resources.requests and not dispatcher.blockers()
    finally:
        await dispatcher.shutdown()
        server.should_exit = True
        await asyncio.wait_for(serving, 5)
        sock.close()
        factory.dispose()
