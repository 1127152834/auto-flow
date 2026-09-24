"""Real SQLite admission tests; only the worker/process boundary is simulated."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from autoflow.adapters.events.workflows import StudioEventJournal
from autoflow.application.models.service import ModelExecutionBinding
from autoflow.application.workflows.coordinator import (
    WorkflowRunCoordinator,
    WorkflowRunError,
)
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.models import ProviderConnection
from autoflow.domain.models.errors import ModelError
from autoflow.domain.profiles.models import Profile
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
from tests.unit.workflows.test_run_coordinator import (
    FakeProfiles,
    FakeResources,
    FakeWorkers,
    _none,
    _profile,
)


class CountingProfiles(FakeProfiles):
    def __init__(self) -> None:
        super().__init__(_profile())
        self.reads: list[str] = []
        self.available = True

    def get(self, profile_id: str) -> Profile:
        self.reads.append(profile_id)
        assert self.available, "原 Profile 已删除，不允许重试重新读取"
        assert profile_id in {"profile-1", "profile-2"}
        return replace(self.profile, id=profile_id)


class MutableModelBinding:
    def __init__(self) -> None:
        self.reads: list[str] = []
        self.enabled = True
        self.secret = "first-secret"

    def __call__(self, model_id: str) -> ModelExecutionBinding:
        self.reads.append(model_id)
        if not self.enabled:
            raise ModelError("MODEL_DISABLED", "模型已停用", 409)
        return ModelExecutionBinding(
            model_id,
            "explicit-model-key",
            ProviderConnection(
                "custom-openai-compatible",
                "openai-compatible",
                "https://model.example/v1",
            ),
            self.secret,
        )


class RetryHarness:
    def __init__(self, tmp_path: Path) -> None:
        database = tmp_path / "retry.sqlite3"
        migrate_database(database)
        self.sessions = create_session_factory(database)
        documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(self.sessions))
        self.document: dict[str, Any] = {
            "id": "retry-flow",
            "name": "启动重试资源冻结",
            "nodes": [
                {
                    "id": "open",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "open_page",
                        "config": {"url": "https://example.test"},
                    },
                },
                {
                    "id": "ask",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "ai_chat",
                        "config": {"modelId": "model-1", "userPrompt": "问题"},
                    },
                },
            ],
            "edges": [{"id": "open-ask", "source": "open", "target": "ask"}],
            "variables": [],
        }
        documents.create(self.document, client_request_id="create-retry-flow")
        self.repository = SqlAlchemyWorkflowRuns(self.sessions)
        self.runs = WorkflowRunService(self.repository)
        self.profiles = CountingProfiles()
        self.model = MutableModelBinding()
        self.workers = FakeWorkers()
        self.resources = FakeResources()
        executable = tmp_path / "CloakBrowser"
        executable.write_bytes(b"test process boundary only")
        self.coordinator = WorkflowRunCoordinator(
            documents=documents,
            runs=self.runs,
            run_repository=self.repository,
            runtime=WorkflowRuntime(build_production_executor_registry()),
            profiles=self.profiles,
            installed_kernels=lambda: [
                InstalledKernel(
                    "public", "145.0.1", executable, executable.stat().st_size
                )
            ],
            resolve_proxy=lambda _profile, _run_id: _none(),
            read_license=lambda: None,
            workers=self.workers,
            resources=self.resources,
            events=StudioEventJournal(),
            artifact_root=tmp_path / "workspace",
            resolve_model=self.model,
        )
        self.request: dict[str, Any] = {
            "runId": "retry-run",
            "documentId": "retry-flow",
            "profileId": "profile-1",
            "document": copy.deepcopy(self.document),
        }


@pytest.fixture
def retry_harness(tmp_path: Path) -> Iterator[RetryHarness]:
    harness = RetryHarness(tmp_path)
    try:
        yield harness
    finally:
        harness.sessions.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation", ["profile-config", "model-secret", "model-disabled"]
)
async def test_same_request_returns_accepted_run_without_resolving_changed_resources(
    retry_harness: RetryHarness, mutation: str
) -> None:
    harness = retry_harness
    original_request = copy.deepcopy(harness.request)
    accepted = await harness.coordinator.start("retry-flow", harness.request)
    assert accepted["status"] == "running"
    assert harness.profiles.reads == ["profile-1"]
    assert harness.model.reads == ["model-1"]
    frozen_run = harness.runs.get("retry-run")
    frozen_payload = copy.deepcopy(harness.workers.payloads[0])
    assert frozen_payload["modelBindings"][0]["secret"] == "first-secret"

    if mutation == "profile-config":
        profile = harness.profiles.profile
        harness.profiles.profile = replace(
            profile, spec=replace(profile.spec, locale="en-US", timezone="UTC")
        )
    elif mutation == "model-secret":
        harness.model.secret = "changed-secret"
    else:
        harness.model.enabled = False

    retried = await harness.coordinator.start(
        "retry-flow", copy.deepcopy(original_request)
    )

    assert retried == accepted
    assert harness.profiles.reads == ["profile-1"], "重试不能再次读取 Profile"
    assert harness.model.reads == ["model-1"], "重试不能再次解析模型或读取秘密"
    assert harness.workers.payloads == [frozen_payload]
    assert len(harness.resources.acquired) == 1
    assert harness.runs.get("retry-run") == frozen_run
    assert harness.request == original_request


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "draft",
        "profile-id",
        "debug-options",
        "headless",
        "run-to",
        "workflow-id",
        "document-id",
        "layout",
    ],
)
async def test_same_run_id_with_different_original_request_is_conflict(
    retry_harness: RetryHarness, mutation: str
) -> None:
    harness = retry_harness
    await harness.coordinator.start("retry-flow", harness.request)
    original = harness.runs.get("retry-run")
    request = copy.deepcopy(harness.request)
    workflow_id = "retry-flow"
    if mutation == "draft":
        request["document"]["nodes"][1]["data"]["config"]["userPrompt"] = "不同的问题"
    elif mutation == "profile-id":
        request["profileId"] = "profile-2"
    elif mutation == "debug-options":
        request["stepMode"] = True
        request["breakpoints"] = ["ask"]
    elif mutation == "headless":
        request["headless"] = True
    elif mutation == "run-to":
        request["runToNodeId"] = "ask"
    elif mutation == "workflow-id":
        workflow_id = "other-flow"
    elif mutation == "document-id":
        request["documentId"] = "other-document"
    else:
        request["document"]["nodes"][0]["position"] = {"x": 250, "y": 300}

    with pytest.raises(WorkflowRunError) as captured:
        await harness.coordinator.start(workflow_id, request)

    assert captured.value.code == "RUN_ID_CONFLICT"
    assert captured.value.status == 409
    assert harness.runs.get("retry-run") == original
    assert len(harness.workers.payloads) == 1
    assert len(harness.resources.acquired) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", ["completed", "failed", "stopped"])
async def test_terminal_retry_preserves_result_without_reopening_released_resources(
    retry_harness: RetryHarness, terminal: str
) -> None:
    harness = retry_harness
    await harness.coordinator.start("retry-flow", harness.request)
    if terminal == "stopped":
        await harness.coordinator.stop("retry-flow", "retry-run")
    else:
        await harness.coordinator.on_worker_event(
            {
                "type": f"execution:{terminal}",
                "runId": "retry-run",
                "workflowId": "retry-flow",
                "executedNodes": 2 if terminal == "completed" else 1,
                "error": "原始模型错误" if terminal == "failed" else None,
            }
        )
    await harness.coordinator.on_worker_exit(
        "retry-run", 1 if terminal == "failed" else 0
    )
    original = harness.runs.get("retry-run")
    assert original.status == terminal
    assert harness.resources.owner_id is None
    assert harness.resources.released == ["retry-run"]
    original_payload = copy.deepcopy(harness.workers.payloads[0])
    original_stop_calls = list(harness.workers.stopped)
    harness.profiles.available = False
    harness.model.enabled = False

    retried = await harness.coordinator.start(
        "retry-flow", copy.deepcopy(harness.request)
    )

    assert retried["status"] == terminal
    assert harness.runs.get("retry-run") == original
    assert harness.profiles.reads == ["profile-1"]
    assert harness.model.reads == ["model-1"]
    assert harness.workers.payloads == [original_payload]
    assert harness.workers.stopped == original_stop_calls
    assert len(harness.resources.acquired) == 1
    assert harness.resources.released == ["retry-run"]
    assert harness.resources.owner_id is None
