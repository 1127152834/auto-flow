"""PM4-C contract counterexamples using real SQLite/CoreRun, no browser E2E."""

import asyncio
import threading

import pytest
from sqlalchemy import event, func, select

from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.project_runs.scheduler import (
    ProjectBatchScheduler,
    _next_candidate_offsets,
)
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_claims import (
    SqlAlchemyProjectInputGroups,
)
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.fixtures.workflow_runs import SyntheticResources
from tests.integration.test_project_run_data_start import _setup, uid
from tests.integration.test_project_run_dispatch import Worker


class CapacityCore:
    """Deterministic core port used to prove scheduler capacity arithmetic."""

    def __init__(self, factory, capacity):
        self.runtime = WorkflowRuntimeService(factory)
        self.capacity = capacity

    def query_run(self, run_id):
        result = self.runtime.query_run(run_id=run_id)
        assert result is not None
        return result

    async def dispatch(self, run_id, *, expected_status_revision, execution_generation):
        return self.runtime.dispatch_run(
            run_id,
            expected_status_revision=expected_status_revision,
            execution_generation=execution_generation,
        )

    def finish(self, run_id, status):
        current = self.query_run(run_id)
        finishing = self.runtime._transition(
            run_id,
            target_status="finishing",
            expected_status_revision=current.status_revision,
            execution_generation=current.execution_generation,
        )
        return self.runtime._transition(
            run_id,
            target_status=status,
            expected_status_revision=finishing.status_revision,
            execution_generation=finishing.execution_generation,
        )


@pytest.fixture
def data_services(tmp_path):
    factory, project, automation, coordinator = _setup(tmp_path)
    worker, gate = Worker(), QuiesceGate()

    async def cleanup(_run):
        pass

    core = WorkflowRunDispatcher(factory, worker, SyntheticResources(), gate, cleanup)
    scheduler = ProjectBatchScheduler(factory, core, gate)
    yield factory, project, automation, coordinator, worker, core, scheduler
    factory.dispose()


def start(services, max_tasks=1):
    _, project, automation, coordinator, *_ = services
    return coordinator.start(
        project,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": max_tasks,
            "concurrency": 1,
        },
    )[0]


def test_environment_reservation_failure_rolls_back_data_task_and_run(data_services):
    from autoflow.domain.environments.rules import environment_error
    from autoflow.domain.projects.models import ProjectError

    class UnavailableEnvironment:
        def reserve_task_instance(self, *args, **kwargs):
            raise environment_error("CAPACITY_EXHAUSTED", "No environment capacity", 429)

        def attach_task_instance(self, *args, **kwargs):
            raise environment_error("CAPACITY_EXHAUSTED", "No environment capacity", 429)

    factory, project, _, _, _, _, scheduler = data_services
    batch = start(data_services)
    scheduler._environments = UnavailableEnvironment()
    with pytest.raises(ProjectError) as failure:
        scheduler._claim_data_task(project, batch.batch_id)
    assert failure.value.code == "CAPACITY_EXHAUSTED"
    with factory() as session:
        for model in (ProjectTaskRow, WorkflowRunRow, ProjectTaskInputSnapshotRow,
                      ProjectRecordLeaseRow):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_candidate_page_cursor_walks_page_pairs_without_diagonal_skips(monkeypatch):
    import autoflow.application.project_runs.scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "MAX_CANDIDATE_EVALUATIONS", 1)
    plan = {"inputs": [{"inputId": "x"}, {"inputId": "y"}]}
    assert _next_candidate_offsets(plan, {}, ("x", "y")) == {"x": 1}
    assert _next_candidate_offsets(plan, {"x": 1}, ("y",)) == {
        "x": 0,
        "y": 1,
    }
    assert _next_candidate_offsets(plan, {"x": 0, "y": 1}, ("x",)) == {
        "x": 1,
        "y": 1,
    }
    assert _next_candidate_offsets(plan, {"x": 1, "y": 1}, ()) is None


def _prepared_selection(factory, project_id, batch_id):
    prepared = ProjectBatchScheduler._prepare_data_claim(
        factory, project_id, batch_id
    )
    assert isinstance(prepared, dict)
    with factory() as session:
        selection = SqlAlchemyProjectInputGroups(session).select_required(
            project_id,
            prepared["inputPlan"],
            candidate_offsets=prepared["candidateOffsets"],
        )
    return prepared, selection


def test_claim_discards_no_match_when_records_change_before_commit(data_services):
    """A stale negative scan cannot close the gate or manufacture exhaustion."""
    factory, project, _, coordinator, *_ = data_services
    batch = start(data_services)
    with factory.begin() as session:
        for row in session.scalars(
            select(DataRecordRow).where(DataRecordRow.project_id == project)
        ):
            row.deleted = True
    prepared, selection = _prepared_selection(factory, project, batch.batch_id)
    assert selection.status == "noMatch"
    with factory.begin() as session:
        for row in session.scalars(
            select(DataRecordRow).where(DataRecordRow.project_id == project)
        ):
            row.deleted = False
    assert (
        ProjectBatchScheduler._commit_data_claim(
            factory, project, batch.batch_id, prepared, selection
        )
        == "staleSelection"
    )
    current = coordinator.get_batch(project, batch.batch_id)
    assert current.claim_gate_state == "open"
    assert coordinator.list_tasks(project, batch.batch_id) == []
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id)
        == "ready"
    )


def test_claim_discards_ready_group_when_a_record_revision_changes(data_services):
    """Preparation cannot silently absorb a later manual record edit."""
    factory, project, _, coordinator, *_ = data_services
    batch = start(data_services)
    prepared, selection = _prepared_selection(factory, project, batch.batch_id)
    assert selection.status == "ready"
    with factory.begin() as session:
        row = session.scalar(
            select(DataRecordRow).where(DataRecordRow.project_id == project)
        )
        row.content_revision += 1
    assert (
        ProjectBatchScheduler._commit_data_claim(
            factory, project, batch.batch_id, prepared, selection
        )
        == "staleSelection"
    )
    assert coordinator.list_tasks(project, batch.batch_id) == []


def test_exact_revalidation_rejects_changed_record_revisions(data_services):
    """The exact-record check preserves the revisions returned by preparation."""
    factory, project, _, _coordinator, *_ = data_services
    batch = start(data_services)
    prepared, selection = _prepared_selection(factory, project, batch.batch_id)
    assert selection.status == "ready"
    selected_ref = selection.inputs[0].record_ref
    with factory.begin() as session:
        row = session.scalar(
            select(DataRecordRow).where(
                DataRecordRow.project_id == selected_ref.project_id,
                DataRecordRow.table_id == selected_ref.table_id,
                DataRecordRow.dataset_generation
                == selected_ref.dataset_generation,
                DataRecordRow.key_type == selected_ref.record_key.type,
                DataRecordRow.key_value == selected_ref.record_key.value,
            )
        )
        assert row is not None
        row.status_revision += 1
    with factory() as session:
        current = SqlAlchemyProjectInputGroups(session).revalidate_selected(
            project,
            prepared["inputPlan"],
            selection,
        )
    assert current.status == "temporarilyBusy"
    assert current.issue_input_ids == (selection.inputs[0].input_id,)
    assert "changed" in current.issue_details[0][1]


@pytest.mark.asyncio
async def test_reuse_count_uses_physical_input_identity_not_revision_tuple(
    data_services,
):
    factory, project, _, coordinator, _, core, scheduler = data_services
    batch = start(data_services, 3)
    for _ in range(3):
        await scheduler.tick()
        await core.wait_idle()
    tasks = coordinator.list_tasks(project, batch.batch_id)
    with factory.begin() as session:
        middle = session.scalar(
            select(ProjectTaskInputSnapshotRow).where(
                ProjectTaskInputSnapshotRow.task_id == tasks[1].task_id
            )
        )
        changed = [dict(item) for item in middle.inputs]
        changed[0]["contentRevision"] += 1
        middle.inputs = changed
    detail = ProjectRunQueries(factory).batch_detail(project, batch.batch_id)
    assert detail["reusedInputGroupCount"] == 2
    assert detail["unchangedInputStreak"] == 0


def test_claim_commit_rechecks_cross_batch_live_capacity(data_services):
    """Two prepared claims cannot both pass a one-instance automation limit."""
    factory, project, automation, coordinator, *_ = data_services
    first = start(data_services)
    second = coordinator.start(
        project,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    first_prepared, first_selection = _prepared_selection(
        factory, project, first.batch_id
    )
    second_prepared, second_selection = _prepared_selection(
        factory, project, second.batch_id
    )
    assert (
        ProjectBatchScheduler._commit_data_claim(
            factory,
            project,
            first.batch_id,
            first_prepared,
            first_selection,
            core_capacity=2,
        )
        == "ready"
    )
    assert (
        ProjectBatchScheduler._commit_data_claim(
            factory,
            project,
            second.batch_id,
            second_prepared,
            second_selection,
            core_capacity=2,
        )
        == "capacityFull"
    )
    assert len(coordinator.list_tasks(project, first.batch_id)) == 1
    assert coordinator.list_tasks(project, second.batch_id) == []


def test_candidate_date_order_is_stable_across_bounded_pages(
    data_services, monkeypatch
):
    """Timezone-aware dates must be paged by instant, not raw JSON text."""
    import autoflow.infrastructure.database.project_claims as claims_module

    factory, project, automation, *_ = data_services
    monkeypatch.setattr(claims_module, "MAX_CANDIDATE_EVALUATIONS", 1)
    definition = dict(automation.input_plan["inputs"][0])
    table_id = definition["tableId"]
    generation = definition["datasetGeneration"]
    field_id = definition["fieldBindings"][0]["fieldRef"]["fieldId"]
    with factory.begin() as session:
        field = session.get(DataFieldRow, (field_id, generation))
        assert field is not None
        field.type = "date"
        existing = session.scalar(
            select(DataRecordRow).where(
                DataRecordRow.project_id == project,
                DataRecordRow.table_id == table_id,
            )
        )
        assert existing is not None
        existing.values_json = {
            field_id: {
                "kind": "date",
                "precision": "datetime",
                "value": "2026-01-01T00:00:00",
                "offset": "+08:00",
            }
        }
        existing_key = existing.key_value
        later_key = uid()
        session.add(
            DataRecordRow(
                project_id=project,
                table_id=table_id,
                dataset_generation=generation,
                key_type="uuid",
                key_value=later_key,
                values_json={
                    field_id: {
                        "kind": "date",
                        "precision": "datetime",
                        "value": "2025-12-31T20:00:00",
                        "offset": "Z",
                    }
                },
                record_slots=[],
                status_id=None,
                current_environment_id=None,
                content_revision=1,
                status_revision=1,
                link_revision=1,
                deleted=False,
                created_at=existing.created_at,
                updated_at=existing.updated_at,
            )
        )
    definition.update(
        {
            "mode": "independent",
            "required": True,
            "relation": None,
            "filter": {"type": "all", "items": []},
            "orderBy": [{"fieldId": field_id, "direction": "asc"}],
        }
    )
    plan = {"inputs": [definition]}
    selected_keys = []
    for offset in (0, 1):
        with factory() as session:
            selection = SqlAlchemyProjectInputGroups(session).select_required(
                project,
                plan,
                candidate_offsets={definition["inputId"]: offset},
            )
        assert selection.status == "ready"
        selected_keys.append(selection.inputs[0].record_ref.record_key.value)
    assert selected_keys == [existing_key, later_key]


@pytest.mark.parametrize("max_tasks", [1, 3, None])
def test_acceptance_defers_all_task_and_lease_creation(data_services, max_tasks):
    """Fails if start eagerly claims data, rejects finite >1, or rejects null."""
    factory, project, _, coordinator, *_ = data_services
    batch = start(data_services, max_tasks)
    assert coordinator.list_tasks(project, batch.batch_id) == []
    with factory() as session:
        for model in (
            ProjectTaskRow,
            ProjectTaskInputSnapshotRow,
            ProjectRecordLeaseRow,
            WorkflowRunRow,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("max_tasks", [3, None])
async def test_reusable_rows_are_claimed_again_without_batch_dedup(
    data_services, max_tasks
):
    """Fails if completed records are excluded or unlimited batches get capped."""
    _, project, _, coordinator, worker, core, scheduler = data_services
    batch = start(data_services, max_tasks)
    for _ in range(4):
        await scheduler.tick()
        await core.wait_idle()
    tasks = coordinator.list_tasks(project, batch.batch_id)
    assert len(worker.calls) == (3 if max_tasks == 3 else 4)
    refs = [
        coordinator.get_snapshot(project, task.task_id).inputs[0]["recordRef"]
        for task in tasks
    ]
    assert all(ref == refs[0] for ref in refs)
    assert len({task.run_id for task in tasks}) == len(tasks)
    current = coordinator.get_batch(project, batch.batch_id)
    if max_tasks == 3:
        assert current.status == "completed"
        detail = ProjectRunQueries(data_services[0]).batch_detail(
            project, batch.batch_id
        )
        assert detail["reusedInputGroupCount"] == 2
        assert detail["unchangedInputStreak"] == 2
    else:
        assert current.status not in {"completed", "failed", "stopped", "interrupted"}
        await scheduler.stop(
            project,
            batch.batch_id,
            uid(),
            {
                "expectedStatusRevision": current.status_revision,
                "reason": "结束不限测试",
            },
        )
        await scheduler.tick()
        assert len(coordinator.list_tasks(project, batch.batch_id)) == 4


@pytest.mark.asyncio
async def test_unlimited_batch_has_no_hidden_former_finite_cap(data_services):
    _, project, _, coordinator, worker, core, scheduler = data_services
    batch = start(data_services, None)
    for _ in range(101):
        await scheduler.tick()
        await core.wait_idle()
    current = coordinator.get_batch(project, batch.batch_id)
    assert len(worker.calls) == 101
    assert current.counts.created_task_count == 101
    assert current.claim_gate_state == "open"
    await scheduler.stop(
        project,
        batch.batch_id,
        uid(),
        {
            "expectedStatusRevision": current.status_revision,
            "reason": "完成不限次数边界验证",
        },
    )
    await scheduler.tick()
    assert coordinator.get_batch(project, batch.batch_id).status == "stopped"


@pytest.mark.asyncio
@pytest.mark.parametrize("continue_after_failure", [False, True])
async def test_failure_closes_only_new_claims_unless_explicitly_continued(
    data_services,
    continue_after_failure,
):
    """Fails if a failure keeps claiming by default or disables explicit continue."""
    factory, project, automation, coordinator, worker, core, scheduler = data_services
    with factory.begin() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        row.run_policy = {
            **row.run_policy,
            "continueAfterFailure": continue_after_failure,
        }
    worker.results = ["failed"]
    batch = start(data_services, 3)
    for _ in range(4):
        await scheduler.tick()
        await core.wait_idle()
    tasks = coordinator.list_tasks(project, batch.batch_id)
    assert len(tasks) == (3 if continue_after_failure else 1)
    assert len(worker.calls) == len(tasks)
    assert tasks[0].status == "failed"
    assert all(task.status == "succeeded" for task in tasks[1:])
    with factory() as session:
        assert session.get(ProjectBatchRow, batch.batch_id).claim_gate_state == "closed"


@pytest.mark.asyncio
async def test_busy_batch_is_not_exhausted_and_recovers_after_owner_finishes(
    data_services,
):
    """Fails if active leases reject batch acceptance or become false exhaustion."""
    _, project, _, coordinator, worker, core, scheduler = data_services
    worker.wait = asyncio.Event()
    first = start(data_services)
    await scheduler.tick()
    await asyncio.sleep(0)
    try:
        second = start(data_services)
        await scheduler.tick()
        assert coordinator.get_batch(project, second.batch_id).status == "blocked"
        assert coordinator.list_tasks(project, second.batch_id) == []
    finally:
        worker.wait.set()
        await core.wait_idle()
    for _ in range(3):
        await scheduler.tick()
        await core.wait_idle()
    assert coordinator.get_batch(project, first.batch_id).status == "completed"
    assert coordinator.get_batch(project, second.batch_id).status == "completed"
    assert len(worker.calls) == 2


@pytest.mark.asyncio
async def test_true_no_match_finishes_without_task_facts(data_services):
    """Fails if legitimate exhaustion is reported as a start command rejection."""
    factory, project, automation, coordinator, worker, _, scheduler = data_services
    with factory.begin() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        source, other = row.input_plan["inputs"]
        row.input_plan = {
            "inputs": [
                {
                    **source,
                    "filter": {
                        "type": "compare",
                        "fieldId": source["fieldBindings"][0]["fieldRef"]["fieldId"],
                        "operator": "eq",
                        "value": "never-matches",
                    },
                },
                other,
            ]
        }
    batch = start(data_services)
    await scheduler.tick()
    assert coordinator.get_batch(project, batch.batch_id).status == "completed"
    assert coordinator.list_tasks(project, batch.batch_id) == []
    assert worker.calls == []


@pytest.mark.asyncio
async def test_core_terminal_event_wakes_scheduler_without_fast_polling(data_services):
    """The 30-second reconciliation fallback must not delay normal progression."""
    _, project, _, coordinator, worker, core, scheduler = data_services
    batch = start(data_services)
    await scheduler.startup()
    try:

        async def completed():
            while coordinator.get_batch(project, batch.batch_id).status != "completed":
                await asyncio.sleep(0.01)

        await asyncio.wait_for(completed(), timeout=1)
        assert len(worker.calls) == 1
    finally:
        await scheduler.shutdown()
        await core.wait_idle()


@pytest.mark.asyncio
async def test_effective_concurrency_uses_request_policy_instance_and_core_minimum(
    data_services,
):
    factory, project, automation, coordinator, *_ = data_services
    with factory.begin() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        row.run_policy = {
            **row.run_policy,
            "concurrency": 3,
            "maxLiveInstances": 2,
        }
        for definition in row.input_plan["inputs"]:
            existing = session.scalar(
                select(DataRecordRow).where(
                    DataRecordRow.project_id == project,
                    DataRecordRow.table_id == definition["tableId"],
                )
            )
            session.add(
                DataRecordRow(
                    project_id=existing.project_id,
                    table_id=existing.table_id,
                    dataset_generation=existing.dataset_generation,
                    key_type="uuid",
                    key_value=uid(),
                    values_json=dict(existing.values_json),
                    record_slots=list(existing.record_slots),
                    status_id=existing.status_id,
                    current_environment_id=None,
                    content_revision=1,
                    status_revision=1,
                    link_revision=1,
                    deleted=False,
                    created_at=existing.created_at,
                    updated_at=existing.updated_at,
                )
            )
    batch = coordinator.start(
        project,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 3,
            "concurrency": 3,
        },
    )[0]
    core = CapacityCore(factory, capacity=3)
    scheduler = ProjectBatchScheduler(factory, core, QuiesceGate())
    await scheduler.tick()
    tasks = coordinator.list_tasks(project, batch.batch_id)
    assert len(tasks) == 2
    assert {task.status for task in tasks} == {"running"}
    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 4
        )
    core.finish(tasks[0].run_id, "failed")
    await scheduler.tick()
    current = coordinator.get_batch(project, batch.batch_id)
    assert current.status == "draining"
    assert current.claim_gate_state == "closed"
    assert coordinator.list_tasks(project, batch.batch_id)[1].status == "running"
    core.finish(tasks[1].run_id, "succeeded")
    await scheduler.tick()
    assert coordinator.get_batch(project, batch.batch_id).status == "failed"


@pytest.mark.asyncio
async def test_effective_concurrency_includes_saved_automation_concurrency(
    data_services,
):
    """The saved automation concurrency is one of the four hard limits."""
    factory, project, automation, coordinator, *_ = data_services
    with factory.begin() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        row.run_policy = {
            **row.run_policy,
            "concurrency": 1,
            "maxLiveInstances": 3,
        }
        for definition in row.input_plan["inputs"]:
            existing = session.scalar(
                select(DataRecordRow).where(
                    DataRecordRow.project_id == project,
                    DataRecordRow.table_id == definition["tableId"],
                )
            )
            session.add(
                DataRecordRow(
                    project_id=existing.project_id,
                    table_id=existing.table_id,
                    dataset_generation=existing.dataset_generation,
                    key_type="uuid",
                    key_value=uid(),
                    values_json=dict(existing.values_json),
                    record_slots=list(existing.record_slots),
                    status_id=existing.status_id,
                    current_environment_id=None,
                    content_revision=1,
                    status_revision=1,
                    link_revision=1,
                    deleted=False,
                    created_at=existing.created_at,
                    updated_at=existing.updated_at,
                )
            )
    batch = coordinator.start(
        project,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 3,
            "concurrency": 3,
        },
    )[0]
    core = CapacityCore(factory, capacity=3)
    scheduler = ProjectBatchScheduler(factory, core, QuiesceGate())
    await scheduler.tick()
    tasks = coordinator.list_tasks(project, batch.batch_id)
    assert len(tasks) == 1
    assert tasks[0].status == "running"


@pytest.mark.asyncio
async def test_max_live_instances_and_core_capacity_apply_across_batches(
    data_services,
):
    factory, project, automation, coordinator, *_ = data_services
    with factory.begin() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        row.run_policy = {
            **row.run_policy,
            "concurrency": 3,
            "maxLiveInstances": 2,
        }
        for definition in row.input_plan["inputs"]:
            existing = session.scalar(
                select(DataRecordRow).where(
                    DataRecordRow.project_id == project,
                    DataRecordRow.table_id == definition["tableId"],
                )
            )
            for _ in range(2):
                session.add(
                    DataRecordRow(
                        project_id=existing.project_id,
                        table_id=existing.table_id,
                        dataset_generation=existing.dataset_generation,
                        key_type="uuid",
                        key_value=uid(),
                        values_json=dict(existing.values_json),
                        record_slots=list(existing.record_slots),
                        status_id=existing.status_id,
                        current_environment_id=None,
                        content_revision=1,
                        status_revision=1,
                        link_revision=1,
                        deleted=False,
                        created_at=existing.created_at,
                        updated_at=existing.updated_at,
                    )
                )
    payload = {
        "expectedAutomationRevision": automation.management_revision,
        "parameters": {},
        "maxTasks": 3,
        "concurrency": 3,
    }
    first = coordinator.start(project, automation.automation_id, uid(), payload)[0]
    second = coordinator.start(project, automation.automation_id, uid(), payload)[0]
    core = CapacityCore(factory, capacity=3)
    scheduler = ProjectBatchScheduler(factory, core, QuiesceGate())
    await scheduler.tick()
    assert len(coordinator.list_tasks(project, first.batch_id)) == 2
    assert coordinator.list_tasks(project, second.batch_id) == []
    assert coordinator.get_batch(project, second.batch_id).status == "blocked"


def test_claim_rechecks_project_lifecycle_inside_commit(data_services):
    factory, project, _, coordinator, _, _, _ = data_services
    batch = start(data_services)
    with factory.begin() as session:
        session.get(ProjectRow, project).lifecycle_state = "archived"
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id)
        == "closed"
    )
    assert coordinator.list_tasks(project, batch.batch_id) == []


@pytest.mark.asyncio
async def test_claim_rechecks_confirmed_failure_before_creating_another_task(
    data_services,
):
    factory, project, _, coordinator, worker, core, scheduler = data_services
    worker.results = ["failed"]
    batch = start(data_services, 3)
    await scheduler.tick()
    await core.wait_idle()
    assert coordinator.list_tasks(project, batch.batch_id)[0].status == "failed"
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id)
        == "closed"
    )
    assert len(coordinator.list_tasks(project, batch.batch_id)) == 1


@pytest.mark.asyncio
async def test_active_task_no_match_is_rechecked_after_the_task_finishes(
    data_services,
):
    factory, project, _, coordinator, *_ = data_services
    batch = start(data_services, 2)
    core = CapacityCore(factory, capacity=2)
    scheduler = ProjectBatchScheduler(factory, core, QuiesceGate())
    await scheduler.tick()
    task = coordinator.list_tasks(project, batch.batch_id)[0]
    with factory.begin() as session:
        batch_row = session.get(ProjectBatchRow, batch.batch_id)
        frozen = dict(batch_row.frozen_request)
        frozen["concurrency"] = 2
        frozen_automation = dict(frozen["automation"])
        frozen_automation["runPolicy"] = {
            **frozen_automation["runPolicy"],
            "concurrency": 2,
            "maxLiveInstances": 2,
        }
        frozen["automation"] = frozen_automation
        batch_row.frozen_request = frozen
        rows = list(
            session.scalars(
                select(DataRecordRow).where(DataRecordRow.project_id == project)
            )
        )
        for row in rows:
            row.deleted = True
    assert scheduler._claim_data_task(project, batch.batch_id) == "noMatch"
    assert coordinator.get_batch(project, batch.batch_id).claim_gate_state == "open"
    with factory.begin() as session:
        for row in session.scalars(
            select(DataRecordRow).where(DataRecordRow.project_id == project)
        ):
            row.deleted = False
    core.finish(task.run_id, "succeeded")
    await scheduler.tick()
    assert len(coordinator.list_tasks(project, batch.batch_id)) == 2


@pytest.mark.asyncio
async def test_configuration_failure_drains_active_task_before_terminal_failure(
    data_services,
):
    factory, project, _, coordinator, *_ = data_services
    batch = start(data_services, 2)
    core = CapacityCore(factory, capacity=2)
    scheduler = ProjectBatchScheduler(factory, core, QuiesceGate())
    await scheduler.tick()
    task = coordinator.list_tasks(project, batch.batch_id)[0]
    with factory.begin() as session:
        row = session.get(ProjectBatchRow, batch.batch_id)
        frozen = dict(row.frozen_request)
        frozen["concurrency"] = 2
        automation = dict(frozen["automation"])
        automation["runPolicy"] = {
            **automation["runPolicy"],
            "concurrency": 2,
            "maxLiveInstances": 2,
        }
        input_plan = dict(automation["inputPlan"])
        inputs = [dict(item) for item in input_plan["inputs"]]
        inputs[0]["datasetGeneration"] = uid()
        input_plan["inputs"] = inputs
        automation["inputPlan"] = input_plan
        frozen["automation"] = automation
        row.frozen_request = frozen
    assert scheduler._claim_data_task(project, batch.batch_id) == "configurationError"
    await scheduler.tick()
    current = coordinator.get_batch(project, batch.batch_id)
    assert current.status == "draining"
    assert current.claim_gate_state == "closed"
    assert task.status == "running"
    core.finish(task.run_id, "succeeded")
    await scheduler.tick()
    assert coordinator.get_batch(project, batch.batch_id).status == "failed"
    with factory() as session:
        assert all(
            lease.released_at is not None
            for lease in session.scalars(select(ProjectRecordLeaseRow))
        )


@pytest.mark.asyncio
async def test_stop_acceptance_closes_claim_gate_in_same_transaction(data_services):
    """Fails if stop commits stopping while a competing claimant still sees open."""
    factory, project, _, coordinator, worker, _, scheduler = data_services
    batch = start(data_services)
    await scheduler.stop(
        project,
        batch.batch_id,
        uid(),
        {
            "expectedStatusRevision": batch.status_revision,
            "reason": "stop wins claim race",
        },
    )
    with factory() as session:
        stored = session.get(ProjectBatchRow, batch.batch_id)
        assert stored.status == "stopping"
        assert stored.claim_gate_state == "closed"
    before = len(coordinator.list_tasks(project, batch.batch_id))
    await scheduler.tick()
    assert len(coordinator.list_tasks(project, batch.batch_id)) == before
    assert worker.calls == []


@pytest.mark.asyncio
async def test_claim_and_stop_transactions_linearize_without_post_stop_task(
    data_services,
):
    """Exercise the claim-wins order with real competing SQLite transactions."""
    factory, project, _, coordinator, _, _, scheduler = data_services
    batch = start(data_services, 2)
    entered, release = threading.Event(), threading.Event()
    engine = factory.kw["bind"]

    def pause_task_insert(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("INSERT INTO PROJECT_TASKS"):
            entered.set()
            assert release.wait(timeout=5)

    event.listen(engine, "before_cursor_execute", pause_task_insert)
    try:
        claim = asyncio.create_task(
            asyncio.to_thread(
                ProjectBatchScheduler.claim_data_task,
                factory,
                project,
                batch.batch_id,
            )
        )
        assert await asyncio.to_thread(entered.wait, 5)
        stop = asyncio.create_task(
            asyncio.to_thread(
                scheduler._accept_stop,
                project,
                batch.batch_id,
                uid(),
                {
                    "expectedStatusRevision": batch.status_revision,
                    "reason": "claim wins, then stop closes the gate",
                },
            )
        )
        await asyncio.sleep(0.05)
        release.set()
        assert await claim == "ready"
        await stop
    finally:
        event.remove(engine, "before_cursor_execute", pause_task_insert)
        release.set()
    assert len(coordinator.list_tasks(project, batch.batch_id)) == 1
    assert coordinator.get_batch(project, batch.batch_id).claim_gate_state == "closed"
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id)
        == "closed"
    )


@pytest.mark.asyncio
async def test_authoritative_terminal_releases_data_leases(data_services):
    """Fails if successful core completion leaves rows permanently busy."""
    factory, project, _, coordinator, _, core, scheduler = data_services
    batch = start(data_services)
    await scheduler.tick()
    await core.wait_idle()
    await scheduler.tick()
    assert coordinator.get_batch(project, batch.batch_id).status == "completed"
    with factory() as session:
        leases = list(session.scalars(select(ProjectRecordLeaseRow)))
        assert len(leases) == 2
        assert all(lease.state == "released" for lease in leases)
        assert all(lease.released_at is not None for lease in leases)
        assert all(
            row.status_id is None for row in session.scalars(select(DataRecordRow))
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_known", [False, True])
async def test_restart_retains_unknown_leases_until_core_confirms_cleanup(
    data_services,
    cleanup_known,
):
    """Fails if restart releases an unknown owner, or retains a reconciled owner."""
    factory, project, automation, coordinator, _, core, scheduler = data_services
    batch = start(data_services)
    # Advance only to materialize a lazy task; block the synthetic worker if used.
    worker = data_services[4]
    worker.wait = asyncio.Event()
    await scheduler.tick()
    await asyncio.sleep(0)
    task = coordinator.list_tasks(project, batch.batch_id)[0]

    async def recover(_run):
        if not cleanup_known:
            raise RuntimeError("ownership remains unknown")

    new_core = WorkflowRunDispatcher(
        factory,
        Worker(),
        SyntheticResources(),
        QuiesceGate(),
        recover,
    )
    new_scheduler = ProjectBatchScheduler(factory, new_core, QuiesceGate())
    try:
        await new_core.startup()
        await new_scheduler.tick()
        current = new_core.query_run(task.run_id)
        assert current.status == ("interrupted" if cleanup_known else "reconciling")
        with factory() as session:
            leases = list(session.scalars(select(ProjectRecordLeaseRow)))
            assert len(leases) == 2
            assert all(
                (lease.released_at is not None) == cleanup_known for lease in leases
            )
        preview = coordinator.preview_inputs(
            project, automation.automation_id, automation.management_revision
        )
        assert preview["selectionStatus"] == (
            "ready" if cleanup_known else "temporarilyBusy"
        )
    finally:
        worker.wait.set()
        await core.wait_idle()


@pytest.mark.asyncio
async def test_old_generation_completion_cannot_release_unknown_lease(data_services):
    """Fails if late pre-fence completion frees rows still owned by an unknown run."""
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError

    factory, project, _, coordinator, worker, core, scheduler = data_services
    worker.wait = asyncio.Event()
    batch = start(data_services)
    await scheduler.tick()
    await asyncio.sleep(0)
    task = coordinator.list_tasks(project, batch.batch_id)[0]
    old = core.query_run(task.run_id)
    fenced = core._transition_identity(
        task.run_id, "reconciling", old.status_revision, old.execution_generation
    )
    try:
        with pytest.raises(WorkflowRuntimeError) as error:
            core._transition_identity(
                task.run_id,
                "interrupted",
                fenced.status_revision,
                old.execution_generation,
            )
        assert error.value.code == "EXECUTION_GENERATION_REVOKED"
        await scheduler.tick()
        assert core.query_run(task.run_id).status == "reconciling"
        with factory() as session:
            leases = list(session.scalars(select(ProjectRecordLeaseRow)))
            assert len(leases) == 2
            assert all(lease.released_at is None for lease in leases)
    finally:
        worker.wait.set()
        await core.wait_idle()


@pytest.mark.asyncio
async def test_identical_ids_in_two_workspaces_do_not_share_stop_or_claim_gate(
    data_services, tmp_path
):
    """Fails if a scheduler writes by logical ID outside its own workspace factory."""
    from shutil import copy2

    from autoflow.infrastructure.database.session import create_session_factory

    factory, project, _, _, _, _, scheduler = data_services
    batch = start(data_services)
    other_path = tmp_path / "other-workspace.sqlite3"
    copy2(factory.kw["bind"].url.database, other_path)
    other = create_session_factory(other_path)
    try:
        await scheduler.stop(
            project,
            batch.batch_id,
            uid(),
            {
                "expectedStatusRevision": batch.status_revision,
                "reason": "only workspace A",
            },
        )
        await scheduler.tick()
        with other() as session:
            row = session.get(ProjectBatchRow, batch.batch_id)
            assert row.status == "accepted"
            assert row.claim_gate_state == "open"
            assert all(
                lease.released_at is None
                for lease in session.scalars(select(ProjectRecordLeaseRow))
            )
    finally:
        other.dispose()


def test_deferred_environment_resolution_failure_creates_no_task_or_lease(data_services):
    factory, project, _, _, _, _, scheduler = data_services
    batch = start(data_services)
    with factory() as session:
        row = session.get(ProjectBatchRow, batch.batch_id)
        row.frozen_request = {**row.frozen_request, "resourceRequest": {"environmentResolution": "atTaskStart"}}
        session.commit()
    assert scheduler._claim_data_task(project, batch.batch_id) == "configurationError"
    with factory() as session:
        row = session.get(ProjectBatchRow, batch.batch_id)
        assert row.claim_gate_state == "closed"
        assert row.selection_outcome["errorCode"] == "RESOURCE_UNAVAILABLE"
        for model in (ProjectTaskRow, WorkflowRunRow, ProjectTaskInputSnapshotRow, ProjectRecordLeaseRow):
            assert session.scalar(select(func.count()).select_from(model)) == 0
