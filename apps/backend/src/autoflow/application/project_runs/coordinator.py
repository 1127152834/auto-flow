from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.domain.project_automations.models import (
    AutomationRecord,
    automation_to_dict,
)
from autoflow.domain.project_runs.models import (
    Batch,
    BatchCounts,
    ProjectRunError,
    batch_to_dict,
)
from autoflow.domain.project_runs.rules import validate_batch_start
from autoflow.domain.projects.models import ProjectOperation
from autoflow.domain.workflows.runtime import TERMINAL_STATUSES, thaw_json
from autoflow.infrastructure.database.models import (
    ProjectOperationRow,
    ProjectRow,
    WorkflowDocumentRow,
)
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_automations import (
    _record as automation_record,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.project_runs import (
    SqlAlchemyProjectRuns,
    batch_record,
)
from autoflow.infrastructure.database.projects import (
    _json_dates,
    _operation,
    _operation_row,
)


class ProjectRunCoordinator:
    """Accept finite parameter batches atomically; never execute inside the UoW."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        core_runtime: WorkflowRuntimeService,
        *,
        resolve_resources: Callable[[AutomationRecord, dict[str, Any]], dict[str, Any]],
        available_capabilities: Sequence[str],
    ) -> None:
        self._factory, self._core = session_factory, core_runtime
        self._resolve_resources = resolve_resources
        self._capabilities = tuple(available_capabilities)

    def start(
        self, project_id: str, automation_id: str, key: str, payload: dict[str, Any]
    ) -> tuple[Batch, ProjectOperation, bool]:
        try:
            if str(UUID(key)) != key:
                raise ValueError
            digest = hashlib.sha256(
                json.dumps(
                    {
                        "kind": "startBatch",
                        "projectId": project_id,
                        "automationId": automation_id,
                        "request": payload,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
        except (TypeError, ValueError, OverflowError) as exc:
            raise ProjectRunError(
                "VALIDATION_ERROR", "操作身份或请求格式无效", 422
            ) from exc
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            project = self._project(session, project_id)
            existing = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            if existing is not None:
                if (
                    existing.project_id != project_id
                    or existing.kind != "startBatch"
                    or existing.request_digest != digest
                ):
                    raise ProjectRunError(
                        "OPERATION_PAYLOAD_MISMATCH", "同一操作身份已用于其他请求", 409
                    )
                result = existing.result
                if not result or "batch" not in result:
                    raise ProjectRunError(
                        "OPERATION_RESULT_UNKNOWN", "启动结果需要核验", 409
                    )
                saved = result["batch"]
                saved_row = SqlAlchemyProjectRuns(session).batch_row(
                    project_id, saved["batchId"]
                )
                # Return the original acceptance snapshot, never today's live counts.
                batch = replace(
                    batch_record(saved_row),
                    status="accepted",
                    status_revision=saved["statusRevision"],
                    counts=BatchCounts(
                        {
                            **dict.fromkeys(TERMINAL_STATUSES, 0),
                            "queued": saved["createdTaskCount"],
                        }
                    ),
                    completed_at=None,
                )
                return batch, _operation(existing), True
            if project.lifecycle_state == "closing":
                raise ProjectRunError("PROJECT_CLOSING", "项目正在关闭", 423)
            if project.lifecycle_state != "active":
                raise ProjectRunError(
                    "LIFECYCLE_CONFLICT", "当前项目只读，不能启动运行", 409
                )
            row = session.get(ProjectAutomationRow, automation_id)
            if row is None or row.project_id != project_id:
                raise ProjectRunError("NOT_FOUND", "自动化不存在", 404)
            automation = automation_record(row)
            start = validate_batch_start(automation, payload)
            effective = (
                replace(
                    automation, environment_policy=thaw_json(start.environment_override)
                )
                if start.environment_override is not None
                else automation
            )
            resources = self._resolve_resources(
                effective, dict(project.default_resources)
            )
            workflow = session.get(WorkflowDocumentRow, automation.workflow_id)
            if workflow is None:
                raise ProjectRunError("NOT_FOUND", "关联工作流不存在", 404)
            now, batch_id, operation_id = datetime.now(UTC), str(uuid4()), str(uuid4())
            prepared = self._core.prepare_content(
                prepare_operation_id=operation_id,
                workflow_id=workflow.id,
                source_revision=workflow.revision,
                available_capabilities=list(self._capabilities),
                created_at=now,
                uow=session,
            )
            frozen = _json_dates(
                {
                    "automation": _json_dates(automation_to_dict(automation)),
                    "parameters": thaw_json(start.parameters),
                    "maxTasks": start.max_tasks,
                    "concurrency": start.concurrency,
                    "resourceRequest": resources,
                    "workflowRevision": workflow.revision,
                }
            )
            operation = ProjectOperation(
                operation_id,
                project_id,
                key,
                "startBatch",
                digest,
                "running",
                1,
                {"type": "batch", "projectId": project_id, "batchId": batch_id},
                None,
                None,
                now,
                now,
                None,
            )
            operation_row = _operation_row(operation)
            session.add(operation_row)
            session.flush()
            batch_row = ProjectBatchRow(
                id=batch_id,
                project_id=project_id,
                automation_id=automation_id,
                start_operation_id=operation_id,
                prepared_content_id=prepared.prepared_content_id,
                automation_revision=automation.management_revision,
                workflow_revision=workflow.revision,
                status="accepted",
                status_revision=1,
                frozen_request=frozen,
                created_at=now,
                completed_at=None,
            )
            session.add(batch_row)
            session.flush()
            for ordinal in range(start.max_tasks):
                task_id, request_id, snapshot_id = (
                    str(uuid4()),
                    str(uuid4()),
                    str(uuid4()),
                )
                run = self._core.prepare_run(
                    run_request_id=request_id,
                    prepared_content_id=prepared.prepared_content_id,
                    parameters=thaw_json(start.parameters),
                    input_snapshot_ref={
                        "projectId": project_id,
                        "batchId": batch_id,
                        "taskId": task_id,
                        "inputSnapshotId": snapshot_id,
                    },
                    resource_request=resources,
                    capability_bindings=[],
                    created_at=now,
                    uow=session,
                )
                session.add(
                    ProjectTaskRow(
                        id=task_id,
                        project_id=project_id,
                        batch_id=batch_id,
                        run_id=run.run_id,
                        run_request_id=run.run_request_id,
                        ordinal=ordinal,
                        created_at=now,
                    )
                )
                session.flush()
                session.add(
                    ProjectTaskInputSnapshotRow(
                        id=snapshot_id,
                        task_id=task_id,
                        batch_id=batch_id,
                        parameters=thaw_json(start.parameters),
                        inputs=[],
                        captured_at=now,
                    )
                )
                session.flush()
            batch = SqlAlchemyProjectRuns(session).batch(project_id, batch_id)
            operation_row.status = "succeeded"
            operation_row.status_revision = 2
            operation_row.result = {"batch": _json_dates(batch_to_dict(batch))}
            operation_row.completed_at = operation_row.updated_at = now
            session.flush()
            result_operation = _operation(operation_row)
            try:
                session.commit()
            except Exception:
                # A failed DBAPI COMMIT can leave SQLite's transaction open after
                # SQLAlchemy marks it inactive. Never return that connection to the pool.
                session.invalidate()
                raise
            return batch, result_operation, False

    def get_batch(self, project_id: str, batch_id: str) -> Batch:
        with self._factory() as session:
            self._project(session, project_id)
            return SqlAlchemyProjectRuns(session).batch(project_id, batch_id)

    def list_tasks(self, project_id: str, batch_id: str):
        with self._factory() as session:
            self._project(session, project_id)
            return SqlAlchemyProjectRuns(session).list_tasks(project_id, batch_id)

    @staticmethod
    def _project(session: Session, project_id: str) -> ProjectRow:
        row = session.get(ProjectRow, project_id)
        if row is None or row.lifecycle_state == "deleted":
            raise ProjectRunError("NOT_FOUND", "项目不存在", 404)
        return row
