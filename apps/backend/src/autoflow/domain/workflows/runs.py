from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

RunMode = Literal["run", "debug"]
RunStatus = Literal[
    "starting",
    "running",
    "paused",
    "failed_paused",
    "completed",
    "failed",
    "stopped",
    "interrupted",
]
TerminalRunStatus = Literal["completed", "failed", "stopped", "interrupted"]


class WorkflowRunError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 409,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class WorkflowRunStart:
    run_id: str
    workflow_id: str
    document_id: str
    workflow_name: str
    document_snapshot: dict[str, Any]
    layout_snapshot: dict[str, Any]
    profile_id: str | None
    profile_snapshot: dict[str, Any]
    mode: RunMode
    custom_module_snapshots: dict[str, Any] = field(default_factory=dict)
    project_id: str | None = None

    def request_payload(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "workflowId": self.workflow_id,
            "documentId": self.document_id,
            "workflowName": self.workflow_name,
            "documentSnapshot": self.document_snapshot,
            "layoutSnapshot": self.layout_snapshot,
            "profileId": self.profile_id,
            "profileSnapshot": self.profile_snapshot,
            "mode": self.mode,
            "customModuleSnapshots": self.custom_module_snapshots,
            # Keep existing unscoped command hashes stable across upgrades.
            **({"projectId": self.project_id} if self.project_id is not None else {}),
        }


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    run_id: str
    workflow_id: str
    request_hash: str
    document_id: str
    workflow_name: str
    document_snapshot: dict[str, Any]
    layout_snapshot: dict[str, Any]
    profile_id: str | None
    profile_snapshot: dict[str, Any]
    mode: RunMode
    status: RunStatus
    cleanup_state: Literal["pending", "completed"]
    started_at: datetime
    finished_at: datetime | None
    current_node_id: str | None
    event_count: int
    log_count: int
    stop_requested: bool
    error: dict[str, Any] | None
    custom_module_snapshots: dict[str, Any] = field(default_factory=dict)
    project_id: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowRunEvent:
    run_id: str
    sequence: int
    type: str
    occurred_at: datetime
    payload: dict[str, Any]
    node_id: str | None = None
    execution_id: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowArtifact:
    run_id: str
    artifact_id: str
    ordinal: int
    node_id: str
    execution_id: str | None
    relative_path: str
    size: int
    sha256: str
    mime_type: str
    purpose: str
    event_sequence: int
