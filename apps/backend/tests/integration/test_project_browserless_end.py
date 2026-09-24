"""Combined PM9 End capability and Studio browser-free worker regression."""
import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from autoflow.application.project_runs.worker_capabilities import (
    ProjectWorkerCapabilities,
)
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.project_runs.worker_commands import project_command_id
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunRow,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from tests.integration.test_project_capability_fencing import (
    capability_context as capability_context,  # noqa: PLC0414 -- exported pytest fixture
)


def _plan(retain):
    nodes = [
        {"id": "value", "data": {"moduleType": "set_variable", "variableName": "answer", "variableValue": "accepted"}},
        {"id": "end", "data": {"moduleType": "project_end", "retainEnvironment": retain}},
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


@pytest.mark.asyncio
async def test_browserless_end_uses_real_worker_and_authorized_capability(capability_context, tmp_path):
    factory, _project, task, *_rest = capability_context
    plan = _prepare(factory, task, {"enabled": False})
    capabilities = ProjectWorkerCapabilities(factory)
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
        assert result.status == "succeeded" and result.cleanup_confirmed
        assert not manager.busy()
        assert len(requests) == 1
        assert requests[0]["browserClosed"] is True
        assert requests[0]["arguments"] == {"retainEnvironment": {"enabled": False}}
        assert [event["nodeId"] for event in events if event["kind"] == "nodeAttempt" and event["payload"]["status"] == "succeeded"] == ["value", "end"]
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["retention", "recordTargets", "browserStillOpen", "wrongNode", "revokedGeneration", "missingEnvironment"])
async def test_browserless_end_cannot_bypass_retention_or_authorization(capability_context, invalid):
    factory, _project, task, *_rest = capability_context
    retain = {"enabled": False}
    if invalid == "retention":
        retain = {"enabled": True, "mode": "saveAs", "name": "must not publish"}
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
               "arguments": {"retainEnvironment": retain}}
    if invalid == "revokedGeneration":
        with factory.begin() as session:
            session.get(WorkflowRunRow, task.run_id).execution_generation = 2
    with pytest.raises(ProjectError) as caught:
        await ProjectWorkerCapabilities(factory).handle(task.run_id, 1, request)
    assert caught.value.code == "CAPABILITY_SCOPE_DENIED"


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
        document["content"].update(_plan({"enabled": True, "mode": "saveAs", "name": "retained"})["document"])
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
        assert rejected.value.details["capabilities"] == ["browser.cloakbrowser"]
    finally:
        factory.dispose()
