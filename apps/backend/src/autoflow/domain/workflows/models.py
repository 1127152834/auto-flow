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


class WorkflowError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        issues: list[WorkflowIssue] | None = None,
    ):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.issues = issues or []


@dataclass(frozen=True)
class WorkflowRecord:
    document: dict[str, Any]
    layout: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime

    def matches(self, document: dict[str, Any], layout: dict[str, Any]) -> bool:
        # JSON equality must distinguish true from 1, including nested draft values.
        def encode(value: object) -> str:
            return json.dumps(
                value, sort_keys=True, ensure_ascii=False, allow_nan=False
            )

        return encode([self.document, self.layout]) == encode([document, layout])


class WorkflowRepository(Protocol):
    def list(self) -> list[WorkflowRecord]: ...
    def get(self, workflow_id: str) -> WorkflowRecord | None: ...
    def create(self, record: WorkflowRecord) -> WorkflowRecord: ...
    def save(
        self, record: WorkflowRecord, expected_revision: int
    ) -> WorkflowRecord: ...
