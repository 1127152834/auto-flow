from __future__ import annotations

import builtins
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class WorkflowIssue:
    node_id: str | None
    path: list[str]
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id,
            "path": self.path,
            "code": self.code,
            "message": self.message,
        }


class WorkflowError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        issues: list[WorkflowIssue] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.issues = issues or []
        self.details = dict(details or {})
        if self.issues:
            self.details.setdefault("issues", [issue.to_dict() for issue in self.issues])


@dataclass(frozen=True)
class WorkflowRecord:
    document: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime
    project_id: str | None = None

    @property
    def workflow_id(self) -> str:
        return str(self.document["id"])

    @property
    def name(self) -> str:
        return str(self.document["content"]["name"])

    def matches(self, document: dict[str, Any]) -> bool:
        return canonical_json(self.document) == canonical_json(document)


@dataclass(frozen=True)
class WorkflowSaveOperation:
    save_operation_id: str
    workflow_id: str
    request_digest: str
    record: WorkflowRecord


@dataclass(frozen=True)
class LegacyWorkflowRecord:
    workflow_id: str
    name: str
    document: object
    layout: object
    revision: int
    created_at: datetime
    updated_at: datetime


class WorkflowRepository(Protocol):
    def list(self) -> list[WorkflowRecord]: ...
    def list_legacy(self) -> builtins.list[LegacyWorkflowRecord]: ...
    def get(self, workflow_id: str) -> WorkflowRecord | None: ...
    def get_legacy(self, workflow_id: str) -> LegacyWorkflowRecord | None: ...
    def save(
        self,
        document: dict[str, Any],
        expected_revision: int,
        save_operation_id: str,
        request_digest: str,
        now: datetime,
    ) -> WorkflowSaveOperation: ...
    def get_save_operation(
        self, save_operation_id: str
    ) -> WorkflowSaveOperation | None: ...


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
