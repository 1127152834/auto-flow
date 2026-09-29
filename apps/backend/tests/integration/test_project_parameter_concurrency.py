"""Real SQLite scheduler/dispatcher; controlled workers hold slots until released."""
import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from autoflow.infrastructure.process.workflow_worker import WorkerOutcome
from tests.integration.test_project_run_data_start import _setup
from tests.integration.test_project_run_start import setup, start_payload
from tests.integration.test_workflow_dispatch import (
    ConcurrentResources,
    ConcurrentWorkers,
)


class Workers(ConcurrentWorkers):
    def __init__(self):
        super().__init__()
        self.fail = set()

    async def run(self, **values):
        await super().run(**values)
        return WorkerOutcome('failed' if values['run_id'] in self.fail else 'succeeded', None, True)


async def until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(.005)


def configure(factory, automation, *, concurrency=2, instances=2, keep_going=True, inputs=None):
    with factory.begin() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        row.run_policy = {**row.run_policy, 'concurrency': concurrency,
                          'maxLiveInstances': instances, 'continueAfterFailure': keep_going}
        if inputs is not None:
            row.input_plan = {'inputs': inputs}


def core_services(factory, capacity=2):
    workers, resources, gate = Workers(), ConcurrentResources(), QuiesceGate()
    async def cleanup(_run):
        pass
    core = WorkflowRunDispatcher(factory, workers, resources, gate, cleanup, capacity=capacity)
    return workers, core, ProjectBatchScheduler(factory, core, gate)


@pytest.mark.asyncio
@pytest.mark.parametrize('requested,configured,instances,capacity,expected', [
    (2, 2, 2, 2, 2), (1, 2, 2, 2, 1), (2, 1, 2, 2, 1),
    (2, 2, 1, 2, 1), (100, 100, 100, 2, 2), (2, 2, 2, 1, 1),
])
async def test_parameter_slots_overlap_obey_all_limits_and_refill(
    tmp_path, requested, configured, instances, capacity, expected,
):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    configure(factory, automation, concurrency=configured, instances=instances)
    batch = coordinator.start(project.project_id, automation.automation_id, str(uuid4()),
                              {**start_payload(automation, max_tasks=3), 'concurrency': requested})[0]
    workers, core, scheduler = core_services(factory, capacity)
    try:
        await scheduler.tick()
        await until(lambda: len(workers.calls) >= expected)
        assert len(workers.active) == expected
        assert len([t for t in coordinator.list_tasks(project.project_id, batch.batch_id) if t.status == 'queued']) == 3 - expected
        first = workers.calls[0]
        workers.active[first].set()
        await until(lambda: core.query_run(first).terminal)
        await scheduler.tick()
        await until(lambda: len(workers.calls) >= expected + 1)
        assert len(workers.active) == expected
        assert len(set(workers.calls)) == expected + 1
    finally:
        await core.shutdown()
        factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('keep_going', [False, True])
async def test_failure_stops_only_queued_tasks_and_does_not_cancel_running_sibling(tmp_path, keep_going):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    configure(factory, automation, keep_going=keep_going)
    batch = coordinator.start(project.project_id, automation.automation_id, str(uuid4()),
                              {**start_payload(automation, max_tasks=3), 'concurrency': 2})[0]
    workers, core, scheduler = core_services(factory)
    try:
        await scheduler.tick()
        await until(lambda: len(workers.active) == 2)
        first, second = workers.calls
        workers.fail.add(first)
        workers.active[first].set()
        await until(lambda: core.query_run(first).terminal)
        await scheduler.tick()
        assert core.query_run(second).status == 'running'
        if keep_going:
            await until(lambda: len(workers.calls) == 3)
        else:
            tasks = coordinator.list_tasks(project.project_id, batch.batch_id)
            assert [t.status for t in tasks].count('cancelled') == 1
            assert len(workers.calls) == 2
    finally:
        await core.shutdown()
        factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('keep_going', [False, True])
async def test_recovered_data_queue_obeys_failure_policy_and_releases_cancelled_claims(tmp_path, keep_going):
    from autoflow.application.project_data.records import DataRecordService
    from autoflow.infrastructure.database.project_data_records import (
        SqlAlchemyProjectDataRecords,
    )

    factory, project, automation, coordinator = _setup(tmp_path)
    configure(factory, automation, keep_going=keep_going)
    records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
    for item in automation.input_plan['inputs']:
        records.create(project, item['tableId'], str(uuid4()), {
            'datasetGeneration': item['datasetGeneration'],
            'values': [{'fieldId': item['fieldBindings'][0]['fieldRef']['fieldId'], 'value': 'second'}],
        })
    batch = coordinator.start(project, automation.automation_id, str(uuid4()), {
        'expectedAutomationRevision': automation.management_revision,
        'parameters': {}, 'maxTasks': 2, 'concurrency': 2,
    })[0]
    for _ in range(2):
        assert ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id, core_capacity=2) == 'ready'
    workers, core, scheduler = core_services(factory)
    try:
        tasks = coordinator.list_tasks(project, batch.batch_id)
        first = core.query_run(tasks[0].run_id)
        # Crash after dispatch persisted running, before a worker was created.
        core._transition_identity(first.run_id, 'running', first.status_revision, first.execution_generation)
        await core.startup()
        assert [t.status for t in coordinator.list_tasks(project, batch.batch_id)] == ['interrupted', 'queued']
        await scheduler.tick()
        if keep_going:
            await until(lambda: len(workers.calls) == 1)
            assert workers.calls == [tasks[1].run_id]
            workers.active[tasks[1].run_id].set()
            await core.wait_idle()
            await scheduler.tick()
        else:
            assert [t.status for t in coordinator.list_tasks(project, batch.batch_id)] == ['interrupted', 'cancelled']
            assert not workers.calls
        assert coordinator.get_batch(project, batch.batch_id).status == 'interrupted'
        with factory() as session:
            assert not session.scalar(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state.in_(['held', 'reconciling'])))
    finally:
        await core.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_manual_wait_counts_towards_same_automation_across_batches(tmp_path):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    configure(factory, automation, instances=1)
    batches = [coordinator.start(project.project_id, automation.automation_id, str(uuid4()),
               {**start_payload(automation), 'concurrency': 2})[0] for _ in range(2)]
    workers, core, scheduler = core_services(factory)
    try:
        await scheduler.tick()
        await until(lambda: len(workers.calls) == 1)
        first = workers.calls[0]
        core.pause_manual(first, 1)
        await scheduler.tick()
        assert len(workers.calls) == 1
        assert coordinator.get_batch(project.project_id, batches[1].batch_id).status == 'blocked'
        core.resume_manual(first, 1)
        workers.active[first].set()
        await until(lambda: core.query_run(first).terminal)
        await scheduler.tick()
        await until(lambda: len(workers.calls) == 2)
    finally:
        await core.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_parameter_queue_does_not_starve_data_claims_and_claimed_data_reserves_its_slot(tmp_path):
    factory, project, automation, coordinator = _setup(tmp_path)
    configure(factory, automation)
    payload = {'expectedAutomationRevision': automation.management_revision, 'parameters': {}, 'maxTasks': 3, 'concurrency': 2}
    data = coordinator.start(project, automation.automation_id, str(uuid4()), payload)[0]
    configure(factory, automation, inputs=[])
    parameter = coordinator.start(project, automation.automation_id, str(uuid4()), payload)[0]
    assert ProjectBatchScheduler.claim_data_task(factory, project, data.batch_id, core_capacity=2) == 'ready'
    workers, core, scheduler = core_services(factory)
    try:
        # Dispatch the parameter batch first: the already-claimed data task keeps one slot.
        await scheduler._advance(project, parameter.batch_id)
        await until(lambda: len(workers.calls) == 1)
        await scheduler.tick()
        await until(lambda: len(workers.calls) == 2)
        data_tasks = coordinator.list_tasks(project, data.batch_id)
        assert len(data_tasks) == 1 and data_tasks[0].status == 'running'
        assert len(workers.active) == 2
        with factory() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state == 'held')).all()
            assert len(leases) == 2 and {lease.task_id for lease in leases} == {data_tasks[0].task_id}
    finally:
        await core.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_stop_cancels_both_active_parameter_runs_and_never_dispatches_queue(tmp_path):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    configure(factory, automation)
    batch = coordinator.start(project.project_id, automation.automation_id, str(uuid4()),
                              {**start_payload(automation, max_tasks=3), 'concurrency': 2})[0]
    workers, core, scheduler = core_services(factory)
    try:
        await scheduler.tick()
        await until(lambda: len(workers.active) == 2)
        current = coordinator.get_batch(project.project_id, batch.batch_id)
        await scheduler.stop(project.project_id, batch.batch_id, str(uuid4()),
                             {'expectedStatusRevision': current.status_revision, 'reason': '用户停止'})
        await scheduler.tick()
        await core.wait_idle()
        await scheduler.tick()
        assert len(workers.calls) == 2
        assert {t.status for t in coordinator.list_tasks(project.project_id, batch.batch_id)} == {'cancelled'}
        assert coordinator.get_batch(project.project_id, batch.batch_id).status == 'stopped'
    finally:
        await core.shutdown()
        factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('data_batch', [False, True])
async def test_scheduler_dispatches_two_production_workers_with_exclusive_record_groups(tmp_path, monkeypatch, data_batch):
    from autoflow.application.project_data.records import DataRecordService
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.infrastructure.database.project_data_records import (
        SqlAlchemyProjectDataRecords,
    )
    from autoflow.infrastructure.database.workflow_runtime import (
        SqlAlchemyWorkflowRuntimeRepository,
    )
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
    from autoflow.infrastructure.process.project_workflow_worker import (
        ProjectWorkflowWorkerManager,
    )
    from tests.integration.test_project_data_worker import _pure_data_document

    if data_batch:
        factory, project_id, automation, coordinator = _setup(tmp_path)
        records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
        for item in automation.input_plan['inputs']:
            records.create(project_id, item['tableId'], str(uuid4()), {
                'datasetGeneration': item['datasetGeneration'],
                'values': [{'fieldId': item['fieldBindings'][0]['fieldRef']['fieldId'], 'value': '第二条'}],
            })
        payload = {'expectedAutomationRevision': automation.management_revision, 'parameters': {}, 'maxTasks': 3, 'concurrency': 2}
    else:
        factory, _, _, coordinator, _, project, automation = setup(tmp_path)
        project_id = project.project_id
        payload = {**start_payload(automation, max_tasks=3), 'concurrency': 2}
    configure(factory, automation)
    document = _pure_data_document(automation.workflow_id)
    WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
        automation.workflow_id, {**document['content'], 'id': automation.workflow_id},
        expected_revision=1, client_request_id=str(uuid4()),
    )
    batch = coordinator.start(project_id, automation.automation_id, str(uuid4()), payload)[0]
    worker = ProjectWorkflowWorkerManager(tmp_path / 'real-workers', start_timeout=10, capacity=2)
    gates = {}
    original_run = worker.run
    async def hold_first_event(**kwargs):
        persist = kwargs['on_event']
        async def on_event(event):
            await persist(event)
            identity = event['runId']
            if identity not in gates:
                gates[identity] = asyncio.Event()
                await gates[identity].wait()
        return await original_run(**{**kwargs, 'on_event': on_event})
    monkeypatch.setattr(worker, 'run', hold_first_event)
    async def cleanup(_run):
        pass
    gate = QuiesceGate()
    core = WorkflowRunDispatcher(factory, worker, ConcurrentResources(), gate, cleanup, capacity=2)
    scheduler = ProjectBatchScheduler(factory, core, gate)
    try:
        await scheduler.tick()
        async with asyncio.timeout(20):
            while len(gates) != 2:
                assert not any(t.status == 'failed' for t in coordinator.list_tasks(project_id, batch.batch_id))
                await asyncio.sleep(.01)
        assert len({item.process.pid for item in worker._workers.values()}) == 2
        tasks = coordinator.list_tasks(project_id, batch.batch_id)
        assert len([t for t in tasks if t.status == 'running']) == 2
        if data_batch:
            with factory() as session:
                leases = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state == 'held')).all()
                assert len(leases) == 4 and len({lease.lease_key for lease in leases}) == 4
                assert {lease.task_id for lease in leases} == {t.task_id for t in tasks}
                assert all(sum(lease.task_id == t.task_id for lease in leases) == 2 for t in tasks)
        first, second = list(gates)
        gates[first].set()
        await until(lambda: core.query_run(first).terminal)
        assert worker.busy(second) and core.query_run(second).status == 'running'
        await scheduler.tick()
        async with asyncio.timeout(20):
            while len(gates) != 3:
                await asyncio.sleep(.01)
        if data_batch:
            with factory() as session:
                held = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state == 'held')).all()
                assert len(held) == len({lease.lease_key for lease in held}) == 4
                # The completed input group can be reused, never the still-active group's rows.
                assert second in {lease.run_id for lease in held} and first not in {lease.run_id for lease in held}
        for event in gates.values():
            event.set()
        await core.wait_idle()
        await scheduler.tick()
        assert coordinator.get_batch(project_id, batch.batch_id).status == 'completed'
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            for run_id in gates:
                events = repository.list_events(run_id, after_sequence=0, limit=100)
                assert any(event.kind == 'output' and event.payload.get('value') == (3, 2, 1) for event in events)
            assert not session.scalar(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.state == 'held'))
        assert not worker.busy()
    finally:
        for event in gates.values():
            event.set()
        await core.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_unknown_cleanup_keeps_automation_instance_occupied_until_reconciled(tmp_path):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    configure(factory, automation, instances=1)
    batches = [coordinator.start(project.project_id, automation.automation_id, str(uuid4()),
               {**start_payload(automation), 'concurrency': 2})[0] for _ in range(2)]
    workers, core, scheduler = core_services(factory)
    try:
        await scheduler.tick()
        await until(lambda: len(workers.calls) == 1)
        first = workers.calls[0]
        workers.cleanup_fail.add(first)
        workers.active[first].set()
        await until(lambda: core.query_run(first).status == 'reconciling')
        await scheduler.tick()
        assert len(workers.calls) == 1
        assert coordinator.get_batch(project.project_id, batches[1].batch_id).status == 'blocked'
        workers.cleanup_fail.clear()
        assert (await core.reconcile(first)).terminal
        await scheduler.tick()
        await until(lambda: len(workers.calls) == 2)
    finally:
        workers.cleanup_fail.clear()
        await core.shutdown()
        factory.dispose()


from tests.integration.test_workflow_real_cloakbrowser import (
    real_cloak_page as real_cloak_page,  # noqa: PLC0414
)


@pytest.mark.asyncio
@pytest.mark.parametrize('pending_initialization', [False, True])
async def test_parallel_browser_tasks_copy_one_template_and_cancel_independently(tmp_path, real_cloak_page, pending_initialization):
    from contextlib import nullcontext
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from autoflow.application.environments.service import EnvironmentService
    from autoflow.application.project_runs.worker_capabilities import (
        ProjectWorkerCapabilities,
    )
    from autoflow.application.workflows.browser_resources import (
        WorkflowBrowserResources,
    )
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.domain.kernels.models import InstalledKernel
    from autoflow.domain.profiles.models import Profile, ProfileSpec
    from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
    from autoflow.infrastructure.database.workflow_runtime import (
        SqlAlchemyWorkflowRuntimeRepository,
    )
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
    from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore
    from autoflow.infrastructure.process.project_workflow_worker import (
        ProjectWorkflowWorkerManager,
    )
    from tests.fixtures.workflows import workflow_payload

    executable, url, _requests = real_cloak_page
    factory, projects, _, coordinator, _, project, automation = setup(tmp_path)
    now = datetime.now(UTC)
    profile = Profile(str(uuid4()), ProfileSpec.from_values({
        'name': 'parallel-template', 'browser_version': '145.0.7632.109.2', 'headless': True, 'geoip': False,
    }), 31415, now, now)
    environments = EnvironmentService(projects, SqlAlchemyEnvironments(factory), EnvironmentStore(tmp_path / 'envs'))
    task_ids = {}
    async def no_proxy(*_):
        return None
    resources = WorkflowBrowserResources(
        SimpleNamespace(get=lambda _: profile),
        lambda: [InstalledKernel('public', profile.spec.browser_version, executable, 0)],
        no_proxy, lambda: None, SimpleNamespace(guard=lambda _: nullcontext()), lambda _: nullcontext(),
        environment_directory=lambda run_id: environments.instance_path(
            environments.environments.find_instance_by_task(project.project_id, task_ids[run_id]).instance_id),
    )
    frozen = {**resources.freeze(profile.id), 'environmentPolicy': {'source': 'newFromProfile', 'profileId': profile.id}}
    coordinator._resolve_resources = lambda *args, **kwargs: {'browser': 'node', 'nodeBrowserEnvironments': {'login': frozen, 'account': frozen}}
    doc = workflow_payload(automation.workflow_id)['content']
    base = url.removesuffix('/fixture')
    nodes = [
        {'id': 'login', 'type': 'open_page', 'data': {'url': base + '/login', 'browserEnvironment': {'source': 'profile', 'profileId': profile.id}}},
        {'id': 'account', 'type': 'open_page', 'data': {'url': base + '/account', 'browserEnvironment': {'source': 'profile', 'profileId': profile.id}}},
        {'id': 'read', 'type': 'get_element_info', 'data': {'selector': '#auth', 'attribute': 'text', 'variableName': 'signedIn', 'timeout': 5}},
        {'id': 'timer', 'type': 'scheduled_task', 'data': {'config': {'scheduleType': 'delay', 'delaySeconds': 5}}},
    ]
    for index, node in enumerate(nodes):
        node['position'] = {'x': index * 200, 'y': 0}
        node['data']['moduleType'] = node['type']
    doc.update(schemaVersion=3, browserEnvironmentVersion=1, nodes=nodes, edges=[
        {'id': 'a', 'source': 'login', 'target': 'account'}, {'id': 'b', 'source': 'account', 'target': 'read'},
        {'id': 'c', 'source': 'read', 'target': 'timer'},
    ])
    WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
        automation.workflow_id, {**doc, 'id': automation.workflow_id}, expected_revision=1, client_request_id=str(uuid4()),
    )
    configure(factory, automation)
    batch = coordinator.start(project.project_id, automation.automation_id, str(uuid4()),
                              {**start_payload(automation, max_tasks=2), 'concurrency': 2})[0]
    tasks = coordinator.list_tasks(project.project_id, batch.batch_id)
    task_ids.update({task.run_id: task.task_id for task in tasks})
    capabilities = ProjectWorkerCapabilities(factory, environments)
    gates = {}
    async def hold_initialization(run_id, generation, request):
        result = await capabilities.handle(run_id, generation, request)
        if request['operation'] == 'initializeBrowser' and run_id not in gates:
            gates[run_id] = asyncio.Event()
            await gates[run_id].wait()
        return result
    manager = ProjectWorkflowWorkerManager(tmp_path / 'browser-workers', on_capability=hold_initialization, capacity=2)
    gate = QuiesceGate()
    async def cleanup(_run):
        pass
    core = WorkflowRunDispatcher(factory, manager, resources, gate, cleanup, capacity=2)
    capabilities.browser_dispatcher = core
    scheduler = ProjectBatchScheduler(factory, core, gate)
    try:
        await scheduler.tick()
        async with asyncio.timeout(45):
            while len(gates) != 2:
                assert not any(core.query_run(task.run_id).terminal for task in tasks)
                await asyncio.sleep(.02)
        instances = [environments.environments.find_instance_by_task(project.project_id, task.task_id) for task in tasks]
        assert len({item.instance_id for item in instances}) == 2
        assert len({environments.instance_path(item.instance_id) for item in instances}) == 2
        assert all(item.profile_id == profile.id for item in instances)
        first, second = list(gates)
        if not pending_initialization:
            gates[first].set()
            def timer_started():
                with factory() as session:
                    events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(first, after_sequence=0, limit=100)
                    return any(event.node_id == 'timer' and event.kind == 'nodeAttempt' for event in events)
            async with asyncio.timeout(30):
                while not timer_started():
                    await asyncio.sleep(.02)
        current = core.query_run(first)
        await core.cancel(first, expected_status_revision=current.status_revision, execution_generation=current.execution_generation)
        await until(lambda: core.query_run(first).terminal)
        assert manager.busy(second) and core.query_run(second).status == 'running'
        gates[second].set()
        await core.wait_idle()
        # A process exiting before a capability reply is confirmed stays an unknown result.
        assert core.query_run(first).status == ('interrupted' if pending_initialization else 'cancelled')
        assert core.query_run(second).status == 'succeeded'
        with factory() as session:
            events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(second, after_sequence=0, limit=100)
            assert any(event.kind == 'output' and event.payload.get('value') == 'signed-in' for event in events)
        assert resources.freeze(profile.id) == {key: value for key, value in frozen.items() if key != 'environmentPolicy'}
        assert not manager.busy()
    finally:
        for event in gates.values():
            event.set()
        await core.shutdown()
        factory.dispose()
