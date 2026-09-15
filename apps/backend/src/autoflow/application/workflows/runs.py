from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
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

    def finish(
        self,
        run_id: str,
        *,
        status: TerminalRunStatus,
        error: dict[str, Any] | None,
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
            raise WorkflowRunError("RUN_REQUEST_INVALID", "运行标识、工作流和浏览器配置不能为空", 422)
        if start.mode not in {"run", "debug"}:
            raise WorkflowRunError("RUN_REQUEST_INVALID", "运行模式无效", 422)
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
    ) -> WorkflowRun:
        if not cleanup_completed:
            raise WorkflowRunError(
                "RUN_CLEANUP_INCOMPLETE", "浏览器与进程清理完成前不能结束运行"
            )
        return self._repository.finish(
            run_id, status=status, error=copy.deepcopy(error), now=self._clock()
        )

    def recover_interrupted(self) -> tuple[WorkflowRun, ...]:
        return self._repository.recover_interrupted(now=self._clock())
