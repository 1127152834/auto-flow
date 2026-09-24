import os
from dataclasses import asdict
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from autoflow.application.environments.service import EnvironmentService
from autoflow.application.project_runs.worker_capabilities import (
    ProjectWorkerCapabilities,
)
from autoflow.application.projects.service import ProjectService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher, _RunOwner
from autoflow.domain.profiles.models import ProfileSpec
from autoflow.domain.project_runs.worker_commands import project_command_id
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
)
from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunRow,
)
from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore
from tests.integration.test_project_capability_fencing import (
    capability_context as capability_context,  # noqa: PLC0414
)


@pytest.mark.asyncio
async def test_authorized_initialization_replays_one_instance_and_fences_other_attempts(capability_context, tmp_path):
    factory, project_id, task, *_ = capability_context
    profile_id, visit = str(uuid4()), str(uuid4())
    resources = {'browser': 'newFromProfile', 'profileId': profile_id, 'kernelId': 'public:1',
                 'environmentPolicy': {'source': 'newFromProfile', 'profileId': profile_id},
                 'frozenConfiguration': {'profileSpec': asdict(ProfileSpec.from_values({'name': 'template', 'browser_version': '1'})), 'fingerprintSeed': 42, 'createdAt': datetime.now(UTC).isoformat(), 'updatedAt': datetime.now(UTC).isoformat()}}
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.resource_request = {'browser': 'node', 'nodeBrowserEnvironments': {'open': resources}}
        prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        prepared.execution_plan = {'nodes': [{'nodeId': 'open', 'moduleType': 'open_page', 'data': {'browserEnvironment': {'source': 'newFromProfile'}}}]}
        SqlAlchemyWorkflowRuntimeRepository(session).append_event({'eventId': str(uuid4()), 'runId': task.run_id, 'executionGeneration': 1, 'nodeId': 'open', 'nodeVisitId': visit, 'attempt': 1, 'kind': 'nodeAttempt', 'occurredAt': datetime.now(UTC), 'payload': {'status': 'started'}})
    environments = EnvironmentService(ProjectService(SqlAlchemyProjects(factory)), SqlAlchemyEnvironments(factory), EnvironmentStore(tmp_path / 'instances'))
    acquired = []
    async def acquire(snapshot, request_id):
        acquired.append((snapshot, request_id))
        return SimpleNamespace(browser={'fingerprintSeed': 42}, executable=tmp_path / 'chrome', release=lambda: None)
    dispatcher = WorkflowRunDispatcher(factory, None, SimpleNamespace(acquire=acquire), QuiesceGate(), None)
    dispatcher._owners[task.run_id] = _RunOwner(task.run_id, 1)
    capabilities = ProjectWorkerCapabilities(factory, environments)
    capabilities.browser_dispatcher = dispatcher
    request = {'nodeId': 'open', 'nodeVisitId': visit, 'attempt': 1, 'commandId': project_command_id(task.run_id, 1, visit), 'operation': 'initializeBrowser', 'arguments': {}}
    first = await capabilities.handle(task.run_id, 1, request)
    replay = await capabilities.handle(task.run_id, 1, request)
    assert first == replay and len(acquired) == 1
    saved = environments.environments.find_instance_by_task(project_id, task.task_id)
    assert saved.instance_id == request['commandId']
    assert saved.identity_package['frozenConfiguration']['fingerprintSeed'] == 42
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectEnvironmentInstanceRow)) == 1
    with pytest.raises(ProjectError) as forbidden:
        await capabilities.handle(task.run_id, 1, {**request, 'arguments': {'userDataDir': '/untrusted'}})
    assert forbidden.value.code == 'CAPABILITY_SCOPE_DENIED'
    second_visit = str(uuid4())
    with factory.begin() as session:
        SqlAlchemyWorkflowRuntimeRepository(session).append_event({'eventId': str(uuid4()), 'runId': task.run_id, 'executionGeneration': 1, 'nodeId': 'open', 'nodeVisitId': second_visit, 'attempt': 1, 'kind': 'nodeAttempt', 'occurredAt': datetime.now(UTC), 'payload': {'status': 'started'}})
    with pytest.raises(ProjectError) as duplicate:
        await capabilities.handle(task.run_id, 1, {**request, 'nodeVisitId': second_visit, 'commandId': project_command_id(task.run_id, 1, second_visit)})
    assert duplicate.value.code == 'BROWSER_INSTANCE_ALREADY_INITIALIZED'
    with factory.begin() as session:
        session.get(WorkflowRunRow, task.run_id).execution_generation = 2
    with pytest.raises(ProjectError):
        await capabilities.handle(task.run_id, 1, request)
    assert len(acquired) == 1


from tests.integration.test_workflow_real_cloakbrowser import (
    real_cloak_page as real_cloak_page,  # noqa: PLC0414
)


@pytest.mark.asyncio
async def test_real_worker_delayed_browser_keeps_cookie_in_one_task(capability_context, tmp_path, real_cloak_page):
    import asyncio
    from contextlib import nullcontext

    from autoflow.application.workflows.browser_resources import (
        WorkflowBrowserResources,
    )
    from autoflow.domain.kernels.models import InstalledKernel
    from autoflow.domain.profiles.models import Profile
    from autoflow.infrastructure.process.project_workflow_worker import (
        ProjectWorkflowWorkerManager,
    )

    factory, project_id, task, *_ = capability_context
    executable, url, requests = real_cloak_page
    now = datetime.now(UTC)
    profile = Profile(str(uuid4()), ProfileSpec.from_values({'name': 'node-real', 'browser_version': os.environ.get('AUTOFLOW_TEST_CLOAK_VERSION', '145.0.7632.109.2'), 'headless': True, 'geoip': False}), 31415, now, now)
    environments = EnvironmentService(ProjectService(SqlAlchemyProjects(factory)), SqlAlchemyEnvironments(factory), EnvironmentStore(tmp_path / 'envs'))
    from autoflow.providers.browser.environment_browser import (
        EnvironmentBrowserLauncher,
    )
    environments._closer = EnvironmentBrowserLauncher(None, list, environments.store).closer
    async def no_proxy(*_): return None
    resources = WorkflowBrowserResources(SimpleNamespace(get=lambda _: profile), lambda: [InstalledKernel('public', profile.spec.browser_version, executable, 0)], no_proxy, lambda: None, SimpleNamespace(guard=lambda _: nullcontext()), lambda _: nullcontext(), environment_directory=lambda _: environments.instance_path(environments.environments.find_instance_by_task(project_id, task.task_id).instance_id))
    frozen = {**resources.freeze(profile.id), 'environmentPolicy': {'source': 'newFromProfile', 'profileId': profile.id}}
    base = url.removesuffix('/fixture')
    nodes = [
        {'id': 'login', 'type': 'open_page', 'data': {'moduleType': 'open_page', 'url': base + '/login', 'browserEnvironment': {'source': 'newFromProfile'}, 'timeout': 15}},
        {'id': 'account', 'type': 'open_page', 'data': {'moduleType': 'open_page', 'url': base + '/account', 'browserEnvironment': {'source': 'current'}, 'timeout': 15}},
        {'id': 'read', 'type': 'get_element_info', 'data': {'moduleType': 'get_element_info', 'selector': '#auth', 'attribute': 'text', 'variableName': 'signedIn', 'timeout': 5}},
        {'id': 'end', 'type': 'project_end', 'data': {'moduleType': 'project_end', 'retainEnvironment': {'enabled': True, 'mode': 'saveAs', 'name': 'node-account'}}},
    ]
    plan = {'document': {'schemaVersion': 3, 'browserEnvironmentVersion': 1, 'nodes': nodes, 'edges': [{'id': 'a', 'source': 'login', 'target': 'account'}, {'id': 'b', 'source': 'account', 'target': 'read'}, {'id': 'c', 'source': 'read', 'target': 'end'}]}, 'nodes': [{'nodeId': node['id'], 'moduleType': node['type'], 'data': node['data']} for node in nodes]}
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.resource_request = {'browser': 'node', 'nodeBrowserEnvironments': {'login': frozen}}
        session.get(WorkflowPreparedContentRow, run.prepared_content_id).execution_plan = plan
    capabilities = ProjectWorkerCapabilities(factory, environments)
    manager = ProjectWorkflowWorkerManager(tmp_path / 'worker', on_capability=capabilities.handle)
    dispatcher = WorkflowRunDispatcher(factory, manager, resources, QuiesceGate(), None)
    owner = _RunOwner(task.run_id, 1); dispatcher._owners[task.run_id] = owner
    capabilities.browser_dispatcher = dispatcher
    events = []
    async def persist(event):
        with factory.begin() as session: SqlAlchemyWorkflowRuntimeRepository(session).append_event(event)
        events.append(event)
    try:
        result = await asyncio.wait_for(manager.run(run_id=task.run_id, execution_generation=1, execution_plan=plan, parameters={}, variables={}, browser={}, executable=None, on_event=persist), 45)
        assert result.status == 'succeeded' and result.cleanup_confirmed, [e['payload'] for e in events if e['kind'] == 'nodeAttempt' and e['payload']['status'] == 'failed']
        assert '/login' in requests and '/account' in requests
        assert any(event['kind'] == 'output' and event['payload'].get('value') == 'signed-in' for event in events), events
        instance = environments.environments.find_instance_by_task(project_id, task.task_id)
        assert instance.identity_package['frozenConfiguration']['fingerprintSeed'] == 31415
        from autoflow.infrastructure.database.environment_models import (
            ProjectEnvironmentRow,
        )
        with factory() as db:
            saved = db.scalar(select(ProjectEnvironmentRow).where(ProjectEnvironmentRow.project_id == project_id))
            assert saved is not None and saved.name == 'node-account'
            assert environments.store.generation_identity(saved.id, saved.content_generation) == instance.identity_package
        assert not manager.busy()
    finally:
        await manager.shutdown()
        dispatcher._release_lease(owner)

@pytest.mark.asyncio
async def test_real_studio_node_browser_without_global_profile(tmp_path, real_cloak_page):
    import asyncio
    from contextlib import nullcontext

    from autoflow.adapters.events.workflows import StudioEventJournal
    from autoflow.application.workflows.browser_resources import (
        WorkflowBrowserResources,
    )
    from autoflow.application.workflows.coordinator import WorkflowRunCoordinator
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.application.workflows.executors.production import (
        build_production_executor_registry,
    )
    from autoflow.application.workflows.runs import WorkflowRunService
    from autoflow.application.workflows.runtime import WorkflowRuntime
    from autoflow.domain.kernels.models import InstalledKernel
    from autoflow.domain.profiles.models import Profile
    from autoflow.infrastructure.database.session import (
        create_session_factory,
        migrate_database,
    )
    from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
    from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager
    from tests.unit.workflows.test_run_coordinator import FakeResources

    executable, url, requests = real_cloak_page
    now = datetime.now(UTC)
    profile = Profile(str(uuid4()), ProfileSpec.from_values({'name': 'studio-node', 'browser_version': os.environ.get('AUTOFLOW_TEST_CLOAK_VERSION', '145.0.7632.109.2'), 'geoip': False}), 31415, now, now)
    async def no_proxy(*_): return None
    profiles = SimpleNamespace(get=lambda _: profile)
    installed = lambda: [InstalledKernel('public', profile.spec.browser_version, executable, 0)]
    resources = WorkflowBrowserResources(profiles, installed, no_proxy, lambda: None, SimpleNamespace(guard=lambda _: nullcontext()), lambda _: nullcontext())
    migrate_database(tmp_path / 'studio.db')
    factory = create_session_factory(tmp_path / 'studio.db')
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    base = url.removesuffix('/fixture')
    nodes = [
        {'id': 'login', 'type': 'moduleNode', 'data': {'moduleType': 'open_page', 'config': {'url': base + '/login', 'browserEnvironment': {'source': 'newFromProfile', 'profileId': profile.id}}}},
        {'id': 'account', 'type': 'moduleNode', 'data': {'moduleType': 'open_page', 'config': {'url': base + '/account', 'browserEnvironment': {'source': 'current'}}}},
        {'id': 'read', 'type': 'moduleNode', 'data': {'moduleType': 'get_element_info', 'config': {'selector': '#auth', 'attribute': 'text', 'variableName': 'signedIn'}}},
    ]
    documents.create({'id': 'studio-node-flow', 'name': 'node', 'schemaVersion': 3, 'browserEnvironmentVersion': 1, 'nodes': nodes, 'edges': [{'id': 'a', 'source': 'login', 'target': 'account'}, {'id': 'b', 'source': 'account', 'target': 'read'}], 'variables': []}, client_request_id='studio-node-create')
    repository = SqlAlchemyWorkflowRuns(factory)
    runs = WorkflowRunService(repository)
    done = asyncio.Event()
    async def on_exit(run_id, code):
        await coordinator.on_worker_exit(run_id, code)
        done.set()
    workers = WorkflowWorkerManager(tmp_path / 'workers', on_event=lambda event: coordinator.on_worker_event(event), on_exit=on_exit)
    coordinator = WorkflowRunCoordinator(documents=documents, runs=runs, run_repository=repository, runtime=WorkflowRuntime(build_production_executor_registry()), profiles=profiles, installed_kernels=installed, resolve_proxy=no_proxy, read_license=lambda: None, workers=workers, resources=FakeResources(), events=StudioEventJournal(), artifact_root=tmp_path)
    coordinator.configure_node_browser_environments(resources, None)
    run_id = str(uuid4())
    try:
        await coordinator.start('studio-node-flow', {'runId': run_id, 'documentId': 'studio-node-flow', 'headless': True})
        await asyncio.wait_for(done.wait(), 45)
        run = runs.get(run_id)
        assert run.status == 'completed', (run, workers.failure(run_id), runs.events(run_id))
        events = runs.events(run_id)
        read = next(event for event in events if event.node_id == 'read' and event.type == 'execution:node-succeeded')
        assert 'signed-in' in str(read.payload)
        assert requests.count('/login') == 1 and requests.count('/account') == 1
        assert not workers.busy() and not coordinator._node_browser_leases
    finally:
        await workers.shutdown()
