from __future__ import annotations

from typing import Any

from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.domain.workflows.runtime import TERMINAL_STATUSES, RunEvent, thaw_json
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.project_run_models import ProjectTaskRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from sqlalchemy.orm import Session, sessionmaker


class ProjectRunEvents:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def page(
        self, project_id: str, task_id: str, after_sequence: int = 0
    ) -> dict[str, Any]:
        if type(after_sequence) is not int or after_sequence < 0:
            raise _error("afterSequence", "必须是非负整数")
        with self._factory() as session:
            _begin_snapshot(session)
            project = session.get(ProjectRow, project_id)
            if project is None or project.lifecycle_state == "deleted":
                raise ProjectRunError("NOT_FOUND", "项目不存在", 404)
            task = session.get(ProjectTaskRow, task_id)
            if task is None or task.project_id != project_id:
                raise ProjectRunError("NOT_FOUND", "任务不存在", 404)
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            run = repository.get_run(run_id=task.run_id)
            if run is None:
                raise ProjectRunError(
                    "RUN_FACTS_INCOMPLETE", "任务证据不完整，需要核验", 409
                )
            if after_sequence > run.last_sequence:
                raise _error("afterSequence", "游标超过当前持久事件序号")
            events = repository.list_events(
                task.run_id, after_sequence=after_sequence, limit=200
            )
            expected = after_sequence + 1
            for event in events:
                if event.sequence != expected:
                    raise ProjectRunError(
                        "RUN_EVENT_HISTORY_UNAVAILABLE", "运行事件历史存在缺口", 409
                    )
                expected += 1
            cursor = events[-1].sequence if events else after_sequence
            if len(events) < 200 and cursor < run.last_sequence:
                raise ProjectRunError(
                    "RUN_EVENT_HISTORY_UNAVAILABLE", "运行事件历史存在缺口", 409
                )
            return {
                "items": [_public(event) for event in events],
                "afterSequence": cursor,
                "lastSequence": run.last_sequence,
                "hasMore": cursor < run.last_sequence,
                "terminal": run.status in TERMINAL_STATUSES,
            }


def _begin_snapshot(session: Session) -> None:
    connection = session.connection()
    if connection.dialect.name == "sqlite":
        driver = getattr(connection.connection, "driver_connection", None)
        if driver is not None and not driver.in_transaction:
            connection.exec_driver_sql("BEGIN")


def _public(event: RunEvent) -> dict[str, Any]:
    kind = "runStatus" if event.kind == "status" else event.kind
    allowed = {
        "runStatus": {"status", "statusRevision"},
        "nodeAttempt": {"status", "durationMs", "error"},
        "log": {"level", "message", "isUserLog"},
        "output": {"name", "value"},
        "artifact": {"artifactId", "kind", "purpose", "availability"},
    }
    if kind not in allowed:
        raise ProjectRunError(
            "RUN_EVENT_HISTORY_UNAVAILABLE", "运行事件类型尚不能公开补读", 409
        )
    payload = thaw_json(event.payload)
    return {
        "eventId": event.event_id,
        "runId": event.run_id,
        "sequence": event.sequence,
        "executionGeneration": event.execution_generation,
        "kind": kind,
        "nodeId": event.node_id,
        "nodeVisitId": event.node_visit_id,
        "attempt": event.attempt,
        "occurredAt": event.occurred_at,
        "payload": {key: payload[key] for key in allowed[kind] if key in payload},
    }


def _error(field: str, message: str) -> ProjectRunError:
    return ProjectRunError(
        "VALIDATION_ERROR",
        "运行事件游标无效",
        422,
        {"fields": {field: message}, "retryable": False},
    )
