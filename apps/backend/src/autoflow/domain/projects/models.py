from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any


class ProjectError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.details = details or {}


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    name: str
    description: str
    default_resources: dict[str, Any]
    management_revision: int
    lifecycle_state: str
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None = None

    def patched(self, patch: dict[str, Any], now: datetime) -> ProjectRecord:
        values = {
            "name": patch.get("name", self.name),
            "description": patch.get("description", self.description),
            "default_resources": patch.get("defaultResources", self.default_resources),
        }
        changed = any(getattr(self, key) != value for key, value in values.items())
        return replace(
            self,
            **values,
            management_revision=self.management_revision + int(changed),
            updated_at=now if changed else self.updated_at,
        )

    def opened(self, now: datetime) -> ProjectRecord:
        return replace(self, last_opened_at=now)


@dataclass(frozen=True)
class ProjectOperation:
    operation_id: str
    project_id: str | None
    idempotency_key: str
    kind: str
    request_digest: str
    status: str
    status_revision: int
    resource: dict[str, Any]
    result: dict[str, Any] | None
    error: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    def with_result(self, project_id: str, project: ProjectRecord) -> ProjectOperation:
        completed_at = datetime.now(UTC)
        return replace(
            self,
            project_id=project_id,
            status="succeeded",
            status_revision=2,
            result=project_to_dict(project),
            updated_at=completed_at,
            completed_at=completed_at,
        )


def project_to_dict(value: ProjectRecord) -> dict[str, Any]:
    return {
        "projectId": value.project_id,
        "name": value.name,
        "description": value.description,
        "managementRevision": value.management_revision,
        "lifecycleState": value.lifecycle_state,
        "defaultResources": value.default_resources,
        "createdAt": value.created_at,
        "updatedAt": value.updated_at,
        "lastOpenedAt": value.last_opened_at,
    }
