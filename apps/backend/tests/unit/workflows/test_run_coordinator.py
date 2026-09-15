from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from autoflow.adapters.events.workflows import StudioEventJournal
from autoflow.application.workflows.coordinator import WorkflowRunCoordinator
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.executors.basic import OpenPageExecutor
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.workflows.browser import WorkflowWorkerSession
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
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

    async def start(
        self,
        run_id: str,
        profile_id: str,
        executable: Path,
        payload: dict[str, Any],
    ) -> WorkflowWorkerSession:
        assert executable.is_file()
        self.payloads.append(payload)
        return WorkflowWorkerSession(run_id, profile_id, 10, 11)

    async def stop(self, run_id: str) -> None:
        self.stopped.append(run_id)

    def busy(self) -> bool:
        return bool(self.payloads) and not self.stopped


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


async def _none() -> None:
    return None
