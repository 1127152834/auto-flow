from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoflow.domain.project_runs.models import (
    Batch,
    BatchCounts,
    BatchStatus,
    ProjectRunError,
    Task,
    TaskInputSnapshot,
)
from autoflow.infrastructure.database.workflow_runtime import (
    _run,  # the repository's row mapping
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow

from .project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)


class SqlAlchemyProjectRuns:
    """Project identities and projections within the caller's transaction."""

    def __init__(self, session: Session):
        self.session = session

    def batch_row(self, project_id: str, batch_id: str) -> ProjectBatchRow:
        row = self.session.get(ProjectBatchRow, batch_id)
        if row is None or row.project_id != project_id:
            raise ProjectRunError("NOT_FOUND", "批次不存在", 404)
        return row

    def list_tasks(self, project_id: str, batch_id: str) -> list[Task]:
        self.batch_row(project_id, batch_id)
        # Remediation M3 AC3-02: one query for the columns a task projection uses. Loading whole
        # run rows decoded their JSON for every task, several times per scheduler tick.
        rows = self.session.execute(
            select(
                ProjectTaskRow.id, ProjectTaskRow.run_id, ProjectTaskRow.run_request_id,
                ProjectTaskRow.created_at, ProjectTaskRow.ordinal, ProjectTaskInputSnapshotRow.id,
                WorkflowRunRow.run_request_id, WorkflowRunRow.status, WorkflowRunRow.status_revision,
                WorkflowRunRow.completed_at,
            )
            .outerjoin(ProjectTaskInputSnapshotRow, ProjectTaskInputSnapshotRow.task_id == ProjectTaskRow.id)
            .outerjoin(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
            .where(ProjectTaskRow.project_id == project_id, ProjectTaskRow.batch_id == batch_id)
            .order_by(ProjectTaskRow.ordinal)
        ).all()
        tasks = []
        for task_id, run_id, run_request_id, created_at, ordinal, snapshot_id, core_request_id, status, revision, completed_at in rows:
            if snapshot_id is None or status is None:
                raise ProjectRunError("RUN_FACTS_INCOMPLETE", "任务证据不完整，需要核验", 409)
            if core_request_id != run_request_id:
                raise ProjectRunError("RUN_IDENTITY_MISMATCH", "核心运行身份与项目任务不一致", 409)
            tasks.append(Task(
                task_id, project_id, batch_id, run_id, run_request_id, snapshot_id, status, revision,
                aware(created_at), aware(completed_at) if completed_at is not None else None, ordinal,
            ))
        return tasks

    def task(self, project_id: str, task_id: str) -> Task:
        row = self.session.get(ProjectTaskRow, task_id)
        if row is None or row.project_id != project_id:
            raise ProjectRunError("NOT_FOUND", "任务不存在", 404)
        snapshot = self.session.scalar(
            select(ProjectTaskInputSnapshotRow).where(
                ProjectTaskInputSnapshotRow.task_id == row.id
            )
        )
        return self._task(row, snapshot, self.session.get(WorkflowRunRow, row.run_id))

    def _task(self, row: ProjectTaskRow, snapshot: ProjectTaskInputSnapshotRow | None, run_row: WorkflowRunRow | None) -> Task:
        run = _run(run_row) if run_row is not None else None
        if snapshot is None or run is None:
            raise ProjectRunError(
                "RUN_FACTS_INCOMPLETE", "任务证据不完整，需要核验", 409
            )
        return Task(
            row.id,
            row.project_id,
            row.batch_id,
            row.run_id,
            row.run_request_id,
            snapshot.id,
            run.status,
            run.status_revision,
            aware(row.created_at),
            run.completed_at,
            row.ordinal,
        ).project(run)

    def snapshot(self, project_id: str, task_id: str) -> TaskInputSnapshot:
        task = self.task(project_id, task_id)
        row = self.session.get(ProjectTaskInputSnapshotRow, task.input_snapshot_id)
        assert row is not None
        return TaskInputSnapshot(
            row.id,
            row.task_id,
            row.batch_id,
            row.parameters,
            tuple(row.inputs),
            aware(row.captured_at),
        )

    def batch(self, project_id: str, batch_id: str) -> Batch:
        row = self.batch_row(project_id, batch_id)
        return batch_record(row).project_counts(self.list_tasks(project_id, batch_id))


def batch_record(row: ProjectBatchRow) -> Batch:
    return Batch(
        row.id,
        row.project_id,
        row.automation_id,
        row.start_operation_id,
        cast(BatchStatus, row.status),
        row.status_revision,
        row.automation_revision,
        row.workflow_revision,
        row.frozen_request,
        BatchCounts({}),
        aware(row.created_at),
        aware(row.completed_at) if row.completed_at else None,
        row.claim_gate_state,
        row.selection_outcome,
    )


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
