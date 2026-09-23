from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, Protocol

from autoflow.domain.workflows.runs import (
    TerminalRunStatus,
    WorkflowArtifact,
    WorkflowRun,
    WorkflowRunError,
    WorkflowRunEvent,
    WorkflowRunStart,
)

_SENSITIVE_PROFILE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "license",
        "licensekey",
        "password",
        "proxycredentials",
        "secret",
        "token",
    }
)


class WorkflowRunRepository(Protocol):
    def create(
        self, start: WorkflowRunStart, *, request_hash: str, now: datetime
    ) -> WorkflowRun: ...

    def get(self, run_id: str) -> WorkflowRun | None: ...

    def append_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        now: datetime,
        node_id: str | None = None,
        execution_id: str | None = None,
        run_patch: dict[str, Any] | None = None,
        artifact_ids: tuple[str, ...] = (),
    ) -> WorkflowRunEvent: ...

    def list_events(
        self, run_id: str, after_sequence: int, limit: int
    ) -> tuple[WorkflowRunEvent, ...]: ...

    def list_runs(
        self, *, document_id: str | None, cursor: int, limit: int
    ) -> tuple[tuple[WorkflowRun, ...], int, int | None]: ...

    def finish(
        self,
        run_id: str,
        *,
        status: TerminalRunStatus,
        error: dict[str, Any] | None,
        terminal_log: dict[str, Any] | None,
        now: datetime,
    ) -> WorkflowRun: ...

    def recover_interrupted(self, *, now: datetime) -> tuple[WorkflowRun, ...]: ...

    def register_artifact(
        self,
        *,
        run_id: str,
        artifact_id: str,
        node_id: str,
        execution_id: str | None,
        relative_path: str,
        size: int,
        sha256: str,
        mime_type: str,
        purpose: str,
    ) -> WorkflowArtifact: ...

    def list_artifacts(
        self, run_id: str, *, cursor: int, limit: int
    ) -> tuple[WorkflowArtifact, ...]: ...

    def get_artifact(
        self, run_id: str, artifact_id: str
    ) -> WorkflowArtifact | None: ...

    def save_debug_command(
        self,
        run_id: str,
        command_id: str,
        *,
        request_hash: str,
        receipt: dict[str, Any],
        http_status: int,
    ) -> tuple[str, dict[str, Any], int]: ...

    def get_debug_command(
        self, command_id: str
    ) -> tuple[str, dict[str, Any], int] | None: ...

    def clear_variable_tracking(
        self, run_id: str, *, now: datetime
    ) -> WorkflowRunEvent: ...


def _sanitize_profile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_profile(item)
            for key, item in value.items()
            if key.lower().replace("_", "") not in _SENSITIVE_PROFILE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_profile(item) for item in value]
    return copy.deepcopy(value)


def _request_hash(start: WorkflowRunStart) -> str:
    encoded = json.dumps(
        start.request_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class WorkflowRunService:
    def __init__(
        self,
        repository: WorkflowRunRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    def start(self, start: WorkflowRunStart) -> WorkflowRun:
        if not start.run_id or not start.workflow_id or not start.profile_id:
            raise WorkflowRunError(
                "RUN_REQUEST_INVALID", "运行标识、工作流和浏览器配置不能为空", 422
            )
        if start.mode not in {"run", "debug"}:
            raise WorkflowRunError("RUN_REQUEST_INVALID", "运行模式无效", 422)
        if start.project_id is not None and (
            not isinstance(start.project_id, str)
            or not start.project_id.strip()
            or len(start.project_id) > 200
        ):
            raise WorkflowRunError("RUN_REQUEST_INVALID", "项目标识无效", 422)
        sanitized = WorkflowRunStart(
            run_id=start.run_id,
            workflow_id=start.workflow_id,
            document_id=start.document_id,
            workflow_name=start.workflow_name,
            document_snapshot=copy.deepcopy(start.document_snapshot),
            layout_snapshot=copy.deepcopy(start.layout_snapshot),
            profile_id=start.profile_id,
            profile_snapshot=_sanitize_profile(start.profile_snapshot),
            mode=start.mode,
            custom_module_snapshots=copy.deepcopy(start.custom_module_snapshots),
            project_id=start.project_id,
        )
        return self._repository.create(
            sanitized,
            request_hash=_request_hash(start),
            now=self._clock(),
        )

    def get(self, run_id: str) -> WorkflowRun:
        run = self._repository.get(run_id)
        if run is None:
            raise WorkflowRunError("RUN_NOT_FOUND", "运行记录不存在", 404)
        return run

    def events(
        self, run_id: str, *, after_sequence: int = 0, limit: int = 200
    ) -> tuple[WorkflowRunEvent, ...]:
        if after_sequence < 0 or limit < 1 or limit > 1000:
            raise WorkflowRunError("RUN_EVENT_PAGE_INVALID", "事件分页参数无效", 422)
        self.get(run_id)
        return self._repository.list_events(run_id, after_sequence, limit)

    def list_runs(
        self, *, document_id: str | None, cursor: int, limit: int
    ) -> tuple[tuple[WorkflowRun, ...], int, int | None]:
        if cursor < 0 or limit < 1 or limit > 200:
            raise WorkflowRunError("RUN_PAGE_INVALID", "运行分页参数无效", 422)
        return self._repository.list_runs(
            document_id=document_id, cursor=cursor, limit=limit
        )

    def logs(
        self,
        run_id: str,
        *,
        cursor: int,
        limit: int,
        query: str | None,
        levels: tuple[str, ...],
        node_id: str | None,
    ) -> tuple[list[dict[str, Any]], int, int | None]:
        if cursor < 0 or limit < 1 or limit > 500:
            raise WorkflowRunError("RUN_LOG_PAGE_INVALID", "日志分页参数无效", 422)
        allowed = {"debug", "info", "success", "warning", "error"}
        if any(level not in allowed for level in levels):
            raise WorkflowRunError("RUN_LOG_FILTER_INVALID", "日志级别无效", 422)
        rows = self.all_logs(
            run_id,
            query=query,
            levels=levels,
            node_id=node_id,
        )
        total = len(rows)
        end = max(0, total - cursor)
        start = max(0, end - limit)
        page = rows[start:end]
        next_cursor = cursor + len(page) if start > 0 else None
        return page, total, next_cursor

    def all_logs(
        self,
        run_id: str,
        *,
        query: str | None,
        levels: tuple[str, ...],
        node_id: str | None,
        execution_id: str | None = None,
        through_sequence: int | None = None,
    ) -> list[dict[str, Any]]:
        return list(
            self.iter_logs(
                run_id,
                query=query,
                levels=levels,
                node_id=node_id,
                execution_id=execution_id,
                through_sequence=through_sequence,
            )
        )

    def iter_logs(
        self,
        run_id: str,
        *,
        query: str | None,
        levels: tuple[str, ...],
        node_id: str | None,
        execution_id: str | None = None,
        through_sequence: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        allowed = {"debug", "info", "success", "warning", "error"}
        if any(level not in allowed for level in levels):
            raise WorkflowRunError("RUN_LOG_FILTER_INVALID", "日志级别无效", 422)
        self.get(run_id)
        needle = query.casefold() if query else None

        def rows() -> Iterator[dict[str, Any]]:
            after_sequence = 0
            while True:
                events = self._repository.list_events(run_id, after_sequence, 1000)
                if not events:
                    return
                for event in events:
                    if through_sequence is not None and event.sequence > through_sequence:
                        return
                    if event.type != "execution:log":
                        continue
                    payload = event.payload
                    level = str(payload.get("level", "info"))
                    message = str(payload.get("message", ""))
                    event_node_id = event.node_id or payload.get("nodeId")
                    if levels and level not in levels:
                        continue
                    if node_id and event_node_id != node_id:
                        continue
                    if execution_id and event.execution_id != execution_id:
                        continue
                    if needle and needle not in message.casefold():
                        continue
                    yield {
                        "sequence": event.sequence,
                        "id": str(payload.get("id") or f"{run_id}-{event.sequence}"),
                        "timestamp": event.occurred_at.isoformat(),
                        "level": level,
                        "message": message,
                        "nodeId": event_node_id,
                        "executionId": event.execution_id,
                        "executionContext": copy.deepcopy(payload.get("executionContext")),
                        "duration": payload.get("duration"),
                        "details": copy.deepcopy(payload.get("details")),
                    }
                after_sequence = events[-1].sequence
                if (
                    through_sequence is not None and after_sequence >= through_sequence
                ) or len(events) < 1000:
                    return

        return rows()

    def event_cutoff(self, run_id: str) -> int:
        self.get(run_id)
        after_sequence = 0
        while True:
            events = self._repository.list_events(run_id, after_sequence, 1000)
            if not events:
                return after_sequence
            after_sequence = events[-1].sequence
            if len(events) < 1000:
                return after_sequence

    def variable_tracking(
        self,
        run_id: str,
        *,
        cursor: int = 0,
        limit: int = 100,
        through_sequence: int | None = None,
        query: str | None = None,
        variable: str | None = None,
        operation: str | None = None,
        value_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int, int | None, int]:
        if cursor < 0 or limit < 1 or limit > 500:
            raise WorkflowRunError(
                "RUN_VARIABLE_PAGE_INVALID", "变量诊断分页参数无效", 422
            )
        if operation not in {None, "create", "update", "scope_exit"}:
            raise WorkflowRunError(
                "RUN_VARIABLE_FILTER_INVALID", "变量诊断操作筛选无效", 422
            )
        rows, maximum = self._variable_tracking_rows(run_id)
        through = maximum if through_sequence is None else through_sequence
        if through < 0 or through > maximum:
            raise WorkflowRunError(
                "RUN_VARIABLE_CURSOR_INVALID", "变量诊断截止位置无效", 422
            )
        needle = query.casefold() if query else None
        filtered = [
            row
            for row in rows
            if row["sequence"] <= through
            and (variable is None or row["variable_name"] == variable)
            and (operation is None or row["operation"] == operation)
            and (value_type is None or row["value_type"] == value_type)
            and (
                needle is None
                or needle
                in json.dumps(row, ensure_ascii=False, separators=(",", ":")).casefold()
            )
        ]
        page = filtered[cursor : cursor + limit]
        next_cursor = cursor + len(page) if cursor + len(page) < len(filtered) else None
        return copy.deepcopy(page), len(filtered), next_cursor, through

    def variable_tracking_value(
        self, run_id: str, *, sequence: int, side: str
    ) -> Any:
        if side not in {"old_value", "new_value"}:
            raise WorkflowRunError(
                "RUN_VARIABLE_VALUE_INVALID", "变量诊断值方向无效", 422
            )
        rows, _ = self._variable_tracking_rows(run_id)
        row = next((item for item in rows if item["sequence"] == sequence), None)
        if row is None:
            raise WorkflowRunError(
                "RUN_VARIABLE_NOT_FOUND", "变量诊断记录不存在", 404
            )
        return copy.deepcopy(row[side])

    def clear_variable_tracking(self, run_id: str) -> None:
        self.get(run_id)
        self._repository.clear_variable_tracking(run_id, now=self._clock())

    def _variable_tracking_rows(
        self, run_id: str
    ) -> tuple[list[dict[str, Any]], int]:
        self.get(run_id)
        events = self._repository.list_events(run_id, 0, 1_000_000)
        relevant = [
            event
            for event in events
            if event.type
            in {"execution:variable_changed", "execution:variables_cleared"}
        ]
        maximum = relevant[-1].sequence if relevant else 0
        cleared_after = max(
            (
                event.sequence
                for event in relevant
                if event.type == "execution:variables_cleared"
            ),
            default=0,
        )
        rows: list[dict[str, Any]] = []
        for event in relevant:
            if event.type != "execution:variable_changed" or event.sequence <= cleared_after:
                continue
            payload = event.payload
            rows.append(
                {
                    "sequence": event.sequence,
                    "executionId": event.execution_id
                    or str(payload.get("executionId") or f"{run_id}-{event.sequence}"),
                    "timestamp": event.occurred_at.isoformat(),
                    "variable_name": str(payload.get("variable_name") or ""),
                    "old_value": copy.deepcopy(payload.get("old_value")),
                    "new_value": copy.deepcopy(payload.get("new_value")),
                    "node_id": event.node_id or str(payload.get("node_id") or ""),
                    "node_name": str(payload.get("node_name") or ""),
                    "operation": str(payload.get("operation") or "update"),
                    "value_type": str(payload.get("value_type") or "unknown"),
                }
            )
        return rows, maximum

    def results(self, run_id: str) -> list[dict[str, Any]]:
        self.get(run_id)
        rows: list[dict[str, Any]] = []
        after_sequence = 0
        while True:
            events = self._repository.list_events(run_id, after_sequence, 1000)
            for event in events:
                if event.type != "execution:node-succeeded" or not event.node_id:
                    continue
                result = event.payload.get("result")
                if not isinstance(result, dict) or result.get("data") is None:
                    continue
                data = copy.deepcopy(result["data"])
                values = data if isinstance(data, dict) else {"value": data}
                row = {
                    "sequence": event.sequence,
                    "nodeId": event.node_id,
                    "executionId": event.execution_id
                    or f"{run_id}-{event.sequence}",
                    "values": values,
                }
                execution_context = event.payload.get("executionContext")
                if isinstance(execution_context, dict):
                    row["executionContext"] = copy.deepcopy(execution_context)
                rows.append(row)
            if len(events) < 1000:
                break
            after_sequence = events[-1].sequence
        return rows

    def artifacts(
        self, run_id: str, *, cursor: int, limit: int
    ) -> tuple[tuple[WorkflowArtifact, ...], int | None]:
        if cursor < 0 or limit < 1 or limit > 500:
            raise WorkflowRunError("RUN_ARTIFACT_PAGE_INVALID", "产物分页参数无效", 422)
        self.get(run_id)
        items = self._repository.list_artifacts(run_id, cursor=cursor, limit=limit + 1)
        page = items[:limit]
        return page, page[-1].ordinal if len(items) > limit and page else None

    def artifact(self, run_id: str, artifact_id: str) -> WorkflowArtifact:
        self.get(run_id)
        artifact = self._repository.get_artifact(run_id, artifact_id)
        if artifact is None:
            raise WorkflowRunError("ARTIFACT_NOT_FOUND", "运行产物不存在", 404)
        return artifact

    def mark_running(self, run_id: str) -> WorkflowRunEvent:
        self.get(run_id)
        return self._repository.append_event(
            run_id,
            "execution:running",
            {},
            now=self._clock(),
            run_patch={"status": "running"},
        )

    def request_stop(self, run_id: str) -> WorkflowRunEvent:
        run = self.get(run_id)
        if run.status in {"completed", "failed", "stopped", "interrupted"}:
            return self._repository.list_events(run_id, 0, 1000)[-1]
        return self._repository.append_event(
            run_id,
            "execution:stop-requested",
            {},
            now=self._clock(),
            run_patch={"stopRequested": True},
        )

    def record_node_success(
        self,
        run_id: str,
        *,
        node_id: str,
        execution_id: str,
        result: dict[str, Any],
        artifact_ids: tuple[str, ...] = (),
    ) -> WorkflowRunEvent:
        return self._repository.append_event(
            run_id,
            "execution:node-succeeded",
            {"result": copy.deepcopy(result)},
            now=self._clock(),
            node_id=node_id,
            execution_id=execution_id,
            run_patch={"currentNodeId": node_id},
            artifact_ids=artifact_ids,
        )

    def finish(
        self,
        run_id: str,
        *,
        status: TerminalRunStatus,
        cleanup_completed: bool,
        error: dict[str, Any] | None = None,
        terminal_log: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        if not cleanup_completed:
            raise WorkflowRunError(
                "RUN_CLEANUP_INCOMPLETE", "浏览器与进程清理完成前不能结束运行"
            )
        return self._repository.finish(
            run_id,
            status=status,
            error=copy.deepcopy(error),
            terminal_log=copy.deepcopy(terminal_log),
            now=self._clock(),
        )

    def recover_interrupted(self) -> tuple[WorkflowRun, ...]:
        return self._repository.recover_interrupted(now=self._clock())
