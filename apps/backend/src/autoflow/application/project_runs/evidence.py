from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.domain.workflows.runtime import RunArtifact, RunEvent, thaw_json
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.project_run_models import ProjectTaskRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)

from .presentation import prepared_node_names


class ProjectRunEvidence:
    """Read persisted core events through a project-scoped task identity."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        workspace_root: Path | None = None,
    ) -> None:
        self._factory = session_factory
        self._workspace_root = workspace_root.resolve() if workspace_root else None

    def artifacts(
        self, project_id: str, task_id: str, *, page: int = 1, page_size: int = 50
    ) -> tuple[list[RunArtifact], int]:
        _page(page, page_size)
        with self._factory() as session:
            task = _task(session, project_id, task_id)
            return SqlAlchemyWorkflowRuntimeRepository(session).list_artifacts(
                task.run_id, offset=(page - 1) * page_size, limit=page_size
            )

    def artifact(self, project_id: str, task_id: str, artifact_id: str) -> RunArtifact:
        with self._factory() as session:
            task = _task(session, project_id, task_id)
            artifact = SqlAlchemyWorkflowRuntimeRepository(session).get_artifact(
                task.run_id, artifact_id
            )
            if artifact is None:
                raise ProjectRunError("NOT_FOUND", "运行产物不存在", 404)
            return artifact

    def artifact_content(
        self, project_id: str, task_id: str, artifact_id: str
    ) -> tuple[bytes, str]:
        artifact = self.artifact(project_id, task_id, artifact_id)
        if (
            artifact.availability != "available"
            or artifact.relative_path is None
            or artifact.media_type is None
            or artifact.byte_size is None
            or artifact.sha256 is None
            or self._workspace_root is None
        ):
            raise _artifact_unavailable()
        try:
            path = (self._workspace_root / artifact.relative_path).resolve(strict=True)
            path.relative_to(self._workspace_root)
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
            descriptor = os.open(path, flags)
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_size != artifact.byte_size:
                    raise OSError
                content = bytearray()
                while chunk := os.read(
                    descriptor, min(1024 * 1024, artifact.byte_size + 1)
                ):
                    content.extend(chunk)
                    if len(content) > artifact.byte_size:
                        raise OSError
            finally:
                os.close(descriptor)
        except (OSError, RuntimeError, ValueError):
            raise _artifact_unavailable() from None
        if (
            len(content) != artifact.byte_size
            or hashlib.sha256(content).hexdigest() != artifact.sha256
        ):
            raise _artifact_unavailable()
        return bytes(content), artifact.media_type

    def node_names(self, project_id: str, task_id: str) -> dict[str, str]:
        with self._factory() as session:
            task = _task(session, project_id, task_id)
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            run = repository.get_run(run_id=task.run_id)
            if run is None:
                raise ProjectRunError(
                    "RUN_FACTS_INCOMPLETE", "任务证据不完整，需要核验", 409
                )
            return _node_names(repository, run.prepared_content_id)

    def logs(
        self,
        project_id: str,
        task_id: str,
        *,
        after_sequence: int = 0,
        level: str | None = None,
        node_id: str | None = None,
        query: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        _cursor(after_sequence, page_size)
        if level is not None and level not in {"debug", "info", "warning", "error"}:
            raise _field("level", "未知日志级别")
        normalized_query = query.strip().casefold() if query else None
        with self._factory() as session:
            session.execute(
                text("BEGIN")
            )  # one read snapshot for cursor, events and core status
            task = _task(session, project_id, task_id)
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            run = repository.get_run(run_id=task.run_id)
            if run is None:
                raise ProjectRunError(
                    "RUN_FACTS_INCOMPLETE", "任务证据不完整，需要核验", 409
                )
            node_names = _node_names(repository, run.prepared_content_id)
            matches = _matching_events(
                repository,
                task.run_id,
                after_sequence,
                page_size + 1,
                lambda event: (
                    event.kind == "log"
                    and (node_id is None or event.node_id == node_id)
                    and (level is None or event.payload.get("level") == level)
                    and (
                        normalized_query is None
                        or normalized_query
                        in str(event.payload.get("message", "")).casefold()
                    )
                ),
            )
            items = [_log(event, node_names) for event in matches[:page_size]]
            return {
                "items": items,
                "afterSequence": items[-1]["sequence"] if items else run.last_sequence,
                "lastSequence": run.last_sequence,
                "hasMore": len(matches) > page_size,
            }

    def node_attempts(
        self, project_id: str, task_id: str, *, page: int = 1, page_size: int = 50
    ) -> tuple[list[dict[str, Any]], int]:
        _page(page, page_size)
        with self._factory() as session:
            session.execute(
                text("BEGIN")
            )  # one read snapshot for cursor, events and core status
            task = _task(session, project_id, task_id)
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            run = repository.get_run(run_id=task.run_id)
            if run is None:
                raise ProjectRunError(
                    "RUN_FACTS_INCOMPLETE", "任务证据不完整，需要核验", 409
                )
            node_names = _node_names(repository, run.prepared_content_id)
            events = _all_events(repository, task.run_id)
            attempts: dict[tuple[str, int], dict[str, Any]] = {}
            for event in events:
                if event.kind != "nodeAttempt":
                    continue
                if not event.node_visit_id or event.attempt is None:
                    raise _history_unavailable()
                payload = thaw_json(event.payload)
                status = payload.get("status")
                if (
                    status not in {"started", "succeeded", "failed"}
                    or not event.node_id
                ):
                    raise _history_unavailable()
                key = (event.node_visit_id, event.attempt)
                item = attempts.setdefault(
                    key,
                    {
                        "nodeVisitId": event.node_visit_id,
                        "nodeId": event.node_id,
                        "nodeName": node_names.get(event.node_id, "未命名节点"),
                        "attempt": event.attempt,
                        "status": "running",
                        "startedAt": None,
                        "completedAt": None,
                        "error": None,
                    },
                )
                if status == "started":
                    if item["startedAt"] is not None:
                        raise _history_unavailable()
                    item["startedAt"] = event.occurred_at
                else:
                    if (
                        item["startedAt"] is None
                        or item["completedAt"] is not None
                        or item["nodeId"] != event.node_id
                    ):
                        raise _history_unavailable()
                    item["status"] = status
                    item["completedAt"] = event.occurred_at
                    item["error"] = payload.get("error")
            ordered = sorted(
                attempts.values(),
                key=lambda item: (
                    item["startedAt"] or item["completedAt"],
                    item["nodeVisitId"],
                ),
            )
            start = (page - 1) * page_size
            return ordered[start : start + page_size], len(ordered)

    def outputs(
        self, project_id: str, task_id: str, *, page: int = 1, page_size: int = 50
    ) -> tuple[list[dict[str, Any]], int]:
        _page(page, page_size)
        with self._factory() as session:
            session.execute(
                text("BEGIN")
            )  # one read snapshot for cursor, events and core status
            task = _task(session, project_id, task_id)
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            run = repository.get_run(run_id=task.run_id)
            if run is None:
                raise ProjectRunError(
                    "RUN_FACTS_INCOMPLETE", "任务证据不完整，需要核验", 409
                )
            node_names = _node_names(repository, run.prepared_content_id)
            events = [
                event
                for event in _all_events(repository, task.run_id)
                if event.kind == "output"
            ]
            values = [_output(event, node_names) for event in events]
            start = (page - 1) * page_size
            return values[start : start + page_size], len(values)


def _task(session: Session, project_id: str, task_id: str) -> ProjectTaskRow:
    project = session.get(ProjectRow, project_id)
    if project is None or project.lifecycle_state == "deleted":
        raise ProjectRunError("NOT_FOUND", "项目不存在", 404)
    task = session.get(ProjectTaskRow, task_id)
    if task is None or task.project_id != project_id:
        raise ProjectRunError("NOT_FOUND", "任务不存在", 404)
    return task


def _checked_events(repository, run_id, cursor):
    run = repository.get_run(run_id=run_id)
    if run is None or cursor > run.last_sequence:
        raise _history_unavailable()
    while cursor < run.last_sequence:
        chunk = repository.list_events(run_id, after_sequence=cursor, limit=200)
        if not chunk:
            raise _history_unavailable()
        for event in chunk:
            if event.sequence != cursor + 1 or event.sequence > run.last_sequence:
                raise _history_unavailable()
            cursor = event.sequence
            yield event


def _all_events(
    repository: SqlAlchemyWorkflowRuntimeRepository, run_id: str
) -> list[RunEvent]:
    return list(_checked_events(repository, run_id, 0))


def _matching_events(repository, run_id, cursor, limit, predicate):
    result = []
    for event in _checked_events(repository, run_id, cursor):
        if event.kind == "log":
            _log(event, {})  # malformed log evidence must not disappear behind a filter
        if predicate(event):
            result.append(event)
            if len(result) == limit:
                break
    return result


def _log(event: RunEvent, node_names: dict[str, str]) -> dict[str, Any]:
    payload = thaw_json(event.payload)
    if payload.get("level") not in {
        "debug",
        "info",
        "warning",
        "error",
    } or not isinstance(payload.get("message"), str):
        raise _history_unavailable()
    return {
        "runId": event.run_id,
        "sequence": event.sequence,
        "eventId": event.event_id,
        "executionGeneration": event.execution_generation,
        "nodeId": event.node_id,
        "nodeName": node_names.get(event.node_id, "未命名节点")
        if event.node_id
        else None,
        "nodeVisitId": event.node_visit_id,
        "attempt": event.attempt,
        "level": payload["level"],
        "message": payload["message"],
        "occurredAt": event.occurred_at,
    }


def _output(event: RunEvent, node_names: dict[str, str]) -> dict[str, Any]:
    payload = thaw_json(event.payload)
    if not isinstance(payload.get("name"), str) or "value" not in payload:
        raise _history_unavailable()
    return {
        "outputId": event.event_id,
        "kind": "value",
        "name": payload["name"],
        "value": payload["value"],
        "runId": event.run_id,
        "sequence": event.sequence,
        "nodeId": event.node_id,
        "nodeName": node_names.get(event.node_id, "未命名节点")
        if event.node_id
        else None,
        "nodeVisitId": event.node_visit_id,
        "attempt": event.attempt,
        "createdAt": event.occurred_at,
    }


def _node_names(
    repository: SqlAlchemyWorkflowRuntimeRepository, prepared_content_id: str
) -> dict[str, str]:
    return prepared_node_names(
        repository.get_prepared_content(prepared_content_id=prepared_content_id)
    )


def _cursor(after_sequence: int, page_size: int) -> None:
    if type(after_sequence) is not int or after_sequence < 0:
        raise _field("afterSequence", "必须是非负整数")
    _page(1, page_size)


def _page(page: int, page_size: int) -> None:
    if type(page) is not int or not 1 <= page <= 2_147_483_647:
        raise _field("page", "超出允许范围")
    if type(page_size) is not int or not 1 <= page_size <= 200:
        raise _field("pageSize", "必须是 1–200 的整数")


def _field(field: str, message: str) -> ProjectRunError:
    return ProjectRunError(
        "VALIDATION_ERROR",
        "证据查询参数无效",
        422,
        {"fields": {field: message}, "retryable": False},
    )


def _history_unavailable() -> ProjectRunError:
    return ProjectRunError(
        "RUN_EVENT_HISTORY_UNAVAILABLE", "运行事件历史不完整，无法还原证据", 409
    )


def _artifact_unavailable() -> ProjectRunError:
    return ProjectRunError("RUN_ARTIFACT_UNAVAILABLE", "运行产物当前不可读取", 409)
