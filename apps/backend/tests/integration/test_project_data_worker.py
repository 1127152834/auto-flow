"""Project-task integration contract for browser-free advanced-data workflows.

This suite uses the existing project runtime, dispatcher and real worker process.
It intentionally supplies no Profile or CloakBrowser executable: pure-data work
must keep the same durable event/stop contract without acquiring browser state.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn
from uuid import uuid4

import pytest

from autoflow.application.project_automations.resource_query import (
    ProjectAutomationResourceQuery,
)
from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.service import WorkflowService
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflows import (
    SqlAlchemyWorkflowDocuments,
    SqlAlchemyWorkflowRepository,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_project_run_start import setup, start_payload

NOW = datetime(2026, 9, 23, tzinfo=UTC)


def _pure_data_document(
    workflow_id: str | None = None, *, values: list[int] | None = None
) -> dict[str, Any]:
    document = workflow_payload(workflow_id) if workflow_id else workflow_payload()
    document["content"]["name"] = "无浏览器高级数据任务"
    document["content"]["nodes"] = [
        {
            "id": "reverse",
            "type": "list_reverse",
            "position": {"x": 100, "y": 80},
            "data": {
                "label": "列表反转",
                "moduleType": "list_reverse",
                "listVariable": "items",
                "resultVariable": "out",
            },
        }
    ]
    document["content"]["edges"] = []
    document["content"]["variables"] = [
        {
            "name": "items",
            "value": values if values is not None else [1, 2, 3],
            "type": "array",
            "scope": "global",
            "builtin": False,
        }
    ]
    return document


class _UnexpectedBrowserDependency:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"纯数据验证不应读取浏览器依赖: {name}")


def _studio_payload(workflow_id: str) -> dict[str, Any]:
    document = _pure_data_document(workflow_id)
    return {**document["content"], "id": workflow_id}


def test_pure_data_project_saves_and_validates_without_profile(tmp_path: Path) -> None:
    factory, _, _, coordinator, runtime, project, automation = setup(tmp_path)
    try:
        documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
        saved = documents.update(
            automation.workflow_id,
            _studio_payload(automation.workflow_id),
            expected_revision=1,
            client_request_id=str(uuid4()),
        )
        unexpected: Any = _UnexpectedBrowserDependency()
        resources = ProjectAutomationResourceQuery(
            SqlAlchemyProjects(factory),
            unexpected,  # type: ignore[arg-type]
            unexpected,  # type: ignore[arg-type]
            unexpected,  # type: ignore[arg-type]
            unexpected,  # type: ignore[arg-type]
            workflow_runtime=runtime,
        )
        service = ProjectAutomationService(
            SqlAlchemyProjects(factory),
            SqlAlchemyProjectAutomations(factory),
            workflow_service=WorkflowService(SqlAlchemyWorkflowRepository(factory)),
            resource_query=resources,
            capability_query=coordinator,
        )

        validation = service.validation(project.project_id, automation.automation_id)

        assert saved.revision == 2
        assert validation.status == "ready"
        assert validation.runnable and validation.valid
        assert validation.issues == []
        browser = next(
            item
            for item in validation.capability_requirements
            if item["capability"] == "browser.cloakbrowser"
        )
        assert browser["required"] is False
        from sqlalchemy import select

        from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
        from autoflow.application.project_runs.resources import (
            ProjectRunResourceResolver,
        )
        from autoflow.infrastructure.database.environment_models import (
            ProjectEnvironmentInstanceRow,
        )

        runner = ProjectRunCoordinator(
            factory, runtime,
            resolve_resources=ProjectRunResourceResolver(resources, unexpected),
            available_capabilities=[], environments=unexpected,
        )
        key = str(uuid4())
        batch, operation, replayed = runner.start(
            project.project_id, automation.automation_id, key, start_payload(automation)
        )
        assert not replayed and operation.status == "succeeded"
        repeated, _, replayed = runner.start(
            project.project_id, automation.automation_id, key, start_payload(automation)
        )
        assert replayed and repeated.batch_id == batch.batch_id
        with factory() as session:
            assert session.scalars(select(ProjectEnvironmentInstanceRow)).all() == []
    finally:
        factory.dispose()


def test_pure_data_prepare_content_has_no_browser_requirement(tmp_path: Path) -> None:
    factory, _, _, _, runtime, _, automation = setup(tmp_path)
    try:
        saved = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
            automation.workflow_id,
            _studio_payload(automation.workflow_id),
            expected_revision=1,
            client_request_id=str(uuid4()),
        )

        prepared = runtime.prepare_content(
            prepare_operation_id=str(uuid4()),
            workflow_id=saved.id,
            source_revision=saved.revision,
            available_capabilities=[],
        )

        assert prepared.capability_requirements == ()
        assert prepared.execution_plan["orderedNodeIds"] == ("reverse",)
    finally:
        factory.dispose()


class _NoBrowserResources:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    async def acquire(
        self, request: Mapping[str, Any], run_request_id: str
    ) -> NoReturn:
        self.requests.append(deepcopy(dict(request)))
        raise AssertionError("纯数据任务不应取得浏览器 lease")


def _queued_pure_data_run(
    tmp_path: Path,
    *,
    values: list[int] | None = None,
    node_data: dict[str, Any] | None = None,
    variables: dict[str, Any] | None = None,
) -> tuple[Any, Any]:
    database = tmp_path / "project-data-worker.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    workflow_id = str(uuid4())
    document = _pure_data_document(workflow_id, values=values)
    if node_data is not None:
        document["content"]["nodes"] = [
            {
                "id": "advanced-data",
                "type": node_data["moduleType"],
                "position": {"x": 100, "y": 80},
                "data": deepcopy(node_data),
            }
        ]
        document["content"]["variables"] = [
            {
                "name": name,
                "value": deepcopy(value),
                "type": (
                    "null"
                    if value is None
                    else "boolean"
                    if isinstance(value, bool)
                    else "number"
                    if isinstance(value, (int, float))
                    else "array"
                    if isinstance(value, list)
                    else "object"
                    if isinstance(value, dict)
                    else "string"
                ),
                "scope": "global",
                "builtin": False,
            }
            for name, value in (variables or {}).items()
        ]
    node = document["content"]["nodes"][0]
    execution_plan = {
        "orderedNodeIds": [node["id"]],
        "nodes": [
            {
                "nodeId": node["id"],
                "moduleType": node["data"]["moduleType"],
                "data": deepcopy(node["data"]),
            }
        ],
    }
    with factory() as session:
        session.add(
            WorkflowDocumentRow(
                id=workflow_id,
                name="无浏览器高级数据任务",
                document=document,
                layout={},
                revision=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.flush()
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        prepared = repository.prepare_content(
            prepared_content_id=str(uuid4()),
            prepare_operation_id=str(uuid4()),
            request_digest="a" * 64,
            workflow_id=workflow_id,
            source_revision=1,
            checksum="b" * 64,
            document=document,
            execution_plan=execution_plan,
            adapter_version="webrpa-chain/v1",
            capability_requirements=[],
            provenance={"kind": "test"},
            created_at=NOW,
        )
        run = repository.prepare_run(
            run_id=str(uuid4()),
            run_request_id=str(uuid4()),
            request_digest="c" * 64,
            prepared_content_id=prepared.prepared_content_id,
            parameters={},
            input_snapshot_ref=None,
            resource_request={
                "browser": "none",
                "automaticExecutionTimeoutSeconds": 30,
            },
            capability_bindings=[],
            created_at=NOW,
        )
        session.commit()
    return factory, run


def _dispatcher(
    factory: Any,
    worker: ProjectWorkflowWorkerManager,
    resources: _NoBrowserResources,
) -> WorkflowRunDispatcher:
    async def recover(_run: object) -> None:
        return None

    return WorkflowRunDispatcher(
        factory,
        worker,
        resources,
        QuiesceGate(),
        recover,
    )


@pytest.mark.asyncio
async def test_real_worker_runs_without_cloak_and_persists_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    factory, queued = _queued_pure_data_run(tmp_path, values=[1, 2, 3])
    worker = ProjectWorkflowWorkerManager(tmp_path / "worker-temp", start_timeout=10)
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, worker, resources)
    try:
        await dispatcher.dispatch(
            queued.run_id,
            expected_status_revision=queued.status_revision,
            execution_generation=queued.execution_generation,
        )
        await dispatcher.wait_idle()

        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=queued.run_id)
            events = repository.list_events(
                queued.run_id, after_sequence=0, limit=100
            )
        outputs = [event for event in events if event.kind == "output"]
        assert finished is not None and finished.status == "succeeded"
        assert len(outputs) == 1
        assert outputs[0].payload["name"] == "out"
        assert tuple(outputs[0].payload["value"]) == (3, 2, 1)
        assert resources.requests == []
        assert not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_real_worker_persists_present_json_null_output_without_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    factory, queued = _queued_pure_data_run(
        tmp_path,
        node_data={
            "label": "字典路径取值",
            "moduleType": "dict_get_path",
            "dictVariable": "payload",
            "path": "present",
            "defaultValue": "fallback",
            "resultVariable": "out",
        },
        variables={"payload": {"present": None}},
    )
    worker = ProjectWorkflowWorkerManager(tmp_path / "worker-temp", start_timeout=10)
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, worker, resources)
    try:
        await dispatcher.dispatch(
            queued.run_id,
            expected_status_revision=queued.status_revision,
            execution_generation=queued.execution_generation,
        )
        await dispatcher.wait_idle()

        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=queued.run_id)
            events = repository.list_events(
                queued.run_id, after_sequence=0, limit=100
            )
        outputs = [event for event in events if event.kind == "output"]
        assert finished is not None and finished.status == "succeeded"
        assert len(outputs) == 1
        assert outputs[0].payload["name"] == "out"
        assert outputs[0].payload["value"] is None
        assert resources.requests == []
        assert not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


async def _wait_for_started(factory: Any, run_id: str) -> None:
    async with asyncio.timeout(10):
        while True:
            with factory() as session:
                events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(
                    run_id, after_sequence=0, limit=100
                )
            if any(
                event.kind == "nodeAttempt"
                and event.payload.get("status") == "started"
                for event in events
            ):
                return
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_stop_cancels_browser_free_worker_and_confirms_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    factory, queued = _queued_pure_data_run(
        tmp_path, values=list(range(100_000))
    )
    worker_root = tmp_path / "worker-temp"
    worker = ProjectWorkflowWorkerManager(worker_root, start_timeout=10)
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, worker, resources)
    try:
        running = await dispatcher.dispatch(
            queued.run_id,
            expected_status_revision=queued.status_revision,
            execution_generation=queued.execution_generation,
        )
        await _wait_for_started(factory, queued.run_id)
        await dispatcher.cancel(
            running.run_id,
            expected_status_revision=running.status_revision,
            execution_generation=running.execution_generation,
        )
        await dispatcher.wait_idle()

        with factory() as session:
            finished = SqlAlchemyWorkflowRuntimeRepository(session).get_run(
                run_id=queued.run_id
            )
        assert finished is not None and finished.status == "cancelled"
        assert resources.requests == []
        assert not worker.busy()
        assert not (
            worker_root / "workflow-runs" / queued.run_id / "generation-1"
        ).exists()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_bootstrap_recovers_pure_data_run_without_installed_kernel(tmp_path: Path) -> None:
    from fastapi import FastAPI

    from autoflow.application.workflows.core_runtime import WorkflowRuntimeService
    from autoflow.bootstrap.workflows import configure_project_workflow_runtime

    factory, queued = _queued_pure_data_run(tmp_path, values=[1, 2, 3])
    runtime = WorkflowRuntimeService(factory)
    runtime.dispatch_run(
        queued.run_id,
        expected_status_revision=queued.status_revision,
        execution_generation=queued.execution_generation,
    )
    temporary = tmp_path / "temp"
    owned = temporary / "workflow-runs" / queued.run_id / "generation-1"
    owned.mkdir(parents=True)
    unexpected: Any = _UnexpectedBrowserDependency()

    def no_kernel_lookup():
        raise AssertionError("纯数据恢复不能要求安装浏览器内核")

    app = FastAPI()
    dispatcher = configure_project_workflow_runtime(
        app, session_factory=factory, profiles=unexpected,
        installed=no_kernel_lookup, resolve_proxy=unexpected, read_license=unexpected,
        usage_guard=unexpected, installations=unexpected, temp_dir=temporary,
        gate=QuiesceGate(),
    )
    try:
        await dispatcher.startup()
        run = runtime.query_run(run_id=queued.run_id)
        assert run is not None and run.status == "interrupted"
        assert not owned.exists()
        assert not app.state.project_workflow_worker_manager.busy()
        await dispatcher.startup()
        assert runtime.query_run(run_id=queued.run_id) == run
    finally:
        await dispatcher.shutdown()
        factory.dispose()
