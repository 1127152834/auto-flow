"""Production End admission uses the real Task, frozen visit and SQLite ledger."""

from copy import deepcopy
from uuid import NAMESPACE_URL, uuid5

import pytest

from autoflow.application.environments.service import EnvironmentService
from autoflow.application.project_runs.end import ProjectRunEnd
from autoflow.application.projects.service import ProjectService
from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunRow,
)
from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore
from tests.integration.test_project_worker_capabilities import (  # noqa: F401
    commit_visit,
    worker_context,
)


@pytest.fixture
def end_context(worker_context, tmp_path):  # noqa: F811 - pytest fixture injection
    factory, _data, task, request, snapshot = worker_context
    request = {
        **request,
        "capability": "project.end",
        "arguments": {"recordTargets": []},
        "commandId": str(
            uuid5(
                NAMESPACE_URL,
                f"autoflow:project-end:{request['nodeVisitId']}:{request['nodeId']}",
            )
        ),
    }
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        content = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        plan = deepcopy(content.execution_plan)
        plan["document"]["nodes"] = [
            {
                "id": request["nodeId"],
                "data": {
                    "moduleType": "project_end",
                    "config": {"retainEnvironment": False},
                },
            }
        ]
        content.execution_plan = plan
    env = EnvironmentService(
        ProjectService(SqlAlchemyProjects(factory)),
        SqlAlchemyEnvironments(factory),
        EnvironmentStore(tmp_path / "environments"),
    )
    commit_visit(factory, task, request)
    return factory, ProjectRunEnd(factory, env), task, request, snapshot


def test_end_is_durable_and_finalizes_without_browser(end_context):
    factory, ends, task, request, _snapshot = end_context
    accepted = ends.worker_call(task.run_id, 1, request)
    assert ends.worker_call(task.run_id, 1, request) == accepted
    with factory() as session:
        assert session.get(WorkflowRunRow, task.run_id).status == "finishing"
    outcome = ends.finalize(task.run_id)
    assert outcome[0] == "succeeded" and outcome[1]["complete"] is True
    assert ends.finalize(task.run_id) == outcome


def _retain(end_context):
    factory, ends, task, _request, _snapshot = end_context
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        content = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        plan = deepcopy(content.execution_plan)
        plan["document"]["nodes"][0]["data"]["config"] = {
            "retainEnvironment": True,
            "name": "End regression",
        }
        content.execution_plan = plan
    from uuid import uuid4

    instance = ends.environments.reserve(
        task.project_id,
        ends.environments.resolve(
            task.project_id, {"source": "newFromProfile", "profileId": str(uuid4())}
        ),
        task_id=task.task_id,
        run_id=task.run_id,
        holder_kind="task",
        holder_id=task.task_id,
    )
    ends.environments.environments.set_instance_state(instance.instance_id, "active")
    ends.environments._closer = lambda _service, _instance: None
    (
        ends.environments.instance_path(instance.instance_id) / "end-evidence"
    ).write_bytes(b"closed browser fixture")
    return instance


def test_end_saves_and_associates_once_and_queries_durable_result(end_context):
    from autoflow.application.project_runs.queries import ProjectRunQueries

    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    accepted = ends.worker_call(task.run_id, 1, request)
    result = ends.finalize(task.run_id)
    assert result[1]["complete"] and result[1]["saved"]["contentGeneration"] == 1
    assert ends.finalize(task.run_id) == result
    visible = ProjectRunQueries(factory).task_detail(task.project_id, task.task_id)[
        "end"
    ]
    assert visible["operationId"] == accepted["endOperationId"]
    assert visible["outcome"]["saved"] == result[1]["saved"]


def test_end_association_conflict_preserves_saved_environment(end_context):
    from autoflow.infrastructure.database.project_data_models import DataRecordRow

    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    ends.worker_call(task.run_id, 1, request)
    targets = ends.operation(task.run_id)[1]["retainEnvironment"]["recordTargets"]
    assert targets
    ref = targets[0]["recordRef"]
    with factory.begin() as session:
        row = session.get(
            DataRecordRow,
            (
                ref["datasetGeneration"],
                ref["recordKey"]["type"],
                ref["recordKey"]["value"],
            ),
        )
        row.link_revision += 1
    outcome = ends.finalize(task.run_id)[1]
    assert outcome["phase"] == "saved_unlinked" and not outcome["complete"]
    assert outcome["error"]["code"] == "LINK_REVISION_CONFLICT"
    assert outcome["error"]["message"] and outcome["error"]["details"]
    assert ends.environments.store.generation_dir(
        outcome["saved"]["environmentId"], 1
    ).is_dir()
    assert ends.finalize(task.run_id)[1] == outcome


@pytest.mark.parametrize("change", ["generation", "visit", "scope", "query_only"])
def test_end_denies_unowned_or_uncommitted_requests(end_context, change):
    from autoflow.domain.projects.models import ProjectError

    factory, ends, task, request, snapshot = end_context
    _retain(end_context)
    generation = 1
    if change == "generation":
        generation = 2
    elif change == "visit":
        request["nodeVisitId"] = "another-visit"
        request["commandId"] = str(
            uuid5(
                NAMESPACE_URL,
                f"autoflow:project-end:{request['nodeVisitId']}:{request['nodeId']}",
            )
        )
    else:
        from autoflow.domain.workflows.runtime import thaw_json

        _end_config(factory, task, recordTargets="{selected_records}")
        ref = thaw_json(snapshot.inputs[0]["recordRef"])
        if change == "scope":
            ref["projectId"] = "another-project"
        else:
            from sqlalchemy import select

            from autoflow.infrastructure.database.project_run_models import (
                ProjectRecordLeaseRow,
            )

            with factory.begin() as session:
                for row in session.scalars(
                    select(ProjectRecordLeaseRow).where(
                        ProjectRecordLeaseRow.record_ref == ref
                    )
                ):
                    row.state = "released"
        request["arguments"]["recordTargets"] = [ref]
    with pytest.raises(ProjectError):
        ends.worker_call(task.run_id, generation, request)
    assert ends.operation(task.run_id) is None


def test_end_fences_final_publication_when_generation_changes_during_io(
    end_context, monkeypatch
):
    from autoflow.domain.projects.models import ProjectError

    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    ends.worker_call(task.run_id, 1, request)
    original = ends.environments.store.stage_candidate

    def revoke(*args):
        digest = original(*args)
        with factory.begin() as session:
            session.get(WorkflowRunRow, task.run_id).execution_generation += 1
        return digest

    monkeypatch.setattr(ends.environments.store, "stage_candidate", revoke)
    with pytest.raises(ProjectError, match="控制权"):
        ends.finalize(task.run_id)
    assert ends.environments.environments.list(task.project_id)[1] == 0


def test_competing_end_and_lost_receipt_share_one_durable_winner(end_context):
    from concurrent.futures import ThreadPoolExecutor

    from autoflow.domain.projects.models import ProjectError

    _factory, ends, task, request, _snapshot = end_context
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: ends.worker_call(task.run_id, 1, request), range(2))
        )
    assert results[0] == results[1]
    changed = deepcopy(request)
    changed["arguments"]["recordTargets"] = [{"unexpected": True}]
    with pytest.raises(ProjectError, match="另一结束意图"):
        ends.worker_call(task.run_id, 1, changed)


@pytest.mark.asyncio
async def test_restart_recovers_committed_end_without_replaying_and_never_resurrects(
    end_context,
):
    from autoflow.application.settings.runtime import QuiesceGate
    from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
    from tests.fixtures.workflow_runs import SyntheticResources
    from tests.integration.test_workflow_dispatch import SyntheticWorker

    factory, ends, task, request, _snapshot = end_context
    ends.worker_call(task.run_id, 1, request)
    ends.finalize(task.run_id)  # response/terminal commit lost

    async def recover(_run):
        pass

    dispatcher = WorkflowRunDispatcher(
        factory,
        SyntheticWorker(),
        SyntheticResources(),
        QuiesceGate(),
        recover,
        project_end=ends,
    )
    await dispatcher.startup()
    assert dispatcher.query_run(task.run_id).status == "succeeded"
    revision = dispatcher.query_run(task.run_id).status_revision
    await dispatcher.startup()
    assert dispatcher.query_run(task.run_id).status_revision == revision
    await dispatcher.shutdown()


@pytest.mark.asyncio
async def test_production_worker_reaches_end_and_skips_downstream_node(tmp_path):
    from autoflow.application.project_data.capabilities import (
        ProjectDataCapabilityService,
    )
    from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
    from autoflow.application.settings.runtime import QuiesceGate
    from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.infrastructure.database.project_capabilities import (
        SqlAlchemyProjectDataCapabilities,
    )
    from autoflow.infrastructure.database.workflow_runtime import (
        SqlAlchemyWorkflowRuntimeRepository,
    )
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
    from autoflow.infrastructure.process.project_workflow_worker import (
        ProjectWorkflowWorkerManager,
    )
    from tests.integration.test_project_data_worker import _NoBrowserResources
    from tests.integration.test_project_run_data_start import _setup, uid
    from tests.integration.test_project_worker_capabilities import save_data_workflow

    factory, project, automation, coordinator = _setup(tmp_path)
    save_data_workflow(factory, automation)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    document = documents.get(automation.workflow_id).to_payload()
    document["nodes"].extend(
        [
            {
                "id": "end",
                "type": "project_end",
                "position": {"x": 900, "y": 0},
                "data": {
                    "moduleType": "project_end",
                    "config": {"retainEnvironment": False},
                },
            },
            {
                "id": "never",
                "type": "set_variable",
                "position": {"x": 1000, "y": 0},
                "data": {
                    "moduleType": "set_variable",
                    "variableName": "must_not_run",
                    "variableValue": "bad",
                },
            },
        ]
    )
    document["edges"].extend(
        [
            {"id": "to-end", "source": "update-node", "target": "end"},
            {"id": "after-end", "source": "end", "target": "never"},
        ]
    )
    documents.update(
        automation.workflow_id, document, expected_revision=2, client_request_id=uid()
    )
    batch = coordinator.start(
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
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id)
        == "ready"
    )
    task = coordinator.list_tasks(project, batch.batch_id)[0]
    env = EnvironmentService(
        ProjectService(SqlAlchemyProjects(factory)),
        SqlAlchemyEnvironments(factory),
        EnvironmentStore(tmp_path / "environments"),
    )
    ends = ProjectRunEnd(factory, env)
    worker = ProjectWorkflowWorkerManager(
        tmp_path / "worker",
        project_data=ProjectDataCapabilityService(
            SqlAlchemyProjectDataCapabilities(factory), project_end=ends
        ),
    )

    async def recover(_run):
        pass

    dispatcher = WorkflowRunDispatcher(
        factory, worker, _NoBrowserResources(), QuiesceGate(), recover, project_end=ends
    )
    try:
        run = dispatcher.query_run(task.run_id)
        await dispatcher.dispatch(
            run.run_id,
            expected_status_revision=run.status_revision,
            execution_generation=run.execution_generation,
        )
        await dispatcher.wait_idle()
        with factory() as session:
            events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(
                task.run_id, after_sequence=0, limit=100
            )
        assert dispatcher.query_run(task.run_id).status == "succeeded", [
            (e.kind, e.payload) for e in events
        ]
        assert ends.operation(task.run_id)[0].result["complete"] is True
        assert not any(e.node_id == "never" for e in events)
        assert not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_saving_holds_control_and_lease_until_cancelled_thread_is_drained(
    end_context, monkeypatch
):
    import asyncio
    from threading import Event

    from autoflow.application.settings.runtime import QuiesceGate
    from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
    from tests.fixtures.workflow_runs import SyntheticResources
    from tests.integration.test_workflow_dispatch import SyntheticWorker

    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    ends.worker_call(task.run_id, 1, request)
    entered, release = Event(), Event()
    original = ends.environments.store.stage_candidate

    def blocked(*args):
        entered.set()
        assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(ends.environments.store, "stage_candidate", blocked)

    async def recover(_run):
        pass

    resources = SyntheticResources()
    dispatcher = WorkflowRunDispatcher(
        factory, SyntheticWorker(), resources, QuiesceGate(), recover, project_end=ends
    )
    dispatcher._lease = resources.lease
    finalizing = asyncio.create_task(dispatcher._finish_end(task.run_id))
    assert await asyncio.to_thread(entered.wait, 5)
    current = dispatcher.query_run(task.run_id)
    cancelling = asyncio.create_task(
        dispatcher.cancel(
            task.run_id,
            expected_status_revision=current.status_revision,
            execution_generation=1,
        )
    )
    try:
        await asyncio.sleep(0.03)
        assert not cancelling.done() and not resources.lease.released
        finalizing.cancel()
        await asyncio.sleep(0.03)
        assert not finalizing.done() and not resources.lease.released
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await finalizing
    assert (await cancelling).status == "finishing"
    assert ends.operation(task.run_id)[0].result["complete"]
    await dispatcher._finish_end(task.run_id)
    assert dispatcher.query_run(task.run_id).status == "succeeded"
    await dispatcher.shutdown()


def test_restart_finds_published_save_without_receipt_and_does_not_reapply_links(
    end_context, monkeypatch
):
    from autoflow.domain.projects.models import ProjectError

    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    ends.worker_call(task.run_id, 1, request)

    def crash(*_args, **_kwargs):
        raise OSError("simulated crash after publication before association")

    monkeypatch.setattr(ends.environments.environments, "bind_records", crash)
    with pytest.raises(OSError):
        ends.finalize(task.run_id)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.status = "reconciling"
        run.execution_generation += 1
    result = ends.recover(task.run_id)
    assert result[1]["phase"] == "saved_unlinked" and result[1]["saved"]
    with pytest.raises(ProjectError):
        ends.worker_call(task.run_id, 1, request)


def _end_config(factory, task, **changes):
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        content = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        plan = deepcopy(content.execution_plan)
        plan["document"]["nodes"][0]["data"]["config"].update(changes)
        content.execution_plan = plan


@pytest.mark.parametrize(
    "change", ["static_targets", "generation_bool", "attempt_bool", "blank_name"]
)
def test_end_rejects_unfrozen_targets_and_invalid_scalar_types(end_context, change):
    from autoflow.domain.projects.models import ProjectError
    from autoflow.domain.workflows.runtime import thaw_json

    factory, ends, task, request, snapshot = end_context
    _retain(end_context)
    generation = True if change == "generation_bool" else 1
    if change == "attempt_bool":
        request["attempt"] = True
    elif change == "static_targets":
        request["arguments"]["recordTargets"] = [
            thaw_json(snapshot.inputs[0]["recordRef"])
        ]
    elif change == "blank_name":
        _end_config(factory, task, name="   ")
    with pytest.raises(ProjectError):
        ends.worker_call(task.run_id, generation, request)
    assert ends.operation(task.run_id) is None


@pytest.mark.parametrize("damage", ["missing", "same_size"])
def test_restart_does_not_confirm_damaged_published_bytes(
    end_context, monkeypatch, damage
):
    import shutil

    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    ends.worker_call(task.run_id, 1, request)

    def crash(*_args, **_kwargs):
        raise OSError("lost association receipt")

    monkeypatch.setattr(ends.environments.environments, "bind_records", crash)
    with pytest.raises(OSError):
        ends.finalize(task.run_id)
    saved = ends.environments.environments.list(task.project_id)[0][0]
    directory = ends.environments.store.generation_dir(saved.ref.environment_id, 1)
    if damage == "missing":
        shutil.rmtree(directory)
    else:
        evidence = directory / "end-evidence"
        evidence.write_bytes(b"x" * evidence.stat().st_size)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.status = "reconciling"
        run.execution_generation += 1
    outcome = ends.recover(task.run_id)[1]
    assert not outcome["complete"] and outcome["phase"] == "failed"
    assert outcome["error"]["code"] == "ENVIRONMENT_INTEGRITY_FAILED"
    assert outcome["saved"]["environmentId"] == saved.ref.environment_id


@pytest.mark.parametrize("result", ["succeeded", "failed"])
def test_end_excludes_inputs_and_accepts_explicit_leased_output(end_context, result):
    from autoflow.domain.workflows.runtime import thaw_json

    factory, ends, task, request, snapshot = end_context
    _retain(end_context)
    _end_config(
        factory,
        task,
        inputIds=[],
        recordTargets="{written_records}",
        businessResult=result,
    )
    ref = thaw_json(snapshot.inputs[0]["recordRef"])
    request["arguments"]["recordTargets"] = [ref]
    ends.worker_call(task.run_id, 1, request)
    assert ends.operation(task.run_id)[1]["retainEnvironment"]["recordTargets"] == [
        {"recordRef": ref, "expectedLinkRevision": 1, "replaceAllowed": False}
    ]
    business, outcome, _error = ends.finalize(task.run_id)
    assert business == result and outcome["complete"]
    assert outcome["targets"] == [ref]


def test_end_can_explicitly_save_without_linking_any_inputs(end_context):
    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    _end_config(factory, task, inputIds=[])
    ends.worker_call(task.run_id, 1, request)
    assert ends.finalize(task.run_id)[1]["targets"] == []


@pytest.mark.asyncio
async def test_end_executor_resolves_list_variable():
    from autoflow.application.workflows.executors.project_end import ProjectEndExecutor
    from autoflow.domain.workflows.execution import ExecutionContext

    calls = []

    async def worker(request):
        calls.append(request)
        return {"phase": "accepted"}

    context = ExecutionContext(
        variables={"written_records": [{"recordKey": "selected"}]}, project_data=worker
    )
    context.proxy_visit.set(("end", "visit"))
    result = await ProjectEndExecutor().execute(
        {"recordTargets": "{written_records}"}, context
    )
    assert result.success and context.project_end.accepted
    assert calls[0]["arguments"]["recordTargets"] == [{"recordKey": "selected"}]


@pytest.mark.parametrize(
    "failure",
    [
        "ASSOCIATION_TARGET_MISSING",
        "ASSOCIATION_REPLACE_FORBIDDEN",
        "END_ACCESS_REVOKED",
    ],
)
def test_association_failure_preserves_saved_reference_and_full_error(
    end_context, monkeypatch, failure
):
    from autoflow.domain.projects.models import ProjectError

    _factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    ends.worker_call(task.run_id, 1, request)

    def reject(*_args, **_kwargs):
        raise ProjectError(
            failure, "precise association failure", 409, {"target": "original"}
        )

    monkeypatch.setattr(ends.environments.environments, "bind_records", reject)
    outcome = ends.finalize(task.run_id)[1]
    assert outcome["phase"] == "saved_unlinked" and outcome["saved"]
    assert outcome["error"] == {
        "code": failure,
        "message": "precise association failure",
        "status": 409,
        "details": {"target": "original"},
    }
    assert ends.operation(task.run_id)[0].error == outcome["error"]


@pytest.mark.asyncio
async def test_cancel_before_end_revokes_admission_without_creating_save(end_context):
    from autoflow.domain.projects.models import ProjectError
    from tests.fixtures.workflow_runs import SyntheticResources
    from tests.integration.test_workflow_dispatch import (
        SyntheticWorker,
        make_dispatcher,
    )

    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    dispatcher = make_dispatcher(
        factory, SyntheticWorker(), SyntheticResources(), project_end=ends
    )
    current = dispatcher.query_run(task.run_id)
    await dispatcher.cancel(
        task.run_id,
        expected_status_revision=current.status_revision,
        execution_generation=1,
    )
    with pytest.raises(ProjectError, match="失效"):
        ends.worker_call(task.run_id, 1, request)
    assert ends.operation(task.run_id) is None
    assert ends.environments.environments.list(task.project_id)[1] == 0
    await dispatcher.shutdown()


@pytest.mark.asyncio
async def test_cancel_after_end_requires_current_control_identity(end_context):
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError
    from tests.fixtures.workflow_runs import SyntheticResources
    from tests.integration.test_workflow_dispatch import (
        SyntheticWorker,
        make_dispatcher,
    )

    factory, ends, task, request, _snapshot = end_context
    ends.worker_call(task.run_id, 1, request)
    dispatcher = make_dispatcher(
        factory, SyntheticWorker(), SyntheticResources(), project_end=ends
    )
    run = dispatcher.query_run(task.run_id)
    for revision, generation in [
        (run.status_revision - 1, 1),
        (run.status_revision, 2),
    ]:
        with pytest.raises(WorkflowRuntimeError):
            await dispatcher.cancel(
                task.run_id,
                expected_status_revision=revision,
                execution_generation=generation,
            )
    assert (
        await dispatcher.cancel(
            task.run_id,
            expected_status_revision=run.status_revision,
            execution_generation=1,
        )
    ).status == "finishing"
    await dispatcher.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown", [True, False])
async def test_forced_reconciliation_never_publishes_and_holds_unknown_lease(
    end_context, unknown
):
    from tests.fixtures.workflow_runs import SyntheticResources
    from tests.integration.test_workflow_dispatch import (
        SyntheticWorker,
        make_dispatcher,
    )

    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    ends.worker_call(task.run_id, 1, request)

    async def recover(_run):
        if unknown:
            raise RuntimeError("browser close ownership unknown")

    resources = SyntheticResources()
    dispatcher = make_dispatcher(
        factory,
        SyntheticWorker(cleanup_fail=unknown),
        resources,
        recovery=recover,
        project_end=ends,
    )
    dispatcher._run_id, dispatcher._lease = task.run_id, resources.lease
    run = dispatcher._transition(dispatcher.query_run(task.run_id), "reconciling")
    result = await dispatcher.force_stop(
        task.run_id,
        expected_status_revision=run.status_revision,
        execution_generation=run.execution_generation,
    )
    assert ends.environments.environments.list(task.project_id)[1] == 0
    if unknown:
        assert result.status == "reconciling" and not resources.lease.released
        assert ends.operation(task.run_id)[0].result is None
    else:
        assert result.status == "failed" and resources.lease.released
        assert ends.operation(task.run_id)[0].result["complete"] is False
    unknown = False
    dispatcher._worker.cleanup_fail = False
    await dispatcher.shutdown()


def test_created_record_acquires_lease_and_can_be_selected_by_dynamic_end(end_context):
    from uuid import uuid4

    from autoflow.domain.project_data.capabilities import CreateProjectRecordCommand
    from autoflow.domain.workflows.runtime import thaw_json
    from autoflow.infrastructure.database.project_capabilities import (
        SqlAlchemyProjectDataCapabilities,
    )

    factory, ends, task, request, snapshot = end_context
    _retain(end_context)
    _end_config(factory, task, inputIds=[], recordTargets="{created_records}")
    item = thaw_json(snapshot.inputs[0])
    ref = item["recordRef"]
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        bindings = deepcopy(run.capability_bindings)
        binding = next(b for b in bindings if b["capability"] == "project.data")
        binding["createRecordTargets"] = [
            {"tableId": ref["tableId"], "datasetGeneration": ref["datasetGeneration"]}
        ]
        for grant in binding["tableGrants"]:
            if grant["tableId"] == ref["tableId"]:
                grant["operations"].append("createRecord")
        run.capability_bindings = bindings
    repository = SqlAlchemyProjectDataCapabilities(factory)
    created, _replayed = repository.create_record(
        repository.scope(task.project_id, task.task_id, task.run_id),
        CreateProjectRecordCommand(
            str(uuid4()),
            1,
            task.project_id,
            ref["tableId"],
            ref["datasetGeneration"],
            {v["fieldId"]: "new-end-output" for v in item["values"]},
        ),
    )
    request["arguments"]["recordTargets"] = [created["ref"]]
    ends.worker_call(task.run_id, 1, request)
    outcome = ends.finalize(task.run_id)[1]
    assert outcome["complete"] and outcome["targets"] == [created["ref"]]


def test_reopened_partial_end_repairs_all_targets_without_reviving_run(end_context):
    from uuid import uuid4

    from autoflow.application.project_runs.queries import ProjectRunQueries
    from autoflow.infrastructure.database.project_data_models import DataRecordRow

    factory, ends, task, request, _snapshot = end_context
    _retain(end_context)
    ends.worker_call(task.run_id, 1, request)
    original_targets = ends.operation(task.run_id)[1]["retainEnvironment"]["recordTargets"]
    ref = original_targets[0]["recordRef"]
    with factory.begin() as session:
        record = session.get(DataRecordRow, (ref["datasetGeneration"], ref["recordKey"]["type"], ref["recordKey"]["value"]))
        record.link_revision += 1
    outcome = ends.finalize(task.run_id)[1]
    assert outcome["phase"] == "saved_unlinked"
    # Dispatcher terminal bookkeeping is independent of association repair.
    with factory.begin() as session:
        session.get(WorkflowRunRow, task.run_id).status = "failed"
    reopened = ProjectRunQueries(factory).task_detail(task.project_id, task.task_id)["end"]
    assert reopened["saveOperationId"] != reopened["operationId"]
    assert reopened["associationPhase"] == "saved_unlinked"
    assert len(reopened["repairTargets"]) == len(original_targets)
    approved = [{"recordRef": target["recordRef"], "expectedLinkRevision": target["currentLinkRevision"], "replaceAllowed": True} for target in reopened["repairTargets"]]
    # A fresh service uses SQLite facts; no previous End mutation state is used.
    service = EnvironmentService(ProjectService(SqlAlchemyProjects(factory)), SqlAlchemyEnvironments(factory), ends.environments.store)
    repaired, _, _ = service.repair(task.project_id, str(uuid4()), reopened["saveOperationId"], {"recordTargets": approved})
    assert repaired["phase"] == "completed"
    detail = ProjectRunQueries(factory).task_detail(task.project_id, task.task_id)
    assert detail["end"]["associationPhase"] == "completed"
    assert detail["end"]["phase"] == "saved_unlinked"
    assert detail["run"]["status"] == "failed"
    assert all(target["currentEnvironmentId"] == outcome["saved"]["environmentId"] for target in detail["end"]["repairTargets"])
