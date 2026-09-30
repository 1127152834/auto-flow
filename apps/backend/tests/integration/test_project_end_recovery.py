"""Durable Project End restart and cleanup regressions."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from autoflow.application.environments.service import EnvironmentService
from autoflow.application.project_runs.end import ProjectRunEnd
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.project_runs.worker_capabilities import (
    ProjectWorkerCapabilities,
)
from autoflow.application.projects.service import ProjectService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.project_runs.worker_commands import project_command_id
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
from tests.fixtures.workflow_runs import SyntheticResources
from tests.integration.test_project_capability_fencing import (
    capability_context as capability_context,  # noqa: PLC0414 -- pytest fixture
)
from tests.integration.test_workflow_dispatch import SyntheticWorker, make_dispatcher


def _environments(factory, root):
    return EnvironmentService(
        ProjectService(SqlAlchemyProjects(factory)),
        SqlAlchemyEnvironments(factory),
        EnvironmentStore(root),
        closer=lambda _service, _instance: None,
    )


async def _accept_end(factory, environments, task, *, retain_environment):
    data = {
        "moduleType": "project_end",
        "retainEnvironment": retain_environment,
        "name": "restart recovery",
    }
    plan = {
        "document": {
            "nodes": [
                {
                    "id": "end",
                    "type": "project_end",
                    "position": {"x": 0, "y": 0},
                    "data": data,
                }
            ],
            "edges": [],
        },
        "nodes": [{"nodeId": "end", "moduleType": "project_end", "data": data}],
        "orderedNodeIds": ["end"],
    }
    visit = uuid4().hex
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        prepared.execution_plan = plan
        SqlAlchemyWorkflowRuntimeRepository(session).append_event(
            {
                "eventId": uuid4().hex,
                "runId": task.run_id,
                "executionGeneration": 1,
                "kind": "nodeAttempt",
                "nodeId": "end",
                "nodeVisitId": visit,
                "attempt": 1,
                "occurredAt": datetime.now(UTC).isoformat(),
                "payload": {"status": "started"},
            }
        )
    capabilities = ProjectWorkerCapabilities(factory, environments)
    await capabilities.handle(
        task.run_id,
        1,
        {
            "commandId": project_command_id(task.run_id, 1, visit),
            "nodeId": "end",
            "nodeVisitId": visit,
            "attempt": 1,
            "operation": "end",
            "browserClosed": True,
            "arguments": {"recordTargets": []},
        },
    )
    return capabilities.project_end


@pytest.mark.asyncio
async def test_interrupted_retained_end_survives_startup_and_batch_cleanup(
    capability_context, tmp_path
):
    factory, project_id, task, *_rest = capability_context
    root = tmp_path / "end-recovery-environments"
    environments = _environments(factory, root)
    instance = environments.reserve(
        project_id,
        environments.resolve(
            project_id, {"source": "newFromProfile", "profileId": str(uuid4())}
        ),
        task_id=task.task_id,
        run_id=task.run_id,
        holder_kind="task",
        holder_id=task.task_id,
    )
    evidence = environments.instance_path(instance.instance_id) / "retained.txt"
    evidence.write_text("must survive interrupted End", encoding="utf-8")
    await _accept_end(factory, environments, task, retain_environment=True)

    restarted = _environments(factory, root)
    dispatcher = make_dispatcher(
        factory,
        SyntheticWorker(),
        SyntheticResources(),
        project_end=ProjectRunEnd(factory, restarted),
    )
    try:
        await dispatcher.startup()
        recovered = dispatcher.query_run(task.run_id)
        assert recovered.status == "failed"
        assert recovered.error["code"] == "END_INTERRUPTED"

        await ProjectBatchScheduler(
            factory, dispatcher, QuiesceGate(), restarted
        ).tick()

        assert evidence.read_text(encoding="utf-8") == "must survive interrupted End"
        assert (
            restarted.environments.get_instance(project_id, instance.instance_id).state
            != "cleaned"
        )
    finally:
        await dispatcher.shutdown()


@pytest.mark.asyncio
async def test_startup_commits_completed_end_once(capability_context, tmp_path):
    factory, _project_id, task, *_rest = capability_context
    root = tmp_path / "completed-end-environments"
    project_end = await _accept_end(
        factory, _environments(factory, root), task, retain_environment=False
    )
    business, outcome, error = project_end.finalize(task.run_id)
    assert business == "succeeded"
    assert outcome["complete"] is True
    assert error is None

    dispatcher = make_dispatcher(
        factory,
        SyntheticWorker(),
        SyntheticResources(),
        project_end=ProjectRunEnd(factory, _environments(factory, root)),
    )
    try:
        await dispatcher.startup()
        recovered = dispatcher.query_run(task.run_id)
        assert recovered.status == "succeeded"
        revision = recovered.status_revision

        await dispatcher.startup()

        assert dispatcher.query_run(task.run_id).status_revision == revision
    finally:
        await dispatcher.shutdown()
