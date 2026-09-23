"""Project-task integration contract for browser-free advanced-data workflows.

This suite uses the existing project runtime, dispatcher and real worker process.
It intentionally supplies no Profile or CloakBrowser executable: pure-data work
must keep the same durable event/stop contract without acquiring browser state.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from types import SimpleNamespace
from typing import Any, NoReturn
from uuid import uuid4

import pytest

from autoflow.application.models.service import ModelExecutionBinding
from autoflow.application.project_automations.resource_query import (
    ProjectAutomationResourceQuery,
)
from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.project_runs.evidence import ProjectRunEvidence
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.core_runtime import WorkflowRuntimeService
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.models.models import ProviderConnection
from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.database.models import ProjectRow
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
    model_provider_id: str | None = None,
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
                **({"modelProviderId": model_provider_id} if model_provider_id else {}),
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
    *,
    resolve_model: Any = None,
    resolve_default_model: Any = None,
) -> WorkflowRunDispatcher:
    async def recover(_run: object) -> None:
        return None

    return WorkflowRunDispatcher(
        factory,
        worker,
        resources,
        QuiesceGate(),
        recover,
        resolve_model=resolve_model,
        resolve_default_model=resolve_default_model,
    )


@pytest.mark.asyncio
async def test_project_ai_task_uses_project_default_or_explicit_model_without_persisting_secret(
    tmp_path: Path,
) -> None:
    requests: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            requests.append({"body": body, "authorization": self.headers.get("authorization")})
            payload = json.dumps({"choices": [{"message": {"content": "模型响应"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for selected in (None, "explicit-model"):
            root = tmp_path / (selected or "project-default")
            root.mkdir()
            factory, queued = _queued_pure_data_run(
                root,
                node_data={
                    "moduleType": "ai_summarize",
                    "inputText": "项目任务原文",
                    "maxWords": 30,
                    "variableName": "summary",
                    **({"modelId": selected} if selected else {}),
                },
                model_provider_id="project-provider",
            )
            worker = ProjectWorkflowWorkerManager(root / "worker-temp", start_timeout=10)
            resources = _NoBrowserResources()
            resolved: list[str] = []

            def resolve(model_id: str, recorded: list[str] = resolved) -> ModelExecutionBinding:
                recorded.append(model_id)
                return ModelExecutionBinding(
                    model_id,
                    model_id,
                    ProviderConnection("custom-openai-compatible", "openai-compatible", f"http://127.0.0.1:{server.server_port}/v1"),
                    "private-model-secret",
                )

            dispatcher = _dispatcher(
                factory, worker, resources,
                resolve_model=resolve,
                resolve_default_model=lambda provider_id: "default-model" if provider_id == "project-provider" else "wrong-provider",
            )
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
                    events = repository.list_events(queued.run_id, after_sequence=0, limit=100)
                assert finished is not None and finished.status == "succeeded"
                assert resolved == [selected or "default-model"]
                assert any(event.kind == "output" for event in events)
                assert not resources.requests
                assert "private-model-secret" not in (root / "project-data-worker.sqlite3").read_bytes().decode("utf-8", errors="ignore")
            finally:
                await dispatcher.shutdown()
                factory.dispose()
        assert [request["body"]["model"] for request in requests] == ["default-model", "explicit-model"]
        assert all(request["authorization"] == "Bearer private-model-secret" for request in requests)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_id", "expected_code"),
    [(None, "PROJECT_DEFAULT_MODEL_MISSING"), (42, "MODEL_ID_INVALID")],
)
async def test_project_ai_task_invalid_model_fails_before_worker_start(
    tmp_path: Path,
    model_id: object,
    expected_code: str,
) -> None:
    factory, queued = _queued_pure_data_run(
        tmp_path,
        node_data={"moduleType": "ai_summarize", "inputText": "原文", "variableName": "summary", **({"modelId": model_id} if model_id is not None else {})},
    )
    worker = ProjectWorkflowWorkerManager(tmp_path / "worker-temp", start_timeout=10)
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        await dispatcher.dispatch(
            queued.run_id,
            expected_status_revision=queued.status_revision,
            execution_generation=queued.execution_generation,
        )
        await dispatcher.wait_idle()
        with factory() as session:
            finished = SqlAlchemyWorkflowRuntimeRepository(session).get_run(run_id=queued.run_id)
        assert finished is not None and finished.status == "failed"
        assert finished.error is not None and finished.error["code"] == expected_code
        assert not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.parametrize(
    ("model_id", "requires_default"),
    [(None, True), ("explicit-model", False), (42, False)],
)
def test_project_runtime_detects_only_missing_ai_model(
    tmp_path: Path, model_id: object, requires_default: bool
) -> None:
    factory, queued = _queued_pure_data_run(
        tmp_path,
        node_data={"moduleType": "ai_summarize", "inputText": "原文", **({"modelId": model_id} if model_id is not None else {})},
    )
    try:
        with factory() as session:
            content = SqlAlchemyWorkflowRuntimeRepository(session).get_prepared_content(
                prepared_content_id=queued.prepared_content_id
            )
        assert content is not None
        assert WorkflowRuntimeService(factory).requires_default_model(content.workflow_id) is requires_default
    finally:
        factory.dispose()


def test_project_task_start_freezes_model_provider_without_browser(
    tmp_path: Path,
) -> None:
    from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
    from autoflow.application.project_runs.resources import ProjectRunResourceResolver

    factory, _, _, _, runtime, project, automation = setup(tmp_path)
    try:
        document = _pure_data_document(automation.workflow_id)
        document["content"]["nodes"] = [{
            "id": "summary", "type": "ai_summarize", "position": {"x": 100, "y": 80},
            "data": {"moduleType": "ai_summarize", "inputText": "项目任务原文", "variableName": "summary"},
        }]
        WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
            automation.workflow_id,
            {**document["content"], "id": automation.workflow_id},
            expected_revision=1,
            client_request_id=str(uuid4()),
        )
        with factory() as session:
            row = session.get(ProjectRow, project.project_id)
            assert row is not None
            row.default_resources = {**row.default_resources, "modelProviderId": "project-provider"}
            session.commit()

        class Models:
            def get_provider(self, provider_id: str) -> Any:
                assert provider_id == "project-provider"
                return SimpleNamespace(enabled=True)

        unused: Any = _UnexpectedBrowserDependency()
        query = ProjectAutomationResourceQuery(
            SqlAlchemyProjects(factory), unused, unused, unused, Models(),
            workflow_runtime=runtime,
        )
        runner = ProjectRunCoordinator(
            factory, runtime,
            resolve_resources=ProjectRunResourceResolver(query, unused),
            available_capabilities=[],
        )
        batch, _, replayed = runner.start(
            project.project_id, automation.automation_id, str(uuid4()), start_payload(automation)
        )
        task = runner.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        assert not replayed and run is not None
        assert run.resource_request["browser"] == "none"
        assert run.resource_request["modelProviderId"] == "project-provider"
        prepared = runtime.query_prepared_content(prepared_content_id=run.prepared_content_id)
        assert prepared is not None and prepared.capability_requirements == ()
        assert prepared.execution_plan["nodes"][0]["moduleType"] == "ai_summarize"
    finally:
        factory.dispose()


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
async def test_project_task_uses_studio_http_gateway_in_real_worker(tmp_path: Path) -> None:
    requests: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            requests.append({"path": self.path, "body": body})
            payload = json.dumps({"accepted": body["value"]}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    factory, queued = _queued_pure_data_run(
        tmp_path,
        node_data={
            "moduleType": "api_request",
            "requestUrl": f"http://127.0.0.1:{server.server_port}/project",
            "requestMethod": "POST",
            "requestBody": '{"value":"项目真实请求"}',
            "variableName": "api_result",
        },
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
            events = repository.list_events(queued.run_id, after_sequence=0, limit=100)
        assert finished is not None and finished.status == "succeeded"
        assert requests == [{"path": "/project", "body": {"value": "项目真实请求"}}]
        assert any(
            event.kind == "output"
            and event.payload.get("name") == "api_result"
            and event.payload["value"]["response"] == {"accepted": "项目真实请求"}
            for event in events
        )
        assert not resources.requests and not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_project_task_stops_in_flight_external_request(tmp_path: Path) -> None:
    entered, release = Event(), Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            entered.set()
            release.wait(5)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    factory, queued = _queued_pure_data_run(
        tmp_path,
        node_data={
            "moduleType": "api_request",
            "requestUrl": f"http://127.0.0.1:{server.server_port}/slow",
            "requestMethod": "POST",
            "requestBody": '{"value":"must not complete"}',
            "requestTimeout": 30,
            "variableName": "api_result",
        },
    )
    worker = ProjectWorkflowWorkerManager(tmp_path / "worker-temp", start_timeout=10)
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        running = await dispatcher.dispatch(
            queued.run_id,
            expected_status_revision=queued.status_revision,
            execution_generation=queued.execution_generation,
        )
        assert await asyncio.to_thread(entered.wait, 15)
        started = monotonic()
        await dispatcher.cancel(
            queued.run_id,
            expected_status_revision=running.status_revision,
            execution_generation=running.execution_generation,
        )
        await dispatcher.wait_idle()
        assert monotonic() - started < 3
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=queued.run_id)
            events = repository.list_events(queued.run_id, after_sequence=0, limit=100)
        assert finished is not None and finished.status == "cancelled"
        assert not any(event.kind == "output" for event in events)
        assert not worker.busy()
    finally:
        release.set()
        await dispatcher.shutdown()
        factory.dispose()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_project_batch_freezes_and_executes_custom_module(tmp_path: Path) -> None:
    from autoflow.application.workflows.modules import CustomModuleService
    from autoflow.infrastructure.database.workflow_modules import (
        SqlAlchemyWorkflowModules,
    )

    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    modules = CustomModuleService(SqlAlchemyWorkflowModules(factory))
    worker = ProjectWorkflowWorkerManager(tmp_path / "module-worker", start_timeout=10)
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        module = modules.create(
            {
                "name": "project_result",
                "display_name": "项目结果模块",
                "parameters": [],
                "outputs": [{"name": "answer"}],
                "workflow": {
                    "nodes": [{"id": "module-inner", "type": "set_variable", "data": {
                        "moduleType": "set_variable",
                        "config": {"variableName": "answer", "variableValue": "42"},
                    }}],
                    "edges": [], "variables": [],
                },
            },
            client_request_id=str(uuid4()),
        )
        wrapper = modules.create(
            {
                "name": "project_wrapper",
                "display_name": "项目模块包装",
                "parameters": [],
                "outputs": [{"name": "answer"}],
                "workflow": {
                    "nodes": [{"id": "module-nested-call", "type": "custom_module", "data": {
                        "moduleType": "custom_module", "config": {"customModuleId": module.id},
                    }}],
                    "edges": [], "variables": [],
                },
            },
            client_request_id=str(uuid4()),
        )
        document = workflow_payload(automation.workflow_id)
        document["content"].update(
            schemaVersion=3,
            nodes=[
                {"id": "module-call", "type": "custom_module", "position": {"x": 100, "y": 80}, "data": {
                    "moduleType": "custom_module", "config": {"customModuleId": wrapper.id},
                }},
                {"id": "root-output", "type": "set_variable", "position": {"x": 250, "y": 80}, "data": {
                    "moduleType": "set_variable", "config": {
                        "variableName": "result", "variableValue": "{answer}",
                    },
                }},
            ],
            edges=[{"id": "after-module", "source": "module-call", "target": "root-output"}],
        )
        WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
            automation.workflow_id,
            {**document["content"], "id": automation.workflow_id},
            expected_revision=1,
            client_request_id=str(uuid4()),
        )
        runtime = WorkflowRuntimeService(
            factory, SqlAlchemyWorkflowRepository(factory), modules=modules
        )
        coordinator._core = runtime
        batch, _, _ = coordinator.start(
            project.project_id, automation.automation_id, str(uuid4()),
            start_payload(automation),
        )
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        assert run is not None
        prepared = runtime.query_prepared_content(prepared_content_id=run.prepared_content_id)
        assert prepared is not None
        frozen = prepared.execution_plan["customModuleDependencies"][module.id]
        assert frozen["workflow"]["nodes"][0]["id"] == "module-inner"
        assert prepared.execution_plan["customModuleDependencies"][wrapper.id]["workflow"]["nodes"][0]["id"] == "module-nested-call"
        modules.update(module.id, {"display_name": "保存后修改"}, expected_revision=1, client_request_id=str(uuid4()))
        await dispatcher.dispatch(
            run.run_id,
            expected_status_revision=run.status_revision,
            execution_generation=run.execution_generation,
        )
        await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=run.run_id)
            events = repository.list_events(run.run_id, after_sequence=0, limit=100)
        assert finished is not None and finished.status == "succeeded", [
            (event.kind, event.node_id, dict(event.payload)) for event in events
        ]
        assert any(event.node_id == "module-inner" and event.kind == "nodeAttempt" for event in events)
        assert any(event.node_id == "module-nested-call" and event.kind == "nodeAttempt" for event in events)
        assert any(
            event.node_id == "module-inner" and event.kind == "nodeAttempt"
            and [scope["id"] for scope in event.payload["executionContext"]["scopes"]]
            == [wrapper.id, module.id]
            for event in events
        )
        assert any(event.node_id == "root-output" and event.kind == "output" and event.payload.get("value") == 42 for event in events)
        attempts, _ = ProjectRunEvidence(factory).node_attempts(project.project_id, task.task_id)
        inner = next(item for item in attempts if item["nodeId"] == "module-inner")
        assert inner["nodeName"] == "设置变量"
        assert [scope["id"] for scope in inner["executionContext"]["scopes"]] == [wrapper.id, module.id]
        assert not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


def test_project_rejects_excluded_node_inside_custom_module(tmp_path: Path) -> None:
    from autoflow.application.workflows.modules import CustomModuleService
    from autoflow.infrastructure.database.workflow_modules import (
        SqlAlchemyWorkflowModules,
    )

    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    try:
        modules = CustomModuleService(SqlAlchemyWorkflowModules(factory))
        module = modules.create(
            {
                "name": "excluded_nested_node",
                "display_name": "已排除节点",
                "parameters": [], "outputs": [],
                "workflow": {
                    "nodes": [{"id": "excluded", "type": "notify_wecom", "data": {"moduleType": "notify_wecom"}}],
                    "edges": [], "variables": [],
                },
            },
            client_request_id=str(uuid4()),
        )
        document = workflow_payload(automation.workflow_id)
        document["content"].update(
            schemaVersion=3,
            nodes=[{"id": "module-call", "type": "custom_module", "position": {"x": 100, "y": 80}, "data": {
                "moduleType": "custom_module", "config": {"customModuleId": module.id},
            }}],
            edges=[],
        )
        WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
            automation.workflow_id, {**document["content"], "id": automation.workflow_id},
            expected_revision=1, client_request_id=str(uuid4()),
        )
        coordinator._core = WorkflowRuntimeService(
            factory, SqlAlchemyWorkflowRepository(factory), modules=modules
        )
        with pytest.raises(WorkflowRuntimeError) as rejected:
            coordinator.start(
                project.project_id, automation.automation_id, str(uuid4()),
                start_payload(automation),
            )
        assert rejected.value.code == "WORKFLOW_PREFLIGHT_FAILED"
        assert rejected.value.details["moduleId"] == module.id
        assert rejected.value.details["issues"][0]["nodeId"] == "excluded"
        assert rejected.value.details["issues"][0]["code"] == "UNSUPPORTED_NODE_TYPE"
    finally:
        factory.dispose()


def test_project_detects_browser_requirement_inside_custom_module(tmp_path: Path) -> None:
    from autoflow.application.workflows.modules import CustomModuleService
    from autoflow.infrastructure.database.workflow_modules import (
        SqlAlchemyWorkflowModules,
    )

    factory, _, _, _, _, _, automation = setup(tmp_path)
    try:
        modules = CustomModuleService(SqlAlchemyWorkflowModules(factory))
        module = modules.create(
            {
                "name": "nested_browser",
                "display_name": "网页模块",
                "parameters": [], "outputs": [],
                "workflow": {
                    "nodes": [{"id": "nested-page", "type": "open_page", "data": {
                        "moduleType": "open_page", "config": {"url": "http://127.0.0.1/"},
                    }}],
                    "edges": [], "variables": [],
                },
            },
            client_request_id=str(uuid4()),
        )
        document = workflow_payload(automation.workflow_id)
        document["content"].update(
            schemaVersion=3,
            nodes=[{"id": "browser-module", "type": "custom_module", "position": {"x": 100, "y": 80}, "data": {
                "moduleType": "custom_module", "config": {"customModuleId": module.id},
            }}],
            edges=[],
        )
        saved = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
            automation.workflow_id, {**document["content"], "id": automation.workflow_id},
            expected_revision=1, client_request_id=str(uuid4()),
        )
        runtime = WorkflowRuntimeService(
            factory, SqlAlchemyWorkflowRepository(factory), modules=modules
        )
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


@pytest.mark.asyncio
async def test_project_task_runs_frozen_nested_workflow_in_real_worker(tmp_path: Path) -> None:
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    worker = ProjectWorkflowWorkerManager(tmp_path / "nested-workflow-worker", start_timeout=10)
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        child = _studio_payload(str(uuid4()))
        child.update(
            projectId=project.project_id, name="项目子工作流", schemaVersion=3,
            nodes=[{"id": "child-set", "type": "set_variable", "position": {"x": 0, "y": 0}, "data": {
                "moduleType": "set_variable", "config": {
                    "variableName": "child_value", "variableValue": "42",
                },
            }}], edges=[], variables=[],
        )
        saved_child = documents.create(child, client_request_id=str(uuid4()))
        parent = _studio_payload(automation.workflow_id)
        parent.update(schemaVersion=3, nodes=[
            {"id": "call", "type": "run_workflow_file", "position": {"x": 0, "y": 0}, "data": {
                "moduleType": "run_workflow_file", "config": {
                    "workflowFile": saved_child.id, "resultVariable": "summary",
                },
            }},
            {"id": "root-output", "type": "set_variable", "position": {"x": 200, "y": 0}, "data": {
                "moduleType": "set_variable", "config": {
                    "variableName": "result", "variableValue": "{child_value}",
                },
            }},
        ], edges=[{"id": "after-call", "source": "call", "target": "root-output"}], variables=[])
        documents.update(
            automation.workflow_id, parent, expected_revision=1,
            client_request_id=str(uuid4()),
        )
        runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
        coordinator._core = runtime
        batch, _, _ = coordinator.start(
            project.project_id, automation.automation_id, str(uuid4()), start_payload(automation),
        )
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        assert run is not None
        prepared = runtime.query_prepared_content(prepared_content_id=run.prepared_content_id)
        assert prepared is not None
        assert prepared.execution_plan["workflowDependencies"][saved_child.id]["nodes"][0]["id"] == "child-set"
        child["nodes"][0]["data"]["config"]["variableValue"] = "99"
        documents.update(
            saved_child.id, child, expected_revision=saved_child.revision,
            client_request_id=str(uuid4()),
        )
        await dispatcher.dispatch(
            run.run_id, expected_status_revision=run.status_revision,
            execution_generation=run.execution_generation,
        )
        await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=run.run_id)
            events = repository.list_events(run.run_id, after_sequence=0, limit=100)
        assert finished is not None and finished.status == "succeeded", [
            (event.kind, event.node_id, dict(event.payload)) for event in events
        ]
        assert any(
            event.node_id == "child-set" and event.kind == "nodeAttempt"
            and event.payload.get("status") == "succeeded"
            and event.payload["executionContext"]["scopes"][-1]["id"] == saved_child.id
            for event in events
        )
        assert any(
            event.node_id == "root-output" and event.kind == "output"
            and event.payload.get("value") == 42 for event in events
        )
        attempts, _ = ProjectRunEvidence(factory).node_attempts(project.project_id, task.task_id)
        assert next(item for item in attempts if item["nodeId"] == "child-set")["nodeName"] == "设置变量"
        assert not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_project_module_keeps_scope_when_calling_child_workflow(tmp_path: Path) -> None:
    from autoflow.application.workflows.modules import CustomModuleService
    from autoflow.infrastructure.database.workflow_modules import (
        SqlAlchemyWorkflowModules,
    )

    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    modules = CustomModuleService(SqlAlchemyWorkflowModules(factory))
    worker = ProjectWorkflowWorkerManager(tmp_path / "module-child-worker", start_timeout=10)
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        child = _studio_payload(str(uuid4()))
        child.update(
            projectId=project.project_id, name="模块内子工作流", schemaVersion=3,
            nodes=[{"id": "child-set", "type": "set_variable", "position": {"x": 0, "y": 0}, "data": {
                "moduleType": "set_variable", "config": {
                    "variableName": "answer", "variableValue": "42",
                },
            }}], edges=[], variables=[],
        )
        saved_child = documents.create(child, client_request_id=str(uuid4()))
        module = modules.create({
            "name": "calls_child", "display_name": "调用子工作流", "parameters": [],
            "outputs": [{"name": "answer"}],
            "workflow": {"nodes": [{"id": "module-child-call", "type": "run_workflow_file", "data": {
                "moduleType": "run_workflow_file", "config": {"workflowFile": saved_child.id},
            }}], "edges": [], "variables": []},
        }, client_request_id=str(uuid4()))
        parent = _studio_payload(automation.workflow_id)
        parent.update(schemaVersion=3, nodes=[
            {"id": "module-call", "type": "custom_module", "position": {"x": 0, "y": 0}, "data": {
                "moduleType": "custom_module", "config": {"customModuleId": module.id},
            }},
            {"id": "root-output", "type": "set_variable", "position": {"x": 200, "y": 0}, "data": {
                "moduleType": "set_variable", "config": {
                    "variableName": "result", "variableValue": "{answer}",
                },
            }},
        ], edges=[{"id": "after-module", "source": "module-call", "target": "root-output"}])
        documents.update(
            automation.workflow_id, parent, expected_revision=1,
            client_request_id=str(uuid4()),
        )
        runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory), modules=modules)
        coordinator._core = runtime
        batch, _, _ = coordinator.start(
            project.project_id, automation.automation_id, str(uuid4()), start_payload(automation),
        )
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        assert run is not None
        prepared = runtime.query_prepared_content(prepared_content_id=run.prepared_content_id)
        assert prepared is not None
        assert saved_child.id in prepared.execution_plan["workflowDependencies"]
        await dispatcher.dispatch(
            run.run_id, expected_status_revision=run.status_revision,
            execution_generation=run.execution_generation,
        )
        await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=run.run_id)
            events = repository.list_events(run.run_id, after_sequence=0, limit=100)
        assert finished is not None and finished.status == "succeeded"
        child_attempt = next(event for event in events if event.node_id == "child-set" and event.kind == "nodeAttempt")
        assert [scope["id"] for scope in child_attempt.payload["executionContext"]["scopes"]] == [module.id, saved_child.id]
        assert any(event.node_id == "root-output" and event.kind == "output" and event.payload.get("value") == 42 for event in events)
        assert not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


def test_project_nested_workflow_rejects_other_project_reference(tmp_path: Path) -> None:
    factory, projects, _, coordinator, _, project, automation = setup(tmp_path)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    try:
        other, _, _ = projects.create(str(uuid4()), {"name": "其他项目", "description": ""})
        child = _studio_payload(str(uuid4()))
        child.update(projectId=other.project_id, name="其他项目工作流", schemaVersion=3)
        saved_child = documents.create(child, client_request_id=str(uuid4()))
        parent = _studio_payload(automation.workflow_id)
        parent.update(schemaVersion=3, nodes=[{"id": "call", "type": "run_workflow_file", "position": {"x": 0, "y": 0}, "data": {
            "moduleType": "run_workflow_file", "config": {"workflowFile": saved_child.id},
        }}], edges=[], variables=[])
        documents.update(
            automation.workflow_id, parent, expected_revision=1,
            client_request_id=str(uuid4()),
        )
        coordinator._core = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
        with pytest.raises(WorkflowRuntimeError) as rejected:
            coordinator.start(
                project.project_id, automation.automation_id, str(uuid4()), start_payload(automation),
            )
        assert rejected.value.code == "WORKFLOW_DEPENDENCY_MISSING"
        assert rejected.value.details["reference"] == saved_child.id
    finally:
        factory.dispose()


@pytest.mark.parametrize(
    ("node_type", "config", "expected_code"),
    [
        ("open_page", {"url": "http://127.0.0.1/"}, "CAPABILITY_MISSING"),
        ("notify_wecom", {}, "WORKFLOW_PREFLIGHT_FAILED"),
    ],
)
def test_project_nested_workflow_checks_frozen_child_before_start(
    tmp_path: Path, node_type: str, config: dict[str, Any], expected_code: str,
) -> None:
    factory, _, _, _, _, project, automation = setup(tmp_path)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    try:
        child = _studio_payload(str(uuid4()))
        child.update(
            projectId=project.project_id, name="待校验子工作流", schemaVersion=3,
            nodes=[{"id": "child-node", "type": node_type, "position": {"x": 0, "y": 0},
                    "data": {"moduleType": node_type, "config": config}}],
            edges=[], variables=[],
        )
        saved_child = documents.create(child, client_request_id=str(uuid4()))
        parent = _studio_payload(automation.workflow_id)
        parent.update(schemaVersion=3, nodes=[{
            "id": "call", "type": "run_workflow_file", "position": {"x": 0, "y": 0},
            "data": {"moduleType": "run_workflow_file", "config": {"workflowFile": saved_child.id}},
        }], edges=[], variables=[])
        saved_parent = documents.update(
            automation.workflow_id, parent, expected_revision=1,
            client_request_id=str(uuid4()),
        )
        runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
        if node_type == "open_page":
            assert runtime.requires_browser(automation.workflow_id)
        with pytest.raises(WorkflowRuntimeError) as rejected:
            runtime.prepare_content(
                prepare_operation_id=str(uuid4()), workflow_id=automation.workflow_id,
                source_revision=saved_parent.revision, available_capabilities=[],
            )
        assert rejected.value.code == expected_code
        if node_type == "notify_wecom":
            assert rejected.value.details["workflowId"] == saved_child.id
            assert rejected.value.details["issues"][0]["nodeId"] == "child-node"
    finally:
        factory.dispose()


@pytest.mark.asyncio
async def test_project_batch_runs_condition_and_loop_in_real_worker(tmp_path: Path) -> None:
    factory, _, _, coordinator, runtime, project, automation = setup(tmp_path)
    worker = ProjectWorkflowWorkerManager(tmp_path / "control-worker", start_timeout=10)
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, worker, resources)
    try:
        document = workflow_payload(automation.workflow_id)
        document["content"]["schemaVersion"] = 3
        document["content"]["nodes"] = [
            {
                "id": node_id, "type": module_type,
                "position": {"x": index * 120, "y": 0},
                "data": {"moduleType": module_type, "config": config},
            }
            for index, (node_id, module_type, config) in enumerate([
                ("gate", "condition", {"conditionType": "boolean", "leftValue": True}),
                ("repeat", "loop", {"loopType": "count", "loopCount": 3}),
                ("body", "set_variable", {"variableName": "last", "variableValue": "{index}"}),
                ("done", "set_variable", {"variableName": "finished", "variableValue": "完成"}),
                ("skipped", "set_variable", {"variableName": "skipped", "variableValue": "跳过"}),
            ])
        ]
        document["content"]["edges"] = [
            {"id": "true", "source": "gate", "sourceHandle": "true", "target": "repeat"},
            {"id": "false", "source": "gate", "sourceHandle": "false", "target": "skipped"},
            {"id": "body", "source": "repeat", "sourceHandle": "loop", "target": "body"},
            {"id": "done", "source": "repeat", "sourceHandle": "done", "target": "done"},
        ]
        saved = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
            automation.workflow_id,
            {**document["content"], "id": automation.workflow_id},
            expected_revision=1,
            client_request_id=str(uuid4()),
        )
        batch, _, _ = coordinator.start(
            project.project_id, automation.automation_id, str(uuid4()), start_payload(automation)
        )
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        assert saved.revision == 2 and run is not None
        prepared = runtime.query_prepared_content(prepared_content_id=run.prepared_content_id)
        assert prepared is not None and prepared.adapter_version == "webrpa-graph/v1"
        assert [dict(edge) for edge in prepared.execution_plan["document"]["edges"]] == document["content"]["edges"]
        await dispatcher.dispatch(
            run.run_id,
            expected_status_revision=run.status_revision,
            execution_generation=run.execution_generation,
        )
        await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=run.run_id)
            events = repository.list_events(run.run_id, after_sequence=0, limit=100)
        assert finished is not None and finished.status == "succeeded"
        attempts = [event for event in events if event.kind == "nodeAttempt" and event.payload["status"] == "succeeded"]
        assert [event.node_id for event in attempts].count("body") == 3
        assert not any(event.node_id == "skipped" for event in attempts)
        assert any(event.kind == "output" and event.payload.get("name") == "finished" and event.payload.get("value") == "完成" for event in events)
        assert resources.requests == [] and not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_project_batch_executes_canvas_subflow_in_real_worker(tmp_path: Path) -> None:
    factory, _, _, coordinator, runtime, project, automation = setup(tmp_path)
    worker = ProjectWorkflowWorkerManager(tmp_path / "subflow-worker", start_timeout=10)
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, worker, resources)
    try:
        document = workflow_payload(automation.workflow_id)
        document["content"]["schemaVersion"] = 3
        document["content"]["nodes"] = [
            {"id": "definition", "type": "group", "position": {"x": 100, "y": 100},
             "data": {"moduleType": "group", "isSubflow": True, "subflowName": "项目子流程", "width": 300, "height": 200}},
            {"id": "inner", "type": "set_variable", "position": {"x": 150, "y": 150},
             "data": {"moduleType": "set_variable", "config": {"variableName": "answer", "variableValue": "42"}}},
            {"id": "call", "type": "subflow", "position": {"x": 500, "y": 100},
             "data": {"moduleType": "subflow", "config": {"subflowGroupId": "definition", "subflowName": "项目子流程"}}},
            {"id": "tail", "type": "set_variable", "position": {"x": 700, "y": 100},
             "data": {"moduleType": "set_variable", "config": {"variableName": "result", "variableValue": "{answer}"}}},
        ]
        document["content"]["edges"] = [{"id": "after", "source": "call", "target": "tail"}]
        WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
            automation.workflow_id, {**document["content"], "id": automation.workflow_id},
            expected_revision=1, client_request_id=str(uuid4()),
        )
        batch, _, _ = coordinator.start(
            project.project_id, automation.automation_id, str(uuid4()), start_payload(automation)
        )
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        assert run is not None
        await dispatcher.dispatch(
            run.run_id,
            expected_status_revision=run.status_revision,
            execution_generation=run.execution_generation,
        )
        await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=run.run_id)
            events = repository.list_events(run.run_id, after_sequence=0, limit=100)
        assert finished is not None and finished.status == "succeeded"
        completed = [event.node_id for event in events if event.kind == "nodeAttempt" and event.payload["status"] == "succeeded"]
        assert completed == ["inner", "call", "tail"]
        assert any(event.kind == "output" and event.payload.get("name") == "result" and event.payload.get("value") == 42 for event in events)
        assert resources.requests == [] and not worker.busy()
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
