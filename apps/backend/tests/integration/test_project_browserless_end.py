"""Combined PM9 End capability and Studio browser-free worker regression."""
import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from autoflow.application.environments.service import EnvironmentService
from autoflow.application.project_runs.worker_capabilities import (
    ProjectWorkerCapabilities,
)
from autoflow.application.projects.service import ProjectService
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.project_runs.worker_commands import project_command_id
from autoflow.domain.projects.models import ProjectError
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
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from tests.integration.test_project_capability_fencing import (
    capability_context as capability_context,  # noqa: PLC0414 -- exported pytest fixture
)


def _plan(retain, **end_config):
    nodes = [
        {"id": "value", "data": {"moduleType": "set_variable", "variableName": "answer", "variableValue": "accepted"}},
        {"id": "end", "data": {"moduleType": "project_end", "retainEnvironment": retain, **end_config}},
    ]
    for index, node in enumerate(nodes):
        node.update(type=node["data"]["moduleType"], position={"x": 0, "y": index * 100})
    return {"document": {"nodes": nodes, "edges": [{"id": "next", "source": "value", "target": "end"}]},
            "nodes": [{"nodeId": node["id"], "moduleType": node["data"]["moduleType"], "data": node["data"]} for node in nodes],
            "orderedNodeIds": ["value", "end"]}


def _prepare(factory, task, retain, *, browser="none"):
    plan = _plan(retain)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.resource_request = {"browser": browser}
        prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        prepared.execution_plan = plan
    return plan


def _environments(factory, tmp_path):
    return EnvironmentService(
        ProjectService(SqlAlchemyProjects(factory)),
        SqlAlchemyEnvironments(factory),
        EnvironmentStore(tmp_path / "environments"),
    )


@pytest.mark.asyncio
async def test_browserless_end_uses_real_worker_and_authorized_capability(capability_context, tmp_path):
    factory, _project, task, *_rest = capability_context
    plan = _prepare(factory, task, False)
    capabilities = ProjectWorkerCapabilities(factory, _environments(factory, tmp_path))
    requests = []
    events = []

    async def persist(event):
        with factory.begin() as session:
            SqlAlchemyWorkflowRuntimeRepository(session).append_event(event)
        events.append(event)

    async def authorize(run_id, generation, request):
        requests.append(request)
        return await capabilities.handle(run_id, generation, request)

    manager = ProjectWorkflowWorkerManager(tmp_path / "worker", on_capability=authorize)
    try:
        result = await asyncio.wait_for(manager.run(
            run_id=task.run_id, execution_generation=1, execution_plan=plan,
            parameters={}, variables={}, browser={}, executable=None, on_event=persist,
        ), 15)
        assert result.status == "succeeded" and result.cleanup_confirmed, (
            result,
            requests,
            events,
        )
        assert not manager.busy()
        assert len(requests) == 1
        assert requests[0]["browserClosed"] is True
        assert requests[0]["arguments"] == {"recordTargets": []}
        assert capabilities.project_end.operation(task.run_id)[0].result is None
        with factory() as session:
            assert session.get(WorkflowRunRow, task.run_id).status == "finishing"
        assert [event["nodeId"] for event in events if event["kind"] == "nodeAttempt" and event["payload"]["status"] == "succeeded"] == ["value", "end"]
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["retention", "recordTargets", "browserStillOpen", "wrongNode", "revokedGeneration", "missingEnvironment"])
async def test_browserless_end_cannot_bypass_retention_or_authorization(capability_context, tmp_path, invalid):
    factory, _project, task, *_rest = capability_context
    retain = {"enabled": False}
    if invalid == "retention":
        retain = {"enabled": True, "mode": "saveAs", "name": "must not publish"}
    if invalid == "missingEnvironment":
        retain = {"enabled": True, "mode": "saveAs", "name": "must exist"}
    if invalid == "recordTargets":
        retain["recordTargets"] = [{"recordRef": {}}]
    _prepare(factory, task, retain, browser="temporary" if invalid == "missingEnvironment" else "none")
    visit = uuid4().hex
    with factory.begin() as session:
        SqlAlchemyWorkflowRuntimeRepository(session).append_event({
            "eventId": uuid4().hex, "runId": task.run_id, "executionGeneration": 1,
            "kind": "nodeAttempt", "nodeId": "end", "nodeVisitId": visit, "attempt": 1,
            "occurredAt": datetime.now(UTC).isoformat(), "payload": {"status": "started"},
        })
    request = {"commandId": project_command_id(task.run_id, 1, visit), "nodeId": "value" if invalid == "wrongNode" else "end",
               "nodeVisitId": visit, "attempt": 1, "operation": "end", "browserClosed": invalid != "browserStillOpen",
               "arguments": {"recordTargets": retain.get("recordTargets", [])}}
    if invalid == "revokedGeneration":
        with factory.begin() as session:
            session.get(WorkflowRunRow, task.run_id).execution_generation = 2
    with pytest.raises(ProjectError) as caught:
        await ProjectWorkerCapabilities(factory, _environments(factory, tmp_path)).handle(task.run_id, 1, request)
    assert caught.value.code == (
        "ENVIRONMENT_UNAVAILABLE"
        if invalid in {"retention", "missingEnvironment"}
        else "CAPABILITY_SCOPE_DENIED"
    )


@pytest.mark.asyncio
async def test_end_accept_replay_and_finalize_use_one_durable_operation(capability_context, tmp_path):
    factory, _project, task, *_rest = capability_context
    _prepare(factory, task, False)
    capabilities = ProjectWorkerCapabilities(factory, _environments(factory, tmp_path))
    visit = uuid4().hex
    with factory.begin() as session:
        SqlAlchemyWorkflowRuntimeRepository(session).append_event({
            "eventId": uuid4().hex, "runId": task.run_id, "executionGeneration": 1,
            "kind": "nodeAttempt", "nodeId": "end", "nodeVisitId": visit, "attempt": 1,
            "occurredAt": datetime.now(UTC).isoformat(), "payload": {"status": "started"},
        })
    request = {
        "commandId": project_command_id(task.run_id, 1, visit),
        "nodeId": "end", "nodeVisitId": visit, "attempt": 1,
        "operation": "end", "browserClosed": True,
        "arguments": {"recordTargets": []},
    }

    accepted = await capabilities.handle(task.run_id, 1, request)
    assert accepted["phase"] == "accepted"
    assert await capabilities.handle(task.run_id, 1, request) == accepted
    with factory() as session:
        assert session.get(WorkflowRunRow, task.run_id).status == "finishing"
    business, outcome, error = capabilities.project_end.finalize(task.run_id)
    assert (business, outcome["phase"], outcome["complete"], error) == (
        "succeeded", "completed", True, None,
    )
    assert capabilities.project_end.finalize(task.run_id) == (business, outcome, error)


@pytest.mark.asyncio
async def test_end_host_derives_targets_and_rejects_read_only_input(capability_context, tmp_path):
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from autoflow.infrastructure.database.project_run_models import (
        ProjectTaskInputSnapshotRow,
    )

    factory, _project, task, *_rest = capability_context
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        snapshot = session.scalar(
            select(ProjectTaskInputSnapshotRow).where(
                ProjectTaskInputSnapshotRow.task_id == task.task_id
            )
        )
        input_id = snapshot.inputs[0]["inputId"]
        prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        prepared.execution_plan = _plan(
            True, inputIds=[input_id], replaceAllowed=True
        )
        for binding in run.capability_bindings:
            if binding.get("capability") == "project.data":
                binding["statusInputIds"] = []
                binding["tableGrants"] = []
        flag_modified(run, "capability_bindings")
    visit = uuid4().hex
    with factory.begin() as session:
        SqlAlchemyWorkflowRuntimeRepository(session).append_event({
            "eventId": uuid4().hex, "runId": task.run_id, "executionGeneration": 1,
            "kind": "nodeAttempt", "nodeId": "end", "nodeVisitId": visit, "attempt": 1,
            "occurredAt": datetime.now(UTC).isoformat(), "payload": {"status": "started"},
        })
    request = {
        "commandId": project_command_id(task.run_id, 1, visit),
        "nodeId": "end", "nodeVisitId": visit, "attempt": 1,
        "operation": "end", "browserClosed": True,
        "arguments": {"recordTargets": []},
    }

    with pytest.raises(ProjectError) as denied:
        await ProjectWorkerCapabilities(
            factory, _environments(factory, tmp_path)
        ).handle(task.run_id, 1, request)
    assert denied.value.code == "CAPABILITY_SCOPE_DENIED"


@pytest.mark.parametrize("nested_config", [False, True])
@pytest.mark.parametrize("kind,config,expected", [
    ("project_end", {"retainEnvironment": {"enabled": False}}, False),
    ("project_end", {"retainEnvironment": {"enabled": True, "mode": "saveAs"}}, True),
    ("project_manual", {"reason": "prepare page"}, True),
])
def test_project_environment_requirements_use_shared_runtime(kind, config, expected, nested_config):
    data = {"moduleType": kind, **({"config": config} if nested_config else config)}
    runtime = WorkflowRuntime(build_production_executor_registry())
    assert runtime.requires_browser({"nodes": [{"id": "end", "data": data}]}) is expected


def test_retained_end_requires_browser_before_dispatch(tmp_path):
    from autoflow.application.workflows.core_runtime import WorkflowRuntimeService
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError
    from autoflow.infrastructure.database.workflows import (
        SqlAlchemyWorkflowDocuments,
        SqlAlchemyWorkflowRepository,
    )
    from tests.fixtures.workflows import workflow_payload
    from tests.integration.test_project_run_start import setup

    factory, _, _, _, _, _, automation = setup(tmp_path)
    try:
        document = workflow_payload(automation.workflow_id)
        document["content"].update(
            _plan(True, saveMode="save_as", name="retained")["document"]
        )
        saved = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
            automation.workflow_id, {**document["content"], "id": automation.workflow_id},
            expected_revision=1, client_request_id=str(uuid4()),
        )
        runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
        assert runtime.requires_browser(automation.workflow_id)
        with pytest.raises(WorkflowRuntimeError) as rejected:
            runtime.prepare_content(
                prepare_operation_id=str(uuid4()), workflow_id=automation.workflow_id,
                source_revision=saved.revision, available_capabilities=[],
            )
        assert rejected.value.code == "CAPABILITY_MISSING"
        assert rejected.value.details["capabilities"] == [
            "browser.cloakbrowser",
            "project.data",
        ]
    finally:
        factory.dispose()
