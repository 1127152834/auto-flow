"""Match a draft input plan against current project data (remediation M5 5B-A4, B4).

Read-only and independent of ``input-preview``: nothing is claimed, held or written. The domain filter
stays authoritative (the SQL predicate only narrows). ``sample`` follows key order, not the plan's
``orderBy``: it shows what kind of rows match, not which one would run first. Callers run it in a thread.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_automations.rules import (
    processing_input,
    validate_input_plan,
)
from autoflow.domain.project_data.query import matches, validate_filter
from autoflow.domain.project_runs.input_match import (
    SAMPLE_ROWS,
    sample_row,
    unprocessed_count,
)
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.signature import document_signature, parse_signature
from autoflow.infrastructure.credentials.redaction import redact_sensitive_value
from autoflow.infrastructure.database.core_workflows import _record as workflow_record
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_filter_sql import translate_filter
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
)
from autoflow.infrastructure.database.record_ledger_models import (
    AutomationRecordLedgerRow,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow

Key = tuple[str, str]


class InputMatchService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def match(self, project_id: str, automation_id: str, input_plan: dict[str, Any]) -> dict[str, Any]:
        with self._factory() as session:
            project = session.get(ProjectRow, project_id)
            automation = session.get(ProjectAutomationRow, automation_id)
            if project is None or project.lifecycle_state == "deleted":
                raise ProjectRunError("NOT_FOUND", "项目不存在", 404)
            if automation is None or automation.project_id != project_id:
                raise ProjectRunError("NOT_FOUND", "自动化不存在", 404)
            plan = validate_input_plan(input_plan, project_id)  # 422 for a plan the editor should not have sent
            groups = _sensitive_by_group(session, automation.workflow_id)
            primary = processing_input(plan)
            return {"inputs": [
                _match_input(session, project_id, automation_id, item, groups, item["inputId"] == primary)
                for item in plan["inputs"]
            ]}


def _match_input(
    session: Session, project_id: str, automation_id: str, item: dict[str, Any],
    sensitive_groups: dict[str, set[str]], is_primary: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "inputId": item["inputId"], "alias": item["alias"], "outcome": "counted",
        "matchedCount": None, "unprocessedCount": None, "sample": [],
    }
    if item["mode"] == "related":
        return {**result, "outcome": "dependsOnOtherInput"}
    table_id, generation = item["tableId"], item["datasetGeneration"]
    table = session.scalar(select(DataTableRow).where(
        DataTableRow.project_id == project_id, DataTableRow.id == table_id,
        DataTableRow.published.is_(True), DataTableRow.current_generation == generation,
    ))
    if table is None:
        return {**result, "outcome": "tableUnavailable"}
    field_types = dict(session.execute(select(DataFieldRow.id, DataFieldRow.type).where(
        DataFieldRow.project_id == project_id, DataFieldRow.table_id == table_id,
        DataFieldRow.dataset_generation == generation,
    )).tuples().all())
    statuses = set(session.scalars(select(DataStatusRow.id).where(
        DataStatusRow.project_id == project_id, DataStatusRow.table_id == table_id, DataStatusRow.deleted.is_(False),
    )))
    try:
        condition = validate_filter(item.get("filter"), field_types, statuses)
    except ProjectError:
        return {**result, "outcome": "filterInvalid"}
    query = select(DataRecordRow.key_type, DataRecordRow.key_value, DataRecordRow.values_json, DataRecordRow.status_id).where(
        DataRecordRow.project_id == project_id, DataRecordRow.table_id == table_id,
        DataRecordRow.dataset_generation == generation, DataRecordRow.deleted.is_(False),
        translate_filter(condition).clause,
    )
    fixed = item.get("fixedRecord")
    if fixed is not None:
        query = query.where(DataRecordRow.key_type == fixed["recordKey"]["type"],
                            DataRecordRow.key_value == str(fixed["recordKey"]["value"]))
    keys: list[Key] = []
    sample: list[dict[str, Any]] = []
    sensitive = sensitive_groups.get(item.get("signatureInput") or "", set())
    for key_type, key_value, values, status_id in session.execute(query.order_by(DataRecordRow.key_value)).yield_per(1000):
        if matches(condition, values, status_id):
            keys.append((key_type, key_value))
            if len(sample) < SAMPLE_ROWS:
                sample.append(redact_sensitive_value(sample_row(item["fieldBindings"], values, sensitive_fields=sensitive)))
    result.update(matchedCount=len(keys), sample=sample)
    if is_primary:
        result["unprocessedCount"] = unprocessed_count(
            keys, _succeeded(session, automation_id, item["inputId"], table_id, generation),
            _occupied(session, automation_id, table_id, generation),
        )
    return result


def _succeeded(session: Session, automation_id: str, input_id: str, table_id: str, generation: str) -> set[Key]:
    return set(session.execute(select(AutomationRecordLedgerRow.key_type, AutomationRecordLedgerRow.key_value).where(
        AutomationRecordLedgerRow.automation_id == automation_id,
        AutomationRecordLedgerRow.processing_input_id == input_id,
        AutomationRecordLedgerRow.table_id == table_id,
        AutomationRecordLedgerRow.dataset_generation == generation,
        AutomationRecordLedgerRow.state == "succeeded",
    )).tuples().all())


def _occupied(session: Session, automation_id: str, table_id: str, generation: str) -> set[Key]:
    """Rows a task of this automation holds right now (a held or reconciling record lease)."""
    ref = ProjectRecordLeaseRow.record_ref
    return set(session.execute(
        select(func.json_extract(ref, "$.recordKey.type"), func.json_extract(ref, "$.recordKey.value"))
        .join(ProjectBatchRow, ProjectBatchRow.id == ProjectRecordLeaseRow.batch_id)
        .where(
            ProjectBatchRow.automation_id == automation_id,
            ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
            func.json_extract(ref, "$.tableId") == table_id,
            func.json_extract(ref, "$.datasetGeneration") == generation,
        )
    ).tuples().all())


def _sensitive_by_group(session: Session, workflow_id: str) -> dict[str, set[str]]:
    """Workflow input group key -> keys of its sensitive fields (empty when the workflow has no signature)."""
    row = session.get(WorkflowDocumentRow, workflow_id)
    if row is None:
        return {}
    signature, _issues = parse_signature(document_signature(workflow_record(row).document))
    if signature is None:
        return {}
    return {group.key: {field.key for field in group.fields if field.sensitive} for group in signature.inputs}
