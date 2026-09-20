"""Opt-in native CloakBrowser checks, never substituted with another browser."""
import asyncio
import os
import shutil
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest

from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.infrastructure.process.project_test_browser_worker import (
    browser_worker_payload,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)


@pytest.fixture
def real_cloak_page():
    configured = os.environ.get('AUTOFLOW_TEST_CLOAKBROWSER')
    if not configured:
        pytest.skip('set AUTOFLOW_TEST_CLOAKBROWSER to an installed real CloakBrowser executable')
    executable = Path(configured).resolve(strict=True)
    page = Path(__file__).parents[1] / 'fixtures' / 'project-management' / 'index.html'
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            content = page.read_bytes()
            if self.path == '/account':
                signed_in = 'pm9-login=verified' in self.headers.get('Cookie', '')
                content = f'<output id=auth>{"signed-in" if signed_in else "signed-out"}</output>'.encode()
            self.send_response(200)
            if self.path == '/login':
                self.send_header('Set-Cookie', 'pm9-login=verified; Path=/; HttpOnly; Max-Age=3600; SameSite=Lax')
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield executable, f'http://127.0.0.1:{server.server_port}/fixture', requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.asyncio
@pytest.mark.parametrize('scenario', ['success', 'stop_before_navigation', 'node_timeout'])
async def test_real_cloakbrowser_worker_lifecycle(tmp_path, valid_profile_values, real_cloak_page, scenario):
    executable, url, requests = real_cloak_page
    now = datetime.now(UTC)
    profile = Profile(str(uuid4()), ProfileSpec.from_values({**valid_profile_values, 'headless': True}), 31415, now, now)
    run_id = str(uuid4())
    browser = browser_worker_payload(run_id, profile, None, None)
    browser['headless'] = True
    nodes = [
        {'nodeId': 'open', 'moduleType': 'open_page', 'data': {'url': url, 'timeout': 15}},
        {'nodeId': 'input', 'moduleType': 'input_text', 'data': {'selector': '#missing' if scenario == 'node_timeout' else '#field', 'text': '{suffix}', 'clearBefore': False, 'timeout': .1 if scenario == 'node_timeout' else 5}},
        {'nodeId': 'read-input', 'moduleType': 'get_element_info', 'data': {'selector': '#field', 'attribute': 'value', 'variableName': 'input', 'timeout': 5}},
        {'nodeId': 'click', 'moduleType': 'click_element', 'data': {'selector': '#button', 'timeout': 5}},
        {'nodeId': 'read-click', 'moduleType': 'get_element_info', 'data': {'selector': '#button', 'attribute': 'data-clicked', 'variableName': 'clicked', 'timeout': 5}},
    ]
    manager = ProjectWorkflowWorkerManager(tmp_path, start_timeout=45)
    events = []

    async def persist(event):
        events.append(event)
        if scenario == 'stop_before_navigation' and len(events) == 1:
            await manager.stop(run_id)

    try:
        outcome = await asyncio.wait_for(manager.run(
            run_id=run_id, execution_generation=1,
            execution_plan={'orderedNodeIds': [node['nodeId'] for node in nodes], 'nodes': nodes},
            parameters={'suffix': '-追加'}, variables={}, browser=browser,
            executable=executable, on_event=persist,
        ), timeout=60)
        assert outcome.cleanup_confirmed and not manager.busy()
        assert not list((tmp_path / 'workflow-runs' / run_id).glob('generation-*'))
        if scenario == 'success':
            assert outcome.status == 'succeeded'
            outputs = {event['payload']['name']: event['payload']['value'] for event in events if event['kind'] == 'output'}
            assert outputs == {'input': 'before-追加', 'clicked': 'yes'}
            assert requests[0] == '/fixture'
        elif scenario == 'stop_before_navigation':
            assert outcome.status == 'cancelled'
            assert len(events) == 1 and requests == []
        else:
            assert outcome.status == 'failed'
            failed_attempts = [
                event for event in events
                if event['kind'] == 'nodeAttempt'
                and event['payload'].get('status') == 'failed'
            ]
            assert len(failed_attempts) == 1
            assert failed_attempts[0]['payload']['error']['code'] == 'WORKFLOW_NODE_TIMEOUT'
            assert not any(event['nodeId'] == 'click' for event in events)
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_real_cloakbrowser_persisted_dispatch_and_service_recreation(tmp_path, valid_profile_values, real_cloak_page):
    from autoflow.application.workflows.service import WorkflowService
    from autoflow.bootstrap.app import create_app
    from autoflow.bootstrap.config import Settings
    from autoflow.infrastructure.database.workflow_runtime import (
        SqlAlchemyWorkflowRuntimeRepository,
    )
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
    from tests.fixtures.workflows import workflow_payload

    executable, url, _ = real_cloak_page
    source = next(parent for parent in executable.parents if parent.name.startswith('chromium-'))
    workspace = tmp_path / 'isolated-workspace'
    target = workspace / 'data' / 'kernels' / source.name
    await asyncio.to_thread(shutil.copytree, source, target, symlinks=True)
    settings = Settings(data_dir=str(workspace), instance_id='real-workflow-fixture')
    app = create_app(settings)
    try:
        profile = app.state.profile_service.create(ProfileSpec.from_values({
            **valid_profile_values, 'headless': True,
            'browser_version': source.name.removeprefix('chromium-'),
        }))
        document = workflow_payload(str(uuid4()))
        nodes = document['content']['nodes']
        nodes[0]['data']['url'] = url
        nodes[1]['data'].update(selector='#field', clearBefore=False)
        nodes[2]['data']['selector'] = '#button'
        nodes[3]['data'].update(selector='#field', attribute='value')
        documents = WorkflowService(SqlAlchemyWorkflowRepository(app.state.session_factory))
        record = documents.create(document, str(uuid4()))
        prepared = app.state.project_workflow_runtime.prepare_content(
            prepare_operation_id=str(uuid4()), workflow_id=record.document['id'],
            source_revision=record.revision, available_capabilities=['browser.cloakbrowser'],
        )
        with app.state.session_factory() as session:
            run = app.state.project_workflow_runtime.prepare_run(
                run_request_id=str(uuid4()), prepared_content_id=prepared.prepared_content_id,
                parameters={'zero': 0, 'flag': False}, input_snapshot_ref=None,
                resource_request=app.state.project_workflow_resources.freeze(profile.id),
                capability_bindings=[], uow=session,
            )
            session.commit()
        document['content']['variables'][0]['value'] = '后续修改不应进入本次运行'
        documents.save(record.document['id'], document, record.revision, str(uuid4()))
        await app.state.project_workflow_dispatcher.dispatch(
            run.run_id, expected_status_revision=run.status_revision,
            execution_generation=run.execution_generation,
        )
        await asyncio.wait_for(app.state.project_workflow_dispatcher.wait_idle(), 60)
        result = app.state.project_workflow_runtime.query_run(run_id=run.run_id)
        assert result.status == 'succeeded'
        assert result.parameters == {'zero': 0, 'flag': False}
        with app.state.session_factory() as session:
            events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(run.run_id, after_sequence=0, limit=200)
        assert [event.payload['value'] for event in events if event.kind == 'output'] == ['before测试用户']
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
        assert events[-1].kind == 'status' and events[-1].payload['status'] == 'succeeded'
        assert app.state.project_workflow_dispatcher.blockers() == []
    finally:
        await app.router.on_shutdown[-1]()
    restored = create_app(settings)
    try:
        await restored.state.project_workflow_dispatcher.startup()
        found = restored.state.project_workflow_runtime.query_run(run_id=run.run_id)
        assert found == result
        assert not restored.state.project_workflow_worker_manager.busy()
    finally:
        await restored.router.on_shutdown[-1]()
