from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Any, Literal

from autoflow.domain.workflows.runtime import TERMINAL_STATUSES, CoreRun, CoreRunStatus

BatchStatus = Literal[
    "accepted",
    "running",
    "blocked",
    "draining",
    "stopping",
    "reconciling",
    "completed",
    "stopped",
    "failed",
    "interrupted",
]


class ProjectRunError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.details = details or {}


@dataclass(frozen=True)
class BatchStart:
    expected_automation_revision: int
    parameters: Mapping[str, Any]
    max_tasks: int
    concurrency: int
    environment_override: Mapping[str, Any] | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _freeze_mapping(self.parameters))
        object.__setattr__(
            self,
            "environment_override",
            _freeze_mapping(self.environment_override)
            if self.environment_override is not None
            else None,
        )


@dataclass(frozen=True)
class TaskInputSnapshot:
    input_snapshot_id: str
    task_id: str
    batch_id: str
    parameters: Mapping[str, Any]
    inputs: tuple[Mapping[str, Any], ...]
    captured_at: datetime

    def __post_init__(self) -> None:
        if self.inputs:
            raise ProjectRunError(
                "PROJECT_INPUTS_NOT_SUPPORTED",
                "当前仅支持参数型运行，任务不能包含项目数据输入快照",
                422,
            )
        object.__setattr__(self, "parameters", _freeze_mapping(self.parameters))
        object.__setattr__(self, "inputs", tuple(self.inputs))


@dataclass(frozen=True)
class Task:
    task_id: str
    project_id: str
    batch_id: str
    run_id: str
    run_request_id: str
    input_snapshot_id: str
    status: CoreRunStatus
    status_revision: int
    created_at: datetime
    completed_at: datetime | None = None

    def project(self, run: CoreRun) -> Task:
        if run.run_id != self.run_id or run.run_request_id != self.run_request_id:
            raise ProjectRunError(
                "RUN_IDENTITY_MISMATCH", "核心运行身份与项目任务不一致", 409
            )
        return replace(
            self,
            status=run.status,
            status_revision=run.status_revision,
            completed_at=run.completed_at,
        )


@dataclass(frozen=True)
class BatchCounts:
    by_status: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_status", MappingProxyType(dict(self.by_status)))

    @property
    def created_task_count(self) -> int:
        return sum(self.by_status.values())

    @property
    def active_task_count(self) -> int:
        return sum(
            count
            for status, count in self.by_status.items()
            if status not in TERMINAL_STATUSES
        )


@dataclass(frozen=True)
class Batch:
    batch_id: str
    project_id: str
    automation_id: str
    start_operation_id: str
    status: BatchStatus
    status_revision: int
    automation_revision: int
    workflow_revision: int
    frozen_request: Mapping[str, Any]
    counts: BatchCounts
    created_at: datetime
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "frozen_request", _freeze_mapping(self.frozen_request))

    @property
    def requested_count(self) -> int:
        return int(self.frozen_request["maxTasks"])

    def project_counts(self, tasks: list[Task] | tuple[Task, ...]) -> Batch:
        if any(
            task.batch_id != self.batch_id or task.project_id != self.project_id
            for task in tasks
        ):
            raise ProjectRunError(
                "TASK_OWNERSHIP_MISMATCH", "任务不属于当前批次和项目", 409
            )
        counts = {status: 0 for status in TERMINAL_STATUSES}
        for task in tasks:
            counts[task.status] = counts.get(task.status, 0) + 1
        return replace(self, counts=BatchCounts(counts))


def batch_to_dict(batch: Batch) -> dict[str, Any]:
    return {
        "batchId": batch.batch_id,
        "projectId": batch.project_id,
        "automationId": batch.automation_id,
        "startOperationId": batch.start_operation_id,
        "status": batch.status,
        "statusRevision": batch.status_revision,
        "managementRevision": batch.automation_revision,
        "requestedCount": batch.requested_count,
        "createdTaskCount": batch.counts.created_task_count,
        "activeTaskCount": batch.counts.active_task_count,
        "createdAt": batch.created_at,
        **({"completedAt": batch.completed_at} if batch.completed_at else {}),
    }


def task_to_dict(task: Task) -> dict[str, Any]:
    return {
        "taskId": task.task_id,
        "projectId": task.project_id,
        "batchId": task.batch_id,
        "runId": task.run_id,
        "runRequestId": task.run_request_id,
        "status": task.status,
        "statusRevision": task.status_revision,
        "inputSnapshotId": task.input_snapshot_id,
        "createdAt": task.created_at,
        **({"completedAt": task.completed_at} if task.completed_at else {}),
    }


def snapshot_to_dict(snapshot: TaskInputSnapshot) -> dict[str, Any]:
    return {
        "inputSnapshotId": snapshot.input_snapshot_id,
        "taskId": snapshot.task_id,
        "batchId": snapshot.batch_id,
        "parameters": dict(snapshot.parameters),
        "inputs": [dict(item) for item in snapshot.inputs],
        "capturedAt": snapshot.captured_at,
    }


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze(value) for key, value in value.items()})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value
