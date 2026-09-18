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
from autoflow.domain.project_data.capabilities import TableCapabilityGrant
from autoflow.domain.project_runs.models import (
    Batch,
    BatchCounts,
    ProjectRunError,
    batch_to_dict,
)
from autoflow.domain.project_runs.rules import validate_batch_start
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.domain.workflows.runtime import TERMINAL_STATUSES, thaw_json
from autoflow.infrastructure.database.models import (
    ProjectOperationRow,
    ProjectRow,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_automations import (
    _record as automation_record,
)
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataTableRow,
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
        resolve_create_record_targets: Callable[
            [Session, AutomationRecord], Sequence[tuple[str, str]]
        ]
        | None = None,
        resolve_status_input_ids: Callable[[AutomationRecord], Sequence[str]]
        | None = None,
        resolve_data_capability_manifest: Callable[
            [Session, AutomationRecord], dict[str, Any]
        ]
        | None = None,
        environments: Any | None = None,
    ) -> None:
        self._factory, self._core = session_factory, core_runtime
        self._resolve_resources = resolve_resources
        self._environments = environments
        self._capabilities = tuple(available_capabilities)
        self._resolve_create_record_targets = resolve_create_record_targets or (
            lambda _session, _automation: ()
        )
        self._resolve_status_input_ids = resolve_status_input_ids or (
            lambda _automation: ()
        )
        self._resolve_data_capability_manifest = resolve_data_capability_manifest or (
            lambda _session, _automation: {}
        )

    def inspect_capabilities(self, workflow_id: str) -> list[dict[str, Any]]:
        # Workflow shape and actual resource availability are checked separately.
        # This is the same installed worker capability used by atomic preparation.
        return [
            {
                "capability": "browser.cloakbrowser",
                "required": True,
                "available": "browser.cloakbrowser" in self._capabilities,
                "reason": "本地浏览器执行能力"
                if "browser.cloakbrowser" in self._capabilities
                else "本地浏览器执行能力不可用",
            },
            {
                "capability": "project.data",
                "required": False,
                "available": "project.data" in self._capabilities,
                "reason": (
                    "项目数据执行能力可用"
                    if "project.data" in self._capabilities
                    else "项目数据执行能力未接入"
                ),
            },
        ]

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
            has_data_inputs = bool(automation.input_plan.get("inputs"))
            declared_table_grants = self._validate_capability_manifest(
                session,
                automation,
                self._resolve_data_capability_manifest(session, automation),
            )
            start = validate_batch_start(
                automation,
                payload,
                allow_data_inputs="project.data" in self._capabilities,
            )
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
            create_record_targets = [
                {"tableId": table_id, "datasetGeneration": generation}
                for table_id, generation in self._resolve_create_record_targets(
                    session, automation
                )
            ]
            table_grants: list[dict[str, Any]] = []
            for target in create_record_targets:
                field_ids = list(
                    session.scalars(
                        select(DataFieldRow.id).where(
                            DataFieldRow.project_id == project_id,
                            DataFieldRow.table_id == target["tableId"],
                            DataFieldRow.dataset_generation
                            == target["datasetGeneration"],
                        )
                    )
                )
                table_grants.append(
                    {
                        **target,
                        "operations": ["createRecord"],
                        "fieldIds": field_ids,
                        "readPurposes": [],
                    }
                )
            table_grants.extend(declared_table_grants)
            status_input_ids = (
                list(self._resolve_status_input_ids(automation))
                if has_data_inputs
                else []
            )
            has_data_capability = bool(
                has_data_inputs
                or create_record_targets
                or table_grants
                or status_input_ids
            )
            if has_data_capability and "project.data" not in self._capabilities:
                raise ProjectRunError(
                    "CAPABILITY_UNAVAILABLE",
                    "项目数据执行能力不可用",
                    409,
                )
            data_capability_binding = (
                {
                    "capability": "project.data",
                    "projectId": project_id,
                    "createRecordTargets": create_record_targets,
                    "tableGrants": table_grants,
                    "statusInputIds": status_input_ids,
                }
                if has_data_capability
                else None
            )
            frozen["dataCapabilityBinding"] = data_capability_binding
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
                claim_gate_state="open" if has_data_inputs else "closed",
                selection_outcome={"status": "pending"} if has_data_inputs else None,
            )
            session.add(batch_row)
            session.flush()
            created_tasks: list[tuple[str, str]] = []
            policy = start.environment_override or automation.environment_policy
            for ordinal in range(0 if has_data_inputs else (start.max_tasks or 0)):
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
                    capability_bindings=(
                        [
                            {
                                **data_capability_binding,
                                "taskId": task_id,
                                "executionGeneration": 1,
                            }
                        ]
                        if data_capability_binding is not None
                        else []
                    ),
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
                snapshot_inputs: list[dict[str, Any]] = []
                session.add(
                    ProjectTaskInputSnapshotRow(
                        id=snapshot_id,
                        task_id=task_id,
                        batch_id=batch_id,
                        parameters=thaw_json(start.parameters),
                        inputs=snapshot_inputs,
                        captured_at=now,
                    )
                )
                session.flush()
                if self._environments is not None:
                    self._environments.reserve_task_instance(
                        session, project_id, task_id, run.run_id, policy
                    )
                created_tasks.append((task_id, run.run_id))
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
            if self._environments is not None:
                for task_id, run_id in created_tasks:
                    self._environments.attach_task_instance(
                        project_id, task_id, run_id, policy
                    )
            return batch, result_operation, False

    @staticmethod
    def _validate_capability_manifest(
        session: Session,
        automation: AutomationRecord,
        manifest: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            if not isinstance(manifest, dict):
                raise TypeError
            if set(manifest) - {"tableGrants"}:
                raise ValueError
            raw_grants = manifest.get("tableGrants", [])
            if not isinstance(raw_grants, list):
                raise TypeError

            grants: list[dict[str, Any]] = []
            for raw in raw_grants:
                if not isinstance(raw, dict) or set(raw) != {
                    "tableId",
                    "datasetGeneration",
                    "operations",
                    "fieldIds",
                    "readPurposes",
                }:
                    raise ValueError
                grant = TableCapabilityGrant(
                    raw["tableId"],
                    raw["datasetGeneration"],
                    frozenset(raw["operations"]),
                    frozenset(raw["fieldIds"]),
                    frozenset(raw["readPurposes"]),
                )
                table = session.get(DataTableRow, grant.table_id)
                if (
                    table is None
                    or table.project_id != automation.project_id
                    or not table.published
                    or table.current_generation != grant.dataset_generation
                ):
                    raise ValueError
                existing_fields = set(
                    session.scalars(
                        select(DataFieldRow.id).where(
                            DataFieldRow.project_id == automation.project_id,
                            DataFieldRow.table_id == grant.table_id,
                            DataFieldRow.dataset_generation == grant.dataset_generation,
                        )
                    )
                )
                if not grant.field_ids <= existing_fields:
                    raise ValueError
                grants.append(
                    {
                        "tableId": grant.table_id,
                        "datasetGeneration": grant.dataset_generation,
                        "operations": sorted(grant.operations),
                        "fieldIds": sorted(grant.field_ids),
                        "readPurposes": sorted(grant.read_purposes),
                    }
                )
            return grants
        except (KeyError, TypeError, ValueError, ProjectError) as exc:
            raise ProjectRunError(
                "CAPABILITY_FACTS_INCOMPLETE",
                "工作流数据能力声明无效",
                409,
            ) from exc

    def get_batch(self, project_id: str, batch_id: str) -> Batch:
        with self._factory() as session:
            self._project(session, project_id)
            return SqlAlchemyProjectRuns(session).batch(project_id, batch_id)

    def preview_inputs(
        self, project_id: str, automation_id: str, expected_revision: int
    ) -> dict[str, Any]:
        with self._factory() as session:
            self._project(session, project_id)
            row = session.get(ProjectAutomationRow, automation_id)
            if row is None or row.project_id != project_id:
                raise ProjectRunError("NOT_FOUND", "自动化不存在", 404)
            automation = automation_record(row)
            if automation.management_revision != expected_revision:
                raise ProjectRunError(
                    "REVISION_CONFLICT",
                    "自动化配置已更新，请刷新后重试",
                    409,
                    {"currentAutomationRevision": automation.management_revision},
                )
            if "project.data" not in self._capabilities:
                raise ProjectRunError(
                    "CAPABILITY_UNAVAILABLE", "当前执行端未开放项目数据能力", 409
                )
            selection = SqlAlchemyProjectInputGroups(session).select_required(
                project_id, automation.input_plan
            )
            selected = {item.input_id: item for item in selection.inputs}
            unavailable = {
                item.input_id: item.reason for item in selection.unavailable_inputs
            }
            issue_ids = set(selection.issue_input_ids)
            raw_issue_details = dict(selection.issue_details)
            issue_details = {
                input_id: _present_input_issue(message)
                for input_id, message in selection.issue_details
            }
            effective_required = set(selection.effective_required_input_ids)
            details = {
                "noMatch": "没有符合条件的记录",
                "temporarilyBusy": "符合条件的记录暂时被其他任务占用",
                "ambiguous": "关联条件匹配到多条记录，请先修复数据",
                "configurationError": "数据输入配置或表结构已失效",
                "scanBudgetExceeded": "候选数据量超出单次预检范围，请收紧筛选条件",
            }
            items = []
            for item in automation.input_plan.get("inputs", []):
                table = session.get(DataTableRow, item["tableId"])
                chosen = selected.get(item["inputId"])
                unavailable_reason = unavailable.get(item["inputId"])
                outcome = (
                    "ready"
                    if chosen is not None
                    else (
                        "noMatch"
                        if unavailable_reason == "no_match"
                        else "temporarilyBusy"
                        if unavailable_reason == "busy"
                        else selection.status
                        if item["inputId"] in issue_ids
                        else "notEvaluated"
                    )
                )
                promoted_to_required = (
                    item["inputId"] in effective_required and not item["required"]
                )
                detail = (
                    "可选输入没有符合条件的记录，本次任务将保留为空"
                    if unavailable_reason == "no_match"
                    else "可选输入的候选记录暂被占用，本次任务将保留为空"
                    if unavailable_reason == "busy"
                    else "因后续必要输入依赖，本次必须提供"
                    if promoted_to_required and outcome != "ready"
                    else issue_details.get(item["inputId"], details.get(outcome))
                )
                ref = chosen.record_ref if chosen is not None else None
                items.append(
                    {
                        "inputId": item["inputId"],
                        "alias": item["alias"],
                        "tableDisplay": table.name
                        if table is not None
                        else "数据表已失效",
                        "recordDisplay": (
                            f"{ref.record_key.type} · {ref.record_key.value}"
                            if ref is not None
                            else None
                        ),
                        "values": (
                            thaw_json(chosen.value.get("values", []))
                            if chosen is not None
                            else []
                        ),
                        "outcome": outcome,
                        "required": item["inputId"] in effective_required,
                        "detail": detail,
                        "scannedCount": (
                            selection.evaluated_candidate_bindings
                            if raw_issue_details.get(item["inputId"])
                            == "record scan budget exceeded"
                            else None
                        ),
                    }
                )
            return {
                "runnable": selection.status == "ready",
                "selectionStatus": selection.status,
                "evaluatedCandidateBindings": selection.evaluated_candidate_bindings,
                "inputs": items,
            }

    def list_tasks(self, project_id: str, batch_id: str):
        with self._factory() as session:
            self._project(session, project_id)
            return SqlAlchemyProjectRuns(session).list_tasks(project_id, batch_id)

    def get_snapshot(self, project_id: str, task_id: str):
        with self._factory() as session:
            self._project(session, project_id)
            return SqlAlchemyProjectRuns(session).snapshot(project_id, task_id)

    @staticmethod
    def _project(session: Session, project_id: str) -> ProjectRow:
        row = session.get(ProjectRow, project_id)
        if row is None or row.lifecycle_state == "deleted":
            raise ProjectRunError("NOT_FOUND", "项目不存在", 404)
        return row


def _present_input_issue(message: str) -> str:
    if message.startswith("ambiguous value ") and "; records " in message:
        value, records = message.removeprefix("ambiguous value ").split("; records ", 1)
        return f"关联值 {value} 同时匹配记录 {records}，请先清理重复数据"
    messages = {
        "input mode is invalid": "输入模式无效",
        "table identity is invalid": "数据表身份无效",
        "table generation is no longer current": "数据表已更新，请重新选择数据表",
        "fixed record reference is invalid": "固定记录引用无效",
        "fixed record reference is outside this input": "固定记录不属于当前输入的数据表",
        "related input has no relation": "关联输入缺少关联条件",
        "relation source is invalid": "关联来源输入无效",
        "same-record relation uses another table generation": "同一记录关联必须使用同一数据表版本",
        "record slot relation is invalid": "记录槽关联已失效",
        "field relation reference is invalid": "字段关联引用已失效",
        "field relation types are incompatible": "关联字段类型不一致",
        "relation type is invalid": "关联方式无效",
        "record slot value is invalid": "记录槽保存的数据引用无效",
        "record scan budget exceeded": "数据表超过单次扫描范围，将由批次调度继续查找",
        "candidate binding budget exceeded": "完整输入组的候选组合过多，请收紧筛选条件",
    }
    return messages.get(message, "输入筛选、字段或状态配置已失效")
