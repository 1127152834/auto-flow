from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any, get_args

from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_runs.models import (
    BatchStatus,
    ProjectRunError,
    TaskInputSnapshot,
    batch_to_dict,
    snapshot_to_dict,
    task_to_dict,
)
from autoflow.domain.workflows.runtime import CoreRunStatus, thaw_json
from autoflow.infrastructure.database.environment_models import ProjectManualItemRow
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataRecordRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRecordQueryRow,
    ProjectTaskRecordReadRow,
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
            snapshots = list(
                session.scalars(
                    select(ProjectTaskInputSnapshotRow)
                    .join(
                        ProjectTaskRow,
                        ProjectTaskRow.id == ProjectTaskInputSnapshotRow.task_id,
                    )
                    .where(ProjectTaskRow.batch_id == batch_id)
                    .order_by(ProjectTaskRow.ordinal)
                )
            )
            identity_signatures: list[str] = []
            condition_signatures: list[str] = []
            for snapshot in snapshots:
                identities = [
                    {
                        "alias": item.get("alias"),
                        "recordRef": item.get("recordRef"),
                    }
                    for item in snapshot.inputs
                    if isinstance(item, dict) and item.get("recordRef") is not None
                ]
                conditions = [
                    {
                        "alias": item.get("alias"),
                        "recordRef": item.get("recordRef"),
                        "contentRevision": item.get("contentRevision"),
                        "statusRevision": item.get("statusRevision"),
                        "linkRevision": item.get("linkRevision"),
                    }
                    for item in snapshot.inputs
                    if isinstance(item, dict) and item.get("recordRef") is not None
                ]
                if identities:
                    identity_signatures.append(
                        json.dumps(
                            identities,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
                    condition_signatures.append(
                        json.dumps(
                            conditions,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
            counts = Counter(identity_signatures)
            unchanged_streak = 0
            if condition_signatures:
                for signature in reversed(condition_signatures[:-1]):
                    if signature != condition_signatures[-1]:
                        break
                    unchanged_streak += 1
            return {
                "batch": batch_to_dict(batch),
                "statusCounts": dict(batch.counts.by_status),
                "taskCount": batch.counts.created_task_count,
                "reusedInputGroupCount": sum(
                    count - 1 for count in counts.values() if count > 1
                ),
                "unchangedInputStreak": unchanged_streak,
                "stopOperation": _operation(operation) if operation else None,
                "configurationSnapshot": thaw_json(batch.frozen_request),
            }

    def list_tasks(
        self,
        project_id: str,
        *,
        batch_id: str | None = None,
        automation_id: str | None = None,
        table_id: str | None = None,
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
            if table_id:
                # 同一冻结集合的两种视角（列表下钻、统计）共用这一处过滤，避免
                # 只在一侧收紧后出现“屏幕结果与下钻结果不一致”。
                input_refs = func.json_tree(
                    ProjectTaskInputSnapshotRow.inputs
                ).table_valued("key", "value", "type")
                query = query.where(
                    exists(
                        select(1)
                        .select_from(input_refs)
                        .where(
                            input_refs.c.key == "tableId",
                            input_refs.c.value == table_id,
                        )
                    )
                )
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
            # 任务列表里的「等待人工」行必须能进入那份唯一的人工详情，所以随行返回
            # 当前仍未结束的人工事项标识；没有事项的任务保持为空，不伪造入口。
            manual_item_ids: dict[str, str] = {}
            if task_rows:
                manual_rows = session.scalars(
                    select(ProjectManualItemRow)
                    .where(
                        ProjectManualItemRow.task_id.in_(
                            [row.id for row in task_rows]
                        ),
                        ProjectManualItemRow.status.in_(
                            ("waiting", "resume_requested")
                        ),
                    )
                    .order_by(ProjectManualItemRow.updated_at.desc())
                ).all()
                for manual in manual_rows:
                    manual_item_ids.setdefault(str(manual.task_id), str(manual.id))
            latest_nodes: dict[str, str] = {}
            latest_node_attempts: dict[str, datetime] = {}
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
                        latest_node_attempts[event.run_id] = aware(event.occurred_at)
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
                        "lastStatusAt": _last_status_at(
                            row.created_at,
                            run,
                            latest_node_attempts.get(row.run_id),
                        ),
                        "manualItemId": manual_item_ids.get(str(row.id)),
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
            node_names = prepared_node_names(
                SqlAlchemyWorkflowRuntimeRepository(session).get_prepared_content(
                    prepared_content_id=run.prepared_content_id
                )
            )
            return {
                "task": task_to_dict(task),
                "inputSnapshot": snapshot_to_dict(snapshot),
                "automationName": batch.frozen_request["automation"]["name"],
                "batchStartedAt": aware(batch.created_at),
                "parameterDefinitions": batch.frozen_request["automation"][
                    "parameterSchema"
                ],
                "nodeNames": node_names,
                "run": _run(run),
                "currentInputs": _current_inputs(session, project_id, snapshot),
                "dataWrites": _data_writes(
                    session,
                    project_id,
                    task_id,
                    visits=_visit_windows(session, task.run_id, node_names),
                ),
            }


def _current_inputs(
    session: Session, project_id: str, snapshot: TaskInputSnapshot
) -> list[dict[str, Any]]:
    """Read the live value of every record frozen into the input snapshot.

    The snapshot itself never changes; this is a separate current-state channel
    so a human can see what the frozen input looked like next to what the record
    holds now.  A missing row (deleted record, superseded data generation) is
    reported as ``exists: False`` instead of an empty record.
    """
    items: list[dict[str, Any]] = []
    for raw in thaw_json(snapshot.inputs):
        item = raw if isinstance(raw, dict) else {}
        ref = item.get("recordRef")
        if not isinstance(ref, dict):
            continue
        key = ref.get("recordKey")
        table_id = ref.get("tableId")
        generation = ref.get("datasetGeneration")
        if (
            not isinstance(key, dict)
            or key.get("type") not in {"text", "integer", "uuid"}
            or not isinstance(key.get("value"), str)
            or not isinstance(table_id, str)
            or not isinstance(generation, str)
        ):
            continue
        frozen = {
            value.get("fieldId"): value.get("value")
            for value in item.get("values", [])
            if isinstance(value, dict)
        }
        row = session.scalar(
            select(DataRecordRow).where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == table_id,
                DataRecordRow.dataset_generation == generation,
                DataRecordRow.key_type == key["type"],
                DataRecordRow.key_value == key["value"],
                DataRecordRow.deleted.is_(False),
            )
        )
        if row is None:
            items.append(
                {
                    "inputId": item.get("inputId"),
                    "recordRef": ref,
                    "exists": False,
                    "values": [],
                    "recordStatus": None,
                    "contentRevision": None,
                    "updatedAt": None,
                    "changedFieldIds": [],
                }
            )
            continue
        fields = {
            field.id: field.name
            for field in session.scalars(
                select(DataFieldRow).where(
                    DataFieldRow.project_id == project_id,
                    DataFieldRow.table_id == table_id,
                    DataFieldRow.dataset_generation == generation,
                )
            )
        }
        status = session.get(DataStatusRow, row.status_id) if row.status_id else None
        values = [
            {
                "fieldId": field_id,
                "fieldName": fields.get(field_id, "字段"),
                "value": value,
            }
            for field_id, value in row.values_json.items()
        ]
        items.append(
            {
                "inputId": item.get("inputId"),
                "recordRef": ref,
                "exists": True,
                "values": values,
                "recordStatus": status.name if status is not None else None,
                "contentRevision": row.content_revision,
                "updatedAt": aware(row.updated_at),
                "changedFieldIds": [
                    value["fieldId"]
                    for value in values
                    if value["fieldId"] in frozen
                    and frozen[value["fieldId"]] != value["value"]
                ],
            }
        )
    return items


def _visit_windows(
    session: Session, run_id: str, node_names: dict[str, str]
) -> list[tuple[datetime, datetime, str | None, str | None]]:
    """Node visit time windows, used to attribute a write to the node that ran it.

    Data operations persist no node id, so attribution reads the window already
    recorded in the run event stream.  ``ponytail:`` time-window attribution, not
    a stored node reference; add a node column to the operation resource if
    concurrent branches ever need exact attribution.
    """
    events = session.scalars(
        select(WorkflowRunEventRow)
        .where(
            WorkflowRunEventRow.run_id == run_id,
            WorkflowRunEventRow.kind == "nodeAttempt",
        )
        .order_by(WorkflowRunEventRow.sequence)
    ).all()
    visits: dict[tuple[str | None, int | None], dict[str, Any]] = {}
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        entry = visits.setdefault(
            (event.node_visit_id, event.attempt),
            {"start": None, "end": None, "nodeId": event.node_id},
        )
        if payload.get("status") == "started":
            entry["start"] = aware(event.occurred_at)
        elif payload.get("status") in {"succeeded", "failed"}:
            entry["end"] = aware(event.occurred_at)
    windows = []
    for entry in visits.values():
        if entry["start"] is None or entry["end"] is None:
            continue
        node_id = entry["nodeId"]
        windows.append(
            (
                entry["start"],
                entry["end"],
                node_id,
                node_names.get(node_id, "未命名节点") if node_id else None,
            )
        )
    return windows


def _attribute_visit(
    occurred_at: datetime,
    visits: list[tuple[datetime, datetime, str | None, str | None]],
) -> tuple[str | None, str | None]:
    when = aware(occurred_at)
    matched = [visit for visit in visits if visit[0] <= when <= visit[1]]
    if len(matched) != 1:
        return None, None
    return matched[0][2], matched[0][3]


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
    session: Session,
    project_id: str,
    task_id: str,
    *,
    visits: list[tuple[datetime, datetime, str | None, str | None]],
) -> list[dict[str, Any]]:
    operations = session.scalars(
        select(ProjectOperationRow)
        .where(
            ProjectOperationRow.project_id == project_id,
            ProjectOperationRow.resource["taskId"].as_string() == task_id,
            ProjectOperationRow.status == "succeeded",
        )
        .order_by(ProjectOperationRow.created_at, ProjectOperationRow.id)
    ).all()
    result: list[tuple[datetime, dict[str, Any]]] = []
    queries = session.scalars(
        select(ProjectTaskRecordQueryRow)
        .where(
            ProjectTaskRecordQueryRow.project_id == project_id,
            ProjectTaskRecordQueryRow.task_id == task_id,
        )
        .order_by(ProjectTaskRecordQueryRow.created_at, ProjectTaskRecordQueryRow.id)
    ).all()
    for query in queries:
        table = session.get(DataTableRow, query.table_id)
        result.append(
            (
                query.created_at,
                {
                    "kind": "query",
                    "tableDisplay": table.name if table is not None else "数据表",
                    "recordDisplay": f"命中 {query.result_count} 条",
                    "detail": (
                        f"读取用途：{query.request_payload.get('readPurpose', 'workflow')}"
                    ),
                    "outcome": "succeeded",
                },
            )
        )
    for operation in operations:
        changes = session.scalars(
            select(DataChangeRow)
            .where(
                DataChangeRow.project_id == project_id,
                DataChangeRow.operation_id == operation.id,
                DataChangeRow.origin == "workflow",
            )
            .order_by(DataChangeRow.sequence)
        ).all()
        if operation.kind in {"setRecordStatus", "updateRecord"} and not changes:
            continue
        change = changes[0] if changes else None
        after = operation.result or {}
        if operation.kind not in {"addField", "ensureField", "modifyField"}:
            after = (change.after if change is not None else None) or after
        before = (change.before if change is not None else None) or {}
        target = after.get("target") if isinstance(after, dict) else None
        ref = (
            after.get("ref")
            or (target.get("recordRef") if isinstance(target, dict) else None)
            or (change.resource.get("recordRef") if change is not None else None)
            or {}
        )
        table_id = ref.get("tableId")
        field = after.get("field") if isinstance(after, dict) else None
        if table_id is None and isinstance(field, dict):
            table_id = field.get("ref", {}).get("tableId")
        table = session.get(DataTableRow, table_id) if table_id else None
        common = {
            "tableDisplay": table.name if table is not None else "数据表",
            "recordDisplay": _record_display(ref),
            "outcome": "succeeded",
        }
        if operation.kind == "setRecordStatus":
            result.append(
                (
                    operation.created_at,
                    {
                        **common,
                        "kind": "statusChange",
                        "previousStatus": _status_name(session, before.get("statusId")),
                        "nextStatus": _status_name(session, after.get("statusId")),
                    },
                )
            )
        elif operation.kind == "createRecord":
            result.append(
                (
                    operation.created_at,
                    {
                        **common,
                        "kind": "recordCreated",
                        "referenceDisplay": _record_display(ref),
                        "afterSummary": _value_summary(session, table_id, after),
                    },
                )
            )
        elif operation.kind == "updateRecord":
            result.append(
                (
                    operation.created_at,
                    {
                        **common,
                        "kind": "recordUpdated",
                        "referenceDisplay": _record_display(ref),
                        "beforeSummary": _value_summary(session, table_id, before),
                        "afterSummary": _value_summary(session, table_id, after),
                    },
                )
            )
        elif operation.kind == "deleteRecord":
            result.append(
                (
                    operation.created_at,
                    {
                        **common,
                        "kind": "recordDeleted",
                        "referenceDisplay": _record_display(ref),
                        "beforeSummary": _value_summary(session, table_id, before),
                    },
                )
            )
        elif operation.kind in {
            "addField",
            "ensureField",
            "modifyField",
        } and isinstance(field, dict):
            labels = {
                "addField": "fieldAdded",
                "ensureField": "fieldEnsured",
                "modifyField": "fieldModified",
            }
            result.append(
                (
                    operation.created_at,
                    {
                        **common,
                        "kind": labels[operation.kind],
                        "recordDisplay": str(field.get("name", "字段")),
                        "referenceDisplay": f"字段 {field.get('name', field.get('fieldId', ''))}",
                        "beforeSummary": _field_summary(before),
                        "afterSummary": _field_summary(field),
                        "detail": (
                            "字段已存在，无需变更"
                            if operation.kind == "ensureField"
                            and not after.get("created", True)
                            else None
                        ),
                    },
                )
            )
    reads = session.scalars(
        select(ProjectTaskRecordReadRow)
        .where(
            ProjectTaskRecordReadRow.project_id == project_id,
            ProjectTaskRecordReadRow.task_id == task_id,
        )
        .order_by(ProjectTaskRecordReadRow.created_at, ProjectTaskRecordReadRow.id)
    ).all()
    for read in reads:
        table = session.get(DataTableRow, read.table_id)
        ref = read.snapshot.get("ref", {})
        result.append(
            (
                read.created_at,
                {
                    "kind": "read",
                    "tableDisplay": table.name if table is not None else "数据表",
                    "recordDisplay": _record_display(ref),
                    "referenceDisplay": _record_display(ref),
                    "detail": f"读取用途：{read.read_purpose}",
                    "outcome": "succeeded",
                },
            )
        )
    items: list[dict[str, Any]] = []
    for occurred_at, item in sorted(result, key=lambda entry: entry[0]):
        node_id, node_name = _attribute_visit(occurred_at, visits)
        items.append({**item, "nodeId": node_id, "nodeName": node_name})
    return items


def _value_summary(
    session: Session, table_id: str | None, value: dict[str, Any]
) -> str | None:
    raw_values = value.get("values") if isinstance(value, dict) else None
    if not raw_values:
        return None
    values = (
        {
            item.get("fieldId"): item.get("value")
            for item in raw_values
            if isinstance(item, dict)
        }
        if isinstance(raw_values, list)
        else raw_values
    )
    if not isinstance(values, dict):
        return None
    fields = {
        row.id: row.name
        for row in session.scalars(
            select(DataFieldRow).where(DataFieldRow.table_id == table_id)
        )
    }
    parts = [
        f"{fields.get(field_id, '字段')}：{field_value}"
        for field_id, field_value in list(values.items())[:3]
    ]
    return "；".join(parts) + ("…" if len(values) > 3 else "")


def _field_summary(value: dict[str, Any]) -> str | None:
    if not value or "type" not in value:
        return None
    return f"{value.get('type')} · {'必填' if value.get('required') else '可选'}"


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


def _last_status_at(
    created_at: datetime,
    run: Any,
    last_node_attempt_at: datetime | None,
) -> datetime:
    """任务最近一次状态时间。

    取任务创建、最近一次节点尝试、运行开始与运行结束四个真实事实中最新者；
    不按剩余时间或客户端时钟推断，缺事实时退回到已经发生的那个时间点。
    """
    candidates = [aware(created_at)]
    if last_node_attempt_at is not None:
        candidates.append(aware(last_node_attempt_at))
    if run is not None:
        if run.started_at is not None:
            candidates.append(aware(run.started_at))
        if run.completed_at is not None:
            candidates.append(aware(run.completed_at))
    return max(candidates)


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
