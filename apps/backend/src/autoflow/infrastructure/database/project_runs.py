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
    SqlAlchemyWorkflowRuntimeRepository,
)

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
        rows = self.session.scalars(
            select(ProjectTaskRow)
            .where(
                ProjectTaskRow.project_id == project_id,
                ProjectTaskRow.batch_id == batch_id,
            )
            .order_by(ProjectTaskRow.ordinal)
        ).all()
        return [self.task(project_id, row.id) for row in rows]

    def task(self, project_id: str, task_id: str) -> Task:
        row = self.session.get(ProjectTaskRow, task_id)
        if row is None or row.project_id != project_id:
            raise ProjectRunError("NOT_FOUND", "任务不存在", 404)
        snapshot = self.session.scalar(
            select(ProjectTaskInputSnapshotRow).where(
                ProjectTaskInputSnapshotRow.task_id == row.id
            )
        )
        run = SqlAlchemyWorkflowRuntimeRepository(self.session).get_run(
            run_id=row.run_id
        )
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
