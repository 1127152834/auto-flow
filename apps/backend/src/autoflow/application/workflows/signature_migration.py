"""Re-entrant migration from automation-bound input references to workflow signatures (remediation M2 R2-22).

``{PROJECT_INPUTS['<inputId>']['values']['<inputFieldId>']}`` binds a workflow to one automation's ids.
For each workflow used by exactly one automation, a signature is derived from that automation's
input aliases, value references are rewritten to ``{input.<key>.<field>}`` and the automation's
inputs get the matching ``signatureInput``/``signatureField``. Anything that cannot be confirmed is
reported and left untouched; old references keep working until the M6 migration gate.
Running it again changes nothing.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.signature import KEY
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_data_models import DataFieldRow
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow

_LEGACY = re.compile(r"PROJECT_INPUTS\[['\"]([^'\"]+)['\"]\]")
_VALUE_REFERENCE = re.compile(
    r"(\$?)\{\s*PROJECT_INPUTS\[['\"](?P<input>[^'\"]+)['\"]\]\[['\"]values['\"]\]\[['\"](?P<field>[^'\"]+)['\"]\]\s*\}"
)


def _walk(value: Any, change: Callable[[str], str]) -> Any:
    if isinstance(value, str):
        return change(value)
    if isinstance(value, dict):
        return {key: _walk(item, change) for key, item in value.items()}
    if isinstance(value, list):
        return [_walk(item, change) for item in value]
    return value


def _strings(value: Any) -> list[str]:
    found: list[str] = []

    def collect(text: str) -> str:
        found.append(text)
        return text

    _walk(value, collect)
    return found


def _plan(document: dict[str, Any], automations: list[ProjectAutomationRow], field_types: dict[str, str]) -> dict[str, Any]:
    """Decide what migrating one workflow would do, without changing anything."""
    # Canonical documents wrap the graph in "content"; documents saved by the Studio keep it at the top.
    wrapped = isinstance(document.get("content"), dict)
    content = document["content"] if wrapped else document
    nodes = content.get("nodes", []) if isinstance(content.get("nodes"), list) else []
    legacy = sum(len(_LEGACY.findall(text)) for node in nodes for text in _strings(node.get("data", {})))
    base: dict[str, Any] = {"automationIds": sorted(row.id for row in automations), "legacyReferences": legacy}
    if content.get("signature") is not None:
        return {**base, "status": "migrated", "reason": "已有流程输入", **({"remaining": legacy} if legacy else {})}
    if legacy == 0:
        return {**base, "status": "notNeeded", "reason": "没有旧式输入引用"}
    if len(automations) != 1:
        return {**base, "status": "ambiguous", "reason": "工作流被多个自动化使用，旧引用属于其中一个，无法确定"}
    automation = automations[0]
    inputs = (automation.input_plan or {}).get("inputs", [])
    groups: dict[str, dict[str, Any]] = {}
    for item in inputs:
        key = str(item.get("alias", "")).strip()
        if not KEY.match(key) or any(group["key"] == key for group in groups.values()):
            return {**base, "status": "ambiguous", "reason": f"数据输入别名「{key}」不能作为流程输入标识（需唯一，且只含字母、数字、下划线或中文）"}
        fields: dict[str, dict[str, Any]] = {}
        for binding in item.get("fieldBindings", []):
            field_key = str(binding.get("inputFieldAlias", "")).strip()
            if not KEY.match(field_key) or any(field["key"] == field_key for field in fields.values()):
                return {**base, "status": "ambiguous", "reason": f"字段别名「{field_key}」不能作为字段标识（需唯一，且只含字母、数字、下划线或中文）"}
            fields[binding["inputFieldId"]] = {
                "key": field_key, "name": field_key,
                "type": field_types.get(binding["fieldRef"]["fieldId"], "any"),
                "required": item.get("required") is True, "sensitive": False,
            }
        groups[item["inputId"]] = {"key": key, "name": key, "fields": fields}
    rewritten = 0

    def change(text: str) -> str:
        nonlocal rewritten

        def replace(match: re.Match[str]) -> str:
            nonlocal rewritten
            group = groups.get(match.group("input"))
            field = group["fields"].get(match.group("field")) if group else None
            if group is None or field is None:
                return match.group(0)
            rewritten += 1
            return f"{match.group(1)}{{input.{group['key']}.{field['key']}}}"

        return _VALUE_REFERENCE.sub(replace, text)

    new_nodes = []
    for node in nodes:
        data = _walk(node.get("data", {}), change)
        if isinstance(data, dict) and isinstance(data.get("projectInputTypes"), dict):
            data["projectInputTypes"] = {key: kind for key, kind in data["projectInputTypes"].items() if _LEGACY.search(key) and not _VALUE_REFERENCE.fullmatch("{" + key + "}")}
            if not data["projectInputTypes"]:
                del data["projectInputTypes"]
        new_nodes.append({**node, "data": data})
    remaining = legacy - rewritten
    signature = {
        "inputs": [
            {"key": group["key"], "name": group["name"], "fields": list(group["fields"].values())}
            for group in groups.values()
        ],
        "outputs": [],
    }
    return {
        **base,
        "status": "migratable" if remaining == 0 else "partial",
        "reason": "可以迁移" if remaining == 0 else f"{remaining} 处引用使用记录身份或版本等信息，保留旧格式",
        "rewritten": rewritten,
        "remaining": remaining,
        "_document": (
            {**document, "content": {**content, "nodes": new_nodes, "signature": signature}}
            if wrapped else {**document, "nodes": new_nodes, "signature": signature}
        ),
        "_bindings": {input_id: (group["key"], {fid: field["key"] for fid, field in group["fields"].items()}) for input_id, group in groups.items()},
    }


class SignatureMigration:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def _plans(self, session: Session) -> list[tuple[WorkflowDocumentRow, list[ProjectAutomationRow], dict[str, Any]]]:
        by_workflow: dict[str, list[ProjectAutomationRow]] = {}
        for row in session.scalars(select(ProjectAutomationRow).order_by(ProjectAutomationRow.id)):
            by_workflow.setdefault(row.workflow_id, []).append(row)
        field_types = {row.id: row.type for row in session.scalars(select(DataFieldRow))}
        plans = []
        for workflow_id in sorted(by_workflow):
            workflow = session.get(WorkflowDocumentRow, workflow_id)
            if workflow is not None and isinstance(workflow.document, dict):
                automations = by_workflow[workflow_id]
                plans.append((workflow, automations, _plan(workflow.document, automations, field_types)))
        return plans

    def report(self) -> list[dict[str, Any]]:
        with self._factory() as session:
            return [
                {"workflowId": workflow.id, "workflowName": workflow.name, **{k: v for k, v in plan.items() if not k.startswith("_")}}
                for workflow, _automations, plan in self._plans(session)
            ]

    def apply(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """Migrate every confirmable workflow (or just one) in one transaction; returns the report after."""
        now = datetime.now(UTC)
        with self._factory.begin() as session:
            for workflow, automations, plan in self._plans(session):
                if plan["status"] not in {"migratable", "partial"} or workflow_id not in {None, workflow.id}:
                    continue
                workflow.document = deepcopy(plan["_document"])
                workflow.revision += 1
                workflow.updated_at = now
                automation = automations[0]
                input_plan = deepcopy(automation.input_plan)
                for item in input_plan.get("inputs", []):
                    group_key, fields = plan["_bindings"][item["inputId"]]
                    item["signatureInput"] = group_key
                    for binding in item.get("fieldBindings", []):
                        binding["signatureField"] = fields[binding["inputFieldId"]]
                automation.input_plan = input_plan
                automation.management_revision += 1
                automation.updated_at = now
        report = self.report()
        return [item for item in report if workflow_id in {None, item["workflowId"]}]
