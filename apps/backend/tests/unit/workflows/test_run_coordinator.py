from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from autoflow.adapters.events.workflows import StudioEventJournal
from autoflow.application.models.service import ModelExecutionBinding
from autoflow.application.workflows.coordinator import WorkflowRunCoordinator
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.executors.basic import OpenPageExecutor
from autoflow.application.workflows.executors.input_prompt import InputPromptExecutor
from autoflow.application.workflows.executors.js_script import JsScriptExecutor
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.modules import CustomModuleService
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.models import ProviderConnection
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.workflows.browser import WorkflowWorkerSession
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_modules import SqlAlchemyWorkflowModules
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments


class FakeProfiles:
    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def get(self, profile_id: str) -> Profile:
        assert profile_id == self.profile.id
        return self.profile


class FakeResources:
    def __init__(self) -> None:
        self.owner_id: str | None = None
        self.acquired: list[tuple[str, str, str, str]] = []
        self.released: list[str] = []

    async def acquire(self, owner_id: str, profile_id: str, kernel: Any) -> None:
        self.owner_id = owner_id
        self.acquired.append((owner_id, profile_id, kernel.edition, kernel.version))

    async def release(self, owner_id: str) -> None:
        assert self.owner_id == owner_id
        self.owner_id = None
        self.released.append(owner_id)


class FakeWorkers:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []
        self.stopped: list[str] = []
        self.commands: list[tuple[str, dict[str, Any]]] = []

    async def start(
        self,
        run_id: str,
        profile_id: str,
        executable: Path | None,
        payload: dict[str, Any],
    ) -> WorkflowWorkerSession:
        assert executable is None or executable.is_file()
        self.payloads.append(payload)
        return WorkflowWorkerSession(run_id, profile_id, 10, 11)

    async def stop(self, run_id: str) -> None:
        self.stopped.append(run_id)

    def busy(self) -> bool:
        return bool(self.payloads) and not self.stopped

    async def send_command(self, run_id: str, command: dict[str, Any]) -> None:
        self.commands.append((run_id, command))


def _profile() -> Profile:
    spec = ProfileSpec.from_values(
        {
            "name": "正式配置",
            "description": "",
            "start_url": "https://must-not-launch.example",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "geoip": False,
            "headless": False,
            "humanize": True,
            "human_preset": "default",
            "user_agent": "AutoFlow",
            "viewport": {"width": 1280, "height": 720},
            "color_scheme": "dark",
            "extension_paths": [],
            "expert_args": [],
            "browser_version": "145.0.1",
            "browser_edition": "public",
            "release_channel": "stable",
            "proxy_mode": "none",
        }
    )
    now = datetime(2026, 9, 15, tzinfo=UTC)
    return Profile("profile-1", spec, 12345, now, now)


@pytest.mark.asyncio
async def test_coordinator_resolves_model_id_without_persisting_secret(tmp_path: Path):
    database = tmp_path / "model-run.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(sessions))
    documents.create(
        {
            "id": "ai-flow",
            "name": "模型流程",
            "nodes": [
                {
                    "id": "ask",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "ai_chat",
                        "config": {
                            "modelId": "model-1",
                            "fallbackModelIds": ["model-2"],
                            "userPrompt": "问题",
                        },
                    },
                }
            ],
            "edges": [],
            "variables": [],
        },
        client_request_id="create-ai-flow",
    )
    repository = SqlAlchemyWorkflowRuns(sessions)
    runs = WorkflowRunService(repository)
    workers = FakeWorkers()
    resolved: list[str] = []

    def resolve(model_id: str) -> ModelExecutionBinding:
        resolved.append(model_id)
        return ModelExecutionBinding(
            model_id,
            f"key-{model_id}",
            ProviderConnection(
                "custom-openai-compatible",
                "openai-compatible",
                "https://model.example/v1",
            ),
            f"secret-{model_id}",
        )

    coordinator = WorkflowRunCoordinator(
        documents=documents,
        runs=runs,
        run_repository=repository,
        runtime=WorkflowRuntime(build_production_executor_registry()),
        profiles=FakeProfiles(_profile()),
        installed_kernels=list,
        resolve_proxy=lambda _profile, _run_id: _none(),
        read_license=lambda: None,
        workers=workers,
        resources=FakeResources(),
        events=StudioEventJournal(),
        artifact_root=tmp_path / "workspace",
        resolve_model=resolve,
    )

    accepted = await coordinator.start(
        "ai-flow",
        {
            "runId": "ai-run",
            "documentId": "ai-flow",
            "profileId": "profile-1",
        },
    )

    assert accepted["status"] == "running"
    assert resolved == ["model-1", "model-2"]
    assert workers.payloads[0]["modelBindings"] == [
        {
            "modelId": "model-1",
            "modelKey": "key-model-1",
            "presetId": "custom-openai-compatible",
            "providerKind": "openai-compatible",
            "baseUrl": "https://model.example/v1",
            "secret": "secret-model-1",
        },
        {
            "modelId": "model-2",
            "modelKey": "key-model-2",
            "presetId": "custom-openai-compatible",
            "providerKind": "openai-compatible",
            "baseUrl": "https://model.example/v1",
            "secret": "secret-model-2",
        },
    ]
    assert "secret-model" not in json.dumps(
        runs.get("ai-run").document_snapshot, ensure_ascii=False
    )


@pytest.mark.asyncio
async def test_coordinator_starts_frozen_document_and_finishes_only_after_cleanup(
    tmp_path: Path,
) -> None:
    database = tmp_path / "coordinator.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(sessions))
    documents.create(
        {
            "id": "workflow-1",
            "name": "协调器流程",
            "nodes": [
                {
                    "id": "open",
                    "type": "moduleNode",
                    "position": {"x": 120, "y": 80},
                    "data": {
                        "moduleType": "open_page",
                        "config": {"url": "https://example.test"},
                    },
                }
            ],
            "edges": [],
            "variables": [],
        },
        client_request_id="create-workflow",
    )
    repository = SqlAlchemyWorkflowRuns(sessions)
    runs = WorkflowRunService(repository)
    registry = ExecutorRegistry()
    registry.register(OpenPageExecutor)
    workers = FakeWorkers()
    resources = FakeResources()
    journal = StudioEventJournal()
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")
    coordinator = WorkflowRunCoordinator(
        documents=documents,
        runs=runs,
        run_repository=repository,
        runtime=WorkflowRuntime(registry),
        profiles=FakeProfiles(_profile()),
        installed_kernels=lambda: [
            InstalledKernel("public", "145.0.1", executable, executable.stat().st_size)
        ],
        resolve_proxy=lambda _profile, _run_id: _none(),
        read_license=lambda: None,
        workers=workers,
        resources=resources,
        events=journal,
        artifact_root=tmp_path / "workspace",
    )

    accepted = await coordinator.start(
        "workflow-1",
        {
            "runId": "run-1",
            "documentId": "document-1",
            "profileId": "profile-1",
            "headless": True,
        },
    )
    duplicate = await coordinator.start(
        "workflow-1",
        {
            "runId": "run-1",
            "documentId": "document-1",
            "profileId": "profile-1",
            "headless": True,
        },
    )

    assert accepted["status"] == "running"
    assert duplicate == accepted
    assert resources.acquired == [("run-1", "profile-1", "public", "145.0.1")]
    assert len(workers.payloads) == 1
    payload = workers.payloads[0]
    assert payload["document"]["nodes"][0]["id"] == "open"
    assert payload["document"]["nodes"][0]["position"] == {"x": 120, "y": 80}
    assert payload["headless"] is True
    assert payload["requiresBrowser"] is True
    assert "startUrl" not in payload

    await coordinator.on_worker_event(
        {
            "type": "execution:node_start",
            "runId": "run-1",
            "workflowId": "workflow-1",
            "nodeId": "open",
            "executionId": "execution-1",
        }
    )
    await coordinator.on_worker_event(
        {
            "type": "execution:node_complete",
            "runId": "run-1",
            "workflowId": "workflow-1",
            "nodeId": "open",
            "executionId": "execution-1",
            "success": True,
            "message": "已打开网页",
            "data": None,
            "artifactIds": [],
        }
    )
    await coordinator.on_worker_event(
        {
            "type": "execution:completed",
            "runId": "run-1",
            "workflowId": "workflow-1",
            "executedNodes": 1,
        }
    )
    assert runs.get("run-1").status == "running"

    await coordinator.on_worker_exit("run-1", 0)

    assert resources.released == ["run-1"]
    assert runs.get("run-1").status == "completed"
    assert [item.event for item in journal.replay(after_sequence=0)] == [
        "execution:started",
        "execution:node_start",
        "execution:node_complete",
        "execution:log",
        "execution:completed",
    ]
    logs, total, next_cursor = runs.logs(
        "run-1", cursor=0, limit=20, query=None, levels=(), node_id=None
    )
    assert total == 2
    assert next_cursor is None
    assert [item["message"] for item in logs] == [
        "已打开网页",
        "执行完成，共执行 1 个节点，失败 0 个",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("via_workflow", [False, True])
async def test_browser_requirement_propagates_from_frozen_custom_module(
    tmp_path: Path,
    via_workflow: bool,
) -> None:
    database = tmp_path / "custom-module-browser.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    modules = CustomModuleService(SqlAlchemyWorkflowModules(sessions))
    module = modules.create(
        {
            "name": "browser_module",
            "display_name": "浏览器模块",
            "parameters": [],
            "outputs": [],
            "workflow": {
                "nodes": [
                    {
                        "id": "open",
                        "type": "moduleNode",
                        "data": {
                            "moduleType": "open_page",
                            "config": {"url": "https://example.test"},
                        },
                    }
                ],
                "edges": [],
                "variables": [],
            },
        },
        client_request_id="create-browser-module",
    )
    documents = WorkflowDocumentService(
        SqlAlchemyWorkflowDocuments(sessions), custom_module_exists=modules.exists
    )
    if via_workflow:
        documents.create(
            {
                "id": "browser-child",
                "name": "browser-child",
                **module.definition["workflow"],
            },
            client_request_id="create-child",
        )
        module = modules.update(
            module.id,
            {
                "workflow": {
                    "nodes": [
                        {
                            "id": "nested",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "run_workflow_file",
                                "workflowFile": "browser-child",
                            },
                        }
                    ],
                    "edges": [],
                }
            },
            expected_revision=1,
            client_request_id="use-child",
        )
    documents.create(
        {
            "id": "module-browser-flow",
            "name": "模块浏览器传播",
            "nodes": [
                {
                    "id": "call",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "custom_module",
                        "customModuleId": module.id,
                    },
                }
            ],
            "edges": [],
            "variables": [],
        },
        client_request_id="create-module-browser-flow",
    )
    repository = SqlAlchemyWorkflowRuns(sessions)
    workers = FakeWorkers()
    resources = FakeResources()
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")
    coordinator = WorkflowRunCoordinator(
        documents=documents,
        runs=WorkflowRunService(repository),
        run_repository=repository,
        runtime=WorkflowRuntime(build_production_executor_registry()),
        profiles=FakeProfiles(_profile()),
        installed_kernels=lambda: [
            InstalledKernel("public", "145.0.1", executable, executable.stat().st_size)
        ],
        resolve_proxy=lambda _profile, _run_id: _none(),
        read_license=lambda: None,
        workers=workers,
        resources=resources,
        events=StudioEventJournal(),
        artifact_root=tmp_path / "workspace",
        modules=modules,
    )

    accepted = await coordinator.start(
        "module-browser-flow",
        {
            "runId": "module-browser-run",
            "documentId": "module-browser-flow",
            "profileId": "profile-1",
        },
    )

    assert accepted["status"] == "running"
    assert resources.acquired == [
        ("module-browser-run", "profile-1", "public", "145.0.1")
    ]
    assert workers.payloads[0]["requiresBrowser"] is True
    assert (
        workers.payloads[0]["customModuleDependencies"][module.id]["revision"]
        == module.revision
    )
    if via_workflow:
        assert "browser-child" in workers.payloads[0]["workflowDependencies"]


@pytest.mark.asyncio
async def test_input_command_waits_for_worker_ack_and_is_idempotent(
    tmp_path: Path,
) -> None:
    database = tmp_path / "input.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(sessions))
    documents.create(
        {
            "id": "input-flow",
            "name": "真实输入",
            "nodes": [
                {
                    "id": "prompt",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "input_prompt",
                        "config": {"variableName": "answer"},
                    },
                }
            ],
            "edges": [],
            "variables": [{"name": "answer", "value": "before"}],
        },
        client_request_id="create-input",
    )
    repository = SqlAlchemyWorkflowRuns(sessions)
    runs = WorkflowRunService(repository)
    registry = ExecutorRegistry()
    registry.register(InputPromptExecutor)
    workers = FakeWorkers()
    coordinator = WorkflowRunCoordinator(
        documents=documents,
        runs=runs,
        run_repository=repository,
        runtime=WorkflowRuntime(registry),
        profiles=FakeProfiles(_profile()),
        installed_kernels=list,
        resolve_proxy=lambda _profile, _run_id: _none(),
        read_license=lambda: None,
        workers=workers,
        resources=FakeResources(),
        events=StudioEventJournal(),
        artifact_root=tmp_path / "workspace",
    )
    await coordinator.start(
        "input-flow",
        {
            "runId": "input-run",
            "documentId": "input-flow",
            "profileId": "profile-1",
        },
    )
    await coordinator.on_worker_event(
        {
            "type": "execution:input_prompt",
            "runId": "input-run",
            "workflowId": "input-flow",
            "nodeId": "prompt",
            "executionId": "execution-1",
            "requestId": "request-1",
            "variableName": "answer",
            "title": "输入",
            "message": "请输入",
            "defaultValue": "",
            "inputMode": "single",
            "required": True,
        }
    )

    submitting = asyncio.create_task(
        coordinator.submit_event_command(
            "command-1",
            "input_prompt_result",
            {"requestId": "request-1", "value": "原文"},
        )
    )
    for _ in range(100):
        if workers.commands:
            break
        await asyncio.sleep(0)
    assert workers.commands == [
        (
            "input-run",
            {
                "type": "input_prompt_result",
                "commandId": "command-1",
                "requestId": "request-1",
                "value": "原文",
            },
        )
    ]
    assert submitting.done() is False
    await coordinator.on_worker_event(
        {
            "type": "execution:command_applied",
            "runId": "input-run",
            "workflowId": "input-flow",
            "commandId": "command-1",
            "requestId": "request-1",
        }
    )

    assert await submitting == ({"commandId": "command-1", "success": True}, 200)
    assert await coordinator.submit_event_command(
        "command-1",
        "input_prompt_result",
        {"requestId": "request-1", "value": "原文"},
    ) == ({"commandId": "command-1", "success": True}, 200)
    assert len(workers.commands) == 1
    assert coordinator.input_prompt_state("request-1")["status"] == "answered"
    assert coordinator.event_command("command-1") == (
        {"commandId": "command-1", "success": True, "httpStatus": 200},
        200,
    )


@pytest.mark.asyncio
async def test_js_script_claim_and_result_are_owned_idempotent_commands(
    tmp_path: Path,
) -> None:
    database = tmp_path / "js-script.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(sessions))
    documents.create(
        {
            "id": "js-flow",
            "name": "真实脚本",
            "nodes": [
                {
                    "id": "script",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "js_script",
                        "config": {"code": "return 2", "resultVariable": "answer"},
                    },
                }
            ],
            "edges": [],
            "variables": [{"name": "count", "value": 1}],
        },
        client_request_id="create-js-flow",
    )
    repository = SqlAlchemyWorkflowRuns(sessions)
    runs = WorkflowRunService(repository)
    registry = ExecutorRegistry()
    registry.register(JsScriptExecutor)
    workers = FakeWorkers()
    coordinator = WorkflowRunCoordinator(
        documents=documents,
        runs=runs,
        run_repository=repository,
        runtime=WorkflowRuntime(registry),
        profiles=FakeProfiles(_profile()),
        installed_kernels=list,
        resolve_proxy=lambda _profile, _run_id: _none(),
        read_license=lambda: None,
        workers=workers,
        resources=FakeResources(),
        events=StudioEventJournal(),
        artifact_root=tmp_path / "workspace",
    )
    await coordinator.start(
        "js-flow",
        {"runId": "js-run", "documentId": "js-flow", "profileId": "profile-1"},
    )
    await coordinator.on_worker_event(
        {
            "type": "execution:js_script",
            "runId": "js-run",
            "workflowId": "js-flow",
            "nodeId": "script",
            "executionId": "execution-1",
            "requestId": "request-1",
            "code": "return 2",
            "variables": {"count": 1},
        }
    )

    claim = {"requestId": "request-1", "claimId": "studio-1"}
    assert await coordinator.submit_event_command(
        "claim-1", "js_script_claim", claim
    ) == (
        {
            "commandId": "claim-1",
            "success": True,
            "requestId": "request-1",
        },
        200,
    )
    assert await coordinator.submit_event_command(
        "claim-1", "js_script_claim", claim
    ) == (
        {
            "commandId": "claim-1",
            "success": True,
            "requestId": "request-1",
        },
        200,
    )
    assert (await coordinator.submit_event_command(
        "foreign", "js_script_claim", {"requestId": "request-1", "claimId": "other"}
    ))[1] == 409

    payload = {
        **claim,
        "success": True,
        "result": 2,
        "variables": {"count": 2, "notDeclared": 99},
    }
    completing = asyncio.create_task(
        coordinator.submit_event_command("result-1", "js_script_result", payload)
    )
    for _ in range(100):
        if workers.commands:
            break
        await asyncio.sleep(0)
    assert workers.commands == [
        (
            "js-run",
            {"type": "js_script_result", "commandId": "result-1", **payload},
        )
    ]
    await coordinator.on_worker_event(
        {
            "type": "execution:command_applied",
            "runId": "js-run",
            "workflowId": "js-flow",
            "commandId": "result-1",
            "requestId": "request-1",
        }
    )
    assert (await completing)[1] == 200
    assert coordinator.js_script_state("request-1") == {
        "requestId": "request-1",
        "workflowId": "js-flow",
        "nodeId": "script",
        "status": "completed",
        "claimId": "studio-1",
    }
    assert await coordinator.submit_event_command(
        "result-1", "js_script_result", payload
    ) == await completing
    assert len(workers.commands) == 1

    await coordinator.on_worker_event(
        {
            "type": "execution:js_script",
            "runId": "js-run",
            "workflowId": "js-flow",
            "nodeId": "script",
            "executionId": "execution-2",
            "requestId": "request-2",
            "code": "return 3",
            "variables": {"count": 2},
        }
    )
    await coordinator.on_worker_exit("js-run", 17)
    assert coordinator.js_script_state("request-2")["status"] == "expired"
    assert (await coordinator.submit_event_command(
        "late-claim",
        "js_script_claim",
        {"requestId": "request-2", "claimId": "late"},
    ))[1] == 409


async def _none() -> None:
    return None
