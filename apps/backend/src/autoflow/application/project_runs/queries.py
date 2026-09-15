from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, get_args

from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_runs.models import (
    BatchStatus,
    ProjectRunError,
    batch_to_dict,
    snapshot_to_dict,
    task_to_dict,
)
from autoflow.domain.workflows.runtime import CoreRunStatus, thaw_json
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.project_runs import SqlAlchemyProjectRuns, aware
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)

from .presentation import prepared_node_names

BATCH_STATUSES = frozenset(get_args(BatchStatus))
RUN_STATUSES = frozenset(get_args(CoreRunStatus))


class ProjectRunQueries:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def list_batches(
        self,
        project_id: str,
        *,
        automation_id: str | None = None,
        query_text: str | None = None,
        status: str | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
        sort: str = "-createdAt",
    ) -> tuple[list[dict[str, Any]], int]:
        _page(page, page_size)
        query_text = _query(query_text)
        started_from, started_to = _range(started_from, started_to, "started")
        _status(status, BATCH_STATUSES)
        with self._factory() as session:
            _project(session, project_id)
            query = select(ProjectBatchRow).where(
                ProjectBatchRow.project_id == project_id
            )
            if automation_id:
                query = query.where(ProjectBatchRow.automation_id == automation_id)
            if query_text:
                query = query.where(
                    or_(
                        func.lower(ProjectBatchRow.id).contains(
                            query_text.lower(), autoescape=True
                        ),
                        func.lower(
                            ProjectBatchRow.frozen_request["automation"][
                                "name"
                            ].as_string()
                        ).contains(query_text.lower(), autoescape=True),
                    )
                )
            if status:
                query = query.where(ProjectBatchRow.status == status)
            if started_from:
                query = query.where(ProjectBatchRow.created_at >= started_from)
            if started_to:
                query = query.where(ProjectBatchRow.created_at <= started_to)
            column, descending = _sort(sort, {"createdAt": ProjectBatchRow.created_at})
            total = (
                session.scalar(select(func.count()).select_from(query.subquery())) or 0
            )
            rows = session.scalars(
                query.order_by(
                    column.desc() if descending else column.asc(),
                    ProjectBatchRow.id.desc()
                    if descending
                    else ProjectBatchRow.id.asc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            repository = SqlAlchemyProjectRuns(session)
            return [
                batch_to_dict(repository.batch(project_id, row.id)) for row in rows
            ], total

    def batch_detail(self, project_id: str, batch_id: str) -> dict[str, Any]:
        with self._factory() as session:
            _project(session, project_id)
            repository = SqlAlchemyProjectRuns(session)
            batch = repository.batch(project_id, batch_id)
            operation = session.scalar(
                select(ProjectOperationRow)
                .where(
                    ProjectOperationRow.project_id == project_id,
                    ProjectOperationRow.kind.in_(("stopBatch", "forceStopBatch")),
                    ProjectOperationRow.resource["batchId"].as_string() == batch_id,
                )
                .order_by(ProjectOperationRow.created_at.desc())
            )
            return {
                "batch": batch_to_dict(batch),
                "statusCounts": dict(batch.counts.by_status),
                "taskCount": batch.counts.created_task_count,
                "stopOperation": _operation(operation) if operation else None,
                "configurationSnapshot": thaw_json(batch.frozen_request),
            }

    def list_tasks(
        self,
        project_id: str,
        *,
        batch_id: str | None = None,
        automation_id: str | None = None,
        query_text: str | None = None,
        status: str | None = None,
        ended_from: datetime | None = None,
        ended_to: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
        sort: str = "-createdAt",
    ) -> tuple[list[dict[str, Any]], int]:
        _page(page, page_size)
        query_text = _query(query_text)
        ended_from, ended_to = _range(ended_from, ended_to, "ended")
        _status(status, RUN_STATUSES)
        with self._factory() as session:
            _project(session, project_id)
            query = (
                select(ProjectTaskRow)
                .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
                .join(ProjectBatchRow, ProjectBatchRow.id == ProjectTaskRow.batch_id)
                .join(
                    ProjectTaskInputSnapshotRow,
                    ProjectTaskInputSnapshotRow.task_id == ProjectTaskRow.id,
                )
                .where(ProjectTaskRow.project_id == project_id)
            )
            if batch_id:
                query = query.where(ProjectTaskRow.batch_id == batch_id)
            if query_text:
                display_ordinal = _task_ordinal(query_text)
                parameter_values = func.json_each(
                    ProjectTaskInputSnapshotRow.parameters
                ).table_valued("key", "value")
                input_values = func.json_tree(
                    ProjectTaskInputSnapshotRow.inputs
                ).table_valued("key", "value", "type")
                query = query.where(
                    or_(
                        func.lower(ProjectTaskRow.id).contains(
                            query_text.lower(), autoescape=True
                        ),
                        func.lower(ProjectTaskRow.batch_id).contains(
                            query_text.lower(), autoescape=True
                        ),
                        func.lower(ProjectTaskRow.run_id).contains(
                            query_text.lower(), autoescape=True
                        ),
                        func.lower(
                            ProjectBatchRow.frozen_request["automation"][
                                "name"
                            ].as_string()
                        ).contains(query_text.lower(), autoescape=True),
                        exists(
                            select(1)
                            .select_from(parameter_values)
                            .where(
                                func.lower(
                                    cast(parameter_values.c.value, String)
                                ).contains(query_text.lower(), autoescape=True)
                            )
                        ),
                        exists(
                            select(1)
                            .select_from(input_values)
                            .where(
                                input_values.c.type.in_(
                                    ("text", "integer", "real", "true", "false", "null")
                                ),
                                func.lower(cast(input_values.c.value, String)).contains(
                                    query_text.lower(), autoescape=True
                                ),
                            )
                        ),
                        *(
                            [ProjectTaskRow.ordinal == display_ordinal]
                            if display_ordinal is not None
                            else []
                        ),
                    )
                )
            if automation_id:
                query = query.where(ProjectBatchRow.automation_id == automation_id)
            if status:
                query = query.where(WorkflowRunRow.status == status)
            if ended_from:
                query = query.where(WorkflowRunRow.completed_at >= ended_from)
            if ended_to:
                query = query.where(WorkflowRunRow.completed_at <= ended_to)
            column, descending = _sort(sort, {"createdAt": ProjectTaskRow.created_at})
            total = (
                session.scalar(select(func.count()).select_from(query.subquery())) or 0
            )
            task_rows = session.scalars(
                query.order_by(
                    column.desc() if descending else column.asc(),
                    ProjectTaskRow.id.desc() if descending else ProjectTaskRow.id.asc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            repository = SqlAlchemyProjectRuns(session)
            run_ids = [row.run_id for row in task_rows]
            latest_nodes: dict[str, str] = {}
            if run_ids:
                events = session.scalars(
                    select(WorkflowRunEventRow)
                    .where(
                        WorkflowRunEventRow.run_id.in_(run_ids),
                        WorkflowRunEventRow.kind == "nodeAttempt",
                    )
                    .order_by(
                        WorkflowRunEventRow.run_id,
                        WorkflowRunEventRow.sequence.desc(),
                    )
                ).all()
                for event in events:
                    if (
                        event.run_id not in latest_nodes
                        and event.node_id
                        and event.payload.get("status") in {"succeeded", "failed"}
                    ):
                        latest_nodes[event.run_id] = event.node_id
            node_names: dict[str, dict[str, str]] = {}
            items: list[dict[str, Any]] = []
            for row in task_rows:
                task = repository.task(project_id, row.id)
                snapshot = session.get(
                    ProjectTaskInputSnapshotRow, task.input_snapshot_id
                )
                if snapshot is None:
                    raise ProjectRunError(
                        "RUN_FACTS_INCOMPLETE", "任务证据不完整，需要核验", 409
                    )
                batch = repository.batch_row(project_id, row.batch_id)
                run = SqlAlchemyWorkflowRuntimeRepository(session).get_run(
                    run_id=row.run_id
                )
                item = task_to_dict(task)
                item.update(
                    {
                        "automationName": batch.frozen_request["automation"]["name"],
                        "batchStartedAt": aware(batch.created_at),
                        "inputIdentifier": _input_identifier(snapshot.inputs),
                        "endNodeName": None,
                    }
                )
                node_id = latest_nodes.get(row.run_id)
                if node_id and run is not None:
                    names = node_names.get(run.prepared_content_id)
                    if names is None:
                        names = prepared_node_names(
                            SqlAlchemyWorkflowRuntimeRepository(
                                session
                            ).get_prepared_content(
                                prepared_content_id=run.prepared_content_id
                            )
                        )
                        node_names[run.prepared_content_id] = names
                    item["endNodeName"] = names.get(node_id, "未命名节点")
                items.append(item)
            return items, total

    def task_detail(self, project_id: str, task_id: str) -> dict[str, Any]:
        with self._factory() as session:
            _project(session, project_id)
            repository = SqlAlchemyProjectRuns(session)
            task = repository.task(project_id, task_id)
            snapshot = repository.snapshot(project_id, task_id)
            batch = repository.batch_row(project_id, task.batch_id)
            run = SqlAlchemyWorkflowRuntimeRepository(session).get_run(
                run_id=task.run_id
            )
            if run is None:
                raise ProjectRunError(
                    "RUN_FACTS_INCOMPLETE", "任务证据不完整，需要核验", 409
                )
            return {
                "task": task_to_dict(task),
                "inputSnapshot": snapshot_to_dict(snapshot),
                "automationName": batch.frozen_request["automation"]["name"],
                "batchStartedAt": aware(batch.created_at),
                "parameterDefinitions": batch.frozen_request["automation"][
                    "parameterSchema"
                ],
                "nodeNames": prepared_node_names(
                    SqlAlchemyWorkflowRuntimeRepository(session).get_prepared_content(
                        prepared_content_id=run.prepared_content_id
                    )
                ),
                "run": _run(run),
                "dataWrites": _data_writes(session, project_id, task_id),
            }


def _input_identifier(inputs: list[dict[str, Any]]) -> str:
    if not inputs:
        return "参数任务"
    first = inputs[0]
    for key in ("alias", "name"):
        value = first.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return str(value)
    return "项目数据输入" if len(inputs) == 1 else f"{len(inputs)} 项项目数据输入"


def _data_writes(
    session: Session, project_id: str, task_id: str
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(DataChangeRow, ProjectOperationRow)
        .join(
            ProjectOperationRow,
            (ProjectOperationRow.project_id == DataChangeRow.project_id)
            & (ProjectOperationRow.id == DataChangeRow.operation_id),
        )
        .where(
            DataChangeRow.project_id == project_id,
            DataChangeRow.origin == "workflow",
            ProjectOperationRow.resource["taskId"].as_string() == task_id,
        )
        .order_by(DataChangeRow.created_at, DataChangeRow.id)
    ).all()
    result: list[dict[str, Any]] = []
    for change, operation in rows:
        after = change.after or {}
        before = change.before or {}
        ref = after.get("ref") or change.resource.get("recordRef") or {}
        table_id = ref.get("tableId")
        table = session.get(DataTableRow, table_id) if table_id else None
        common = {
            "tableDisplay": table.name if table is not None else "数据表",
            "recordDisplay": _record_display(ref),
            "outcome": "succeeded",
        }
        if operation.kind == "setRecordStatus":
            result.append(
                {
                    **common,
                    "kind": "statusChange",
                    "previousStatus": _status_name(session, before.get("statusId")),
                    "nextStatus": _status_name(session, after.get("statusId")),
                }
            )
        elif operation.kind == "createRecord":
            result.append(
                {
                    **common,
                    "kind": "recordCreated",
                    "referenceDisplay": _record_display(ref),
                }
            )
    return result


def _status_name(session: Session, status_id: str | None) -> str | None:
    if status_id is None:
        return None
    row = session.get(DataStatusRow, status_id)
    return row.name if row is not None else "已删除的状态"


def _record_display(ref: dict[str, Any]) -> str:
    key = ref.get("recordKey") if isinstance(ref, dict) else None
    if not isinstance(key, dict):
        return "记录"
    return f"{key.get('type', 'unknown')} · {key.get('value', '')}"


def _project(session: Session, project_id: str) -> None:
    project = session.get(ProjectRow, project_id)
    if project is None or project.lifecycle_state == "deleted":
        raise ProjectRunError("NOT_FOUND", "项目不存在", 404)


def _status(value: str | None, allowed: frozenset[str]) -> None:
    if value is not None and value not in allowed:
        raise ProjectRunError(
            "VALIDATION_ERROR",
            "状态筛选无效",
            422,
            {"fields": {"status": "未知状态"}, "retryable": False},
        )


def _query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if len(normalized) > 120:
        raise ProjectRunError(
            "VALIDATION_ERROR",
            "搜索内容无效",
            422,
            {"fields": {"q": "最多 120 个字符"}, "retryable": False},
        )
    return normalized or None


def _task_ordinal(value: str) -> int | None:
    match = re.fullmatch(r"(?:任务\s*|[Tt]0*)?([1-9][0-9]*)", value)
    return int(match.group(1)) - 1 if match else None


def _page(page: int, page_size: int) -> None:
    if (
        type(page) is not int
        or not 1 <= page <= 2_147_483_647
        or type(page_size) is not int
        or not 1 <= page_size <= 200
    ):
        raise ProjectRunError(
            "VALIDATION_ERROR",
            "分页参数无效",
            422,
            {"fields": {"page": "超出允许范围"}, "retryable": False},
        )


def _range(
    lower: datetime | None, upper: datetime | None, prefix: str
) -> tuple[datetime | None, datetime | None]:
    values = ((f"{prefix}From", lower), (f"{prefix}To", upper))
    for field, value in values:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ProjectRunError(
                "VALIDATION_ERROR",
                "时间范围无效",
                422,
                {"fields": {field: "必须包含时区"}, "retryable": False},
            )
    normalized_lower = lower.astimezone(UTC) if lower else None
    normalized_upper = upper.astimezone(UTC) if upper else None
    if normalized_lower and normalized_upper and normalized_lower > normalized_upper:
        raise ProjectRunError(
            "VALIDATION_ERROR",
            "时间范围无效",
            422,
            {
                "fields": {f"{prefix}To": "结束时间不能早于开始时间"},
                "retryable": False,
            },
        )
    return normalized_lower, normalized_upper


def _sort(value: str, columns: dict[str, Any]) -> tuple[Any, bool]:
    descending, name = value.startswith("-"), value.removeprefix("-")
    if name not in columns:
        raise _sort_error(value)
    return columns[name], descending


def _sort_error(value: str) -> ProjectRunError:
    return ProjectRunError(
        "VALIDATION_ERROR", "排序字段无效", 422, {"fields": {"sort": value}}
    )


def _operation(row: ProjectOperationRow) -> dict[str, Any]:
    return {
        "operationId": row.id,
        "projectId": row.project_id,
        "idempotencyKey": row.idempotency_key,
        "kind": row.kind,
        "status": row.status,
        "statusRevision": row.status_revision,
        "resource": row.resource,
        "result": row.result,
        "error": row.error,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
        "completedAt": row.completed_at,
    }


def _run(run: Any) -> dict[str, Any]:
    resource = thaw_json(run.resource_request)
    public_resource = {
        key: resource[key]
        for key in (
            "browser",
            "profileId",
            "kernelId",
            "proxy",
            "modelProviderId",
            "automaticExecutionTimeoutSeconds",
        )
        if key in resource
    }
    return {
        "runId": run.run_id,
        "runRequestId": run.run_request_id,
        "status": run.status,
        "statusRevision": run.status_revision,
        "executionGeneration": run.execution_generation,
        "preparedContentId": run.prepared_content_id,
        "capabilityBindings": thaw_json(run.capability_bindings),
        "resourceRequest": public_resource,
        "lastSequence": run.last_sequence,
        "terminal": run.terminal,
        "error": thaw_json(run.error) if run.error is not None else None,
        "startedAt": run.started_at,
        "finishedAt": run.completed_at,
    }
