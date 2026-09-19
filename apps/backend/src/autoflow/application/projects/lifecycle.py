"""Project lifecycle use cases and their convergence loop.

Removing a project and finishing an accepted archive are management work, not
workflow work: they run on this coordinator, never on a second executor.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.domain.projects.ports import Projects

_LOG = logging.getLogger(__name__)
LIFECYCLE_KINDS = {"archiveProject", "restoreProject", "deleteProject"}


class LifecycleRepository(Protocol):
    def impact(self, project_id: str, action: str) -> dict[str, Any]: ...
    def archive(
        self,
        project_id: str,
        expected_revision: int,
        impact_revision: int,
        operation: ProjectOperation,
    ) -> ProjectOperation: ...
    def restore(
        self, project_id: str, expected_revision: int, operation: ProjectOperation
    ) -> ProjectOperation: ...
    def delete(
        self,
        project_id: str,
        confirmation_name: str,
        expected_revision: int,
        impact_revision: int,
        operation: ProjectOperation,
    ) -> ProjectOperation: ...
    def pending(self) -> list[str]: ...
    def advance(self, project_id: str) -> None: ...


class ProjectLifecycleCoordinator:
    """Advance accepted lifecycle commands until they settle or stay blocked."""

    def __init__(
        self,
        repository: LifecycleRepository,
        gate: Any,
        *,
        interval: float = 2.0,
        idle_interval: float = 30.0,
    ) -> None:
        self._repository, self._gate = repository, gate
        self._interval, self._idle_interval = interval, idle_interval
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._loop: asyncio.Task[None] | None = None
        self._closed = False

    async def startup(self) -> None:
        if self._loop is None:
            self._closed = False
            self._loop = asyncio.create_task(self._run())

    def wake(self) -> None:
        self._wake.set()

    async def shutdown(self) -> None:
        self._closed = True
        self.wake()
        if self._loop is not None:
            await self._loop
            self._loop = None

    def blockers(self) -> list[str]:
        return ["project_lifecycle_pending"] if self._repository.pending() else []

    async def tick(self) -> None:
        async with self._lock:
            if self._closed:
                return
            for project_id in self._repository.pending():
                with self._gate.mutation() as admitted:
                    if not admitted:
                        return
                    self._repository.advance(project_id)

    async def _run(self) -> None:
        while not self._closed:
            self._wake.clear()
            timeout = self._idle_interval
            try:
                if self._repository.pending():
                    timeout = self._interval
                await self.tick()
            except Exception:  # noqa: BLE001 - durable facts decide, never this loop
                _LOG.exception("Project lifecycle could not be advanced")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=timeout)
            except TimeoutError:
                pass


class ProjectLifecycleService:
    def __init__(
        self,
        projects: Projects,
        repository: LifecycleRepository,
        coordinator: ProjectLifecycleCoordinator,
    ) -> None:
        self.projects, self.repository, self.coordinator = (
            projects,
            repository,
            coordinator,
        )

    def impact(self, project_id: str, action: str) -> dict[str, Any]:
        _canonical(project_id, "projectId")
        project = self.projects.get(project_id)
        if project is None or project.lifecycle_state == "deleted":
            _missing()
        return self.repository.impact(project_id, _action(action))

    def archive(
        self, project_id: str, key: str, payload: dict[str, Any]
    ) -> ProjectOperation:
        _canonical(project_id, "projectId")
        idem = _canonical(key, "Idempotency-Key")
        body = _body(payload, {"impactRevision", "expectedManagementRevision"})
        operation = _operation(
            idem,
            "archiveProject",
            {
                "scope": "project",
                "target": project_id,
                "request": {
                    "impactRevision": _revision(body, "impactRevision"),
                    "expectedManagementRevision": _revision(
                        body, "expectedManagementRevision"
                    ),
                },
            },
            project_id,
        )
        saved = self.repository.archive(
            project_id,
            _revision(body, "expectedManagementRevision"),
            _revision(body, "impactRevision"),
            operation,
        )
        self.coordinator.wake()
        return saved

    def restore(
        self, project_id: str, key: str, payload: dict[str, Any]
    ) -> ProjectOperation:
        _canonical(project_id, "projectId")
        idem = _canonical(key, "Idempotency-Key")
        body = _body(payload, {"expectedManagementRevision"})
        expected = _revision(body, "expectedManagementRevision")
        operation = _operation(
            idem,
            "restoreProject",
            {
                "scope": "project",
                "target": project_id,
                "request": {"expectedManagementRevision": expected},
            },
            project_id,
        )
        return self.repository.restore(project_id, expected, operation)

    def delete(
        self, project_id: str, key: str, payload: dict[str, Any]
    ) -> ProjectOperation:
        _canonical(project_id, "projectId")
        idem = _canonical(key, "Idempotency-Key")
        body = _body(
            payload,
            {"confirmationName", "impactRevision", "expectedManagementRevision"},
        )
        name = body["confirmationName"]
        if not isinstance(name, str) or not name.strip():
            raise _validation("confirmationName", "Confirmation name is required")
        operation = _operation(
            idem,
            "deleteProject",
            {
                "scope": "project",
                "target": project_id,
                "request": {
                    "confirmationName": name,
                    "impactRevision": _revision(body, "impactRevision"),
                    "expectedManagementRevision": _revision(
                        body, "expectedManagementRevision"
                    ),
                },
            },
            project_id,
        )
        saved = self.repository.delete(
            project_id,
            name,
            _revision(body, "expectedManagementRevision"),
            _revision(body, "impactRevision"),
            operation,
        )
        self.coordinator.wake()
        return saved


def _operation(
    key: str, kind: str, canonical: dict[str, Any], project_id: str
) -> ProjectOperation:
    now = datetime.now(UTC)
    digest = hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    return ProjectOperation(
        str(uuid4()),
        project_id,
        key,
        kind,
        digest,
        "running",
        1,
        {"type": "project", "projectId": project_id},
        None,
        None,
        now,
        now,
        None,
    )


def _body(payload: dict[str, Any], required: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != required:
        raise _validation("form", "Invalid lifecycle request")
    return payload


def _revision(payload: dict[str, Any], field: str) -> int:
    value = payload[field]
    if type(value) is not int or value < 1:
        raise _validation(field, "Must be a positive integer")
    return value


def _action(action: Any) -> str:
    if action not in {"archive", "delete"}:
        raise _validation("action", "Must be archive or delete")
    return action


def _canonical(value: Any, field: str) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError) as error:
        raise _validation(field, "Must be a canonical UUID") from error
    return value


def _missing():
    raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)


def _validation(field: str, message: str) -> ProjectError:
    return ProjectError(
        "VALIDATION_ERROR",
        "Request validation failed",
        422,
        {
            "fields": {field: message},
            "domainCode": "validation_error",
            "retryable": False,
        },
    )
