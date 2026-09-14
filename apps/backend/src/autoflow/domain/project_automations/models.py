from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AutomationRecord:
    automation_id: str
    project_id: str
    workflow_id: str
    name: str
    description: str
    management_revision: int
    input_plan: dict[str, Any]
    parameter_schema: list[dict[str, Any]]
    environment_policy: dict[str, Any]
    run_policy: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    def updated(self, values: dict[str, Any], now: datetime) -> AutomationRecord:
        fields = {
            "name": values["name"],
            "description": values["description"],
            "input_plan": values["inputPlan"],
            "parameter_schema": values["parameterSchema"],
            "environment_policy": values["environmentPolicy"],
            "run_policy": values["runPolicy"],
        }
        changed = any(
            json.dumps(
                getattr(self, key),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            != json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            for key, value in fields.items()
        )
        return replace(
            self,
            **fields,
            management_revision=self.management_revision + int(changed),
            updated_at=now if changed else self.updated_at,
        )


@dataclass(frozen=True)
class ValidationIssue:
    path: list[str]
    code: str
    message: str
    resource: dict[str, Any] | None = None


@dataclass(frozen=True)
class AutomationValidation:
    status: str
    valid: bool
    runnable: bool
    issues: list[ValidationIssue]
    capability_requirements: list[dict[str, Any]]
    checked_at: datetime


def automation_to_dict(value: AutomationRecord) -> dict[str, Any]:
    return {
        "automationId": value.automation_id,
        "projectId": value.project_id,
        "workflowId": value.workflow_id,
        "name": value.name,
        "description": value.description,
        "managementRevision": value.management_revision,
        "inputPlan": value.input_plan,
        "parameterSchema": value.parameter_schema,
        "environmentPolicy": value.environment_policy,
        "runPolicy": value.run_policy,
        "capabilityRequirements": [],
        "createdAt": value.created_at,
        "updatedAt": value.updated_at,
    }
