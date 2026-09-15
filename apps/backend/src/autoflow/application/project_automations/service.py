from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from autoflow.domain.project_automations.models import (
    AutomationRecord,
    AutomationValidation,
    ValidationIssue,
)
from autoflow.domain.project_automations.ports import (
    AutomationCapabilityQuery,
    AutomationResourceQuery,
    ProjectAutomations,
)
from autoflow.domain.project_automations.rules import validate_write, validation_error
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.domain.projects.ports import Projects
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import prepare_run


class ProjectAutomationService:
    def __init__(
        self,
        projects: Projects,
        automations: ProjectAutomations,
        workflow_service=None,
        resource_query: AutomationResourceQuery | None = None,
        capability_query: AutomationCapabilityQuery | None = None,
    ):
        self.projects, self.automations = projects, automations
        self.workflow_service, self.resource_query, self.capability_query = (
            workflow_service,
            resource_query,
            capability_query,
        )

    def list(self, project_id: str, **query):
        self._project(project_id)
        return self.automations.list(project_id, **query)

    def create(self, project_id: str, key: str, payload: dict[str, Any]):
        data = validate_write(payload, project_id)
        now = datetime.now(UTC)
        record = AutomationRecord(
            str(uuid4()),
            project_id,
            data["workflowId"],
            data["name"],
            data["description"],
            1,
            data["inputPlan"],
            data["parameterSchema"],
            data["environmentPolicy"],
            data["runPolicy"],
            now,
            now,
        )
        operation = _operation(
            key,
            "createAutomation",
            project_id,
            record.automation_id,
            {"scope": "project", "projectId": project_id, "request": data},
            now,
        )
        return self.automations.create(record, operation)

    def get(self, project_id: str, automation_id: str):
        self._project(project_id)
        value = self.automations.get(project_id, automation_id)
        if value is None:
            raise ProjectError("AUTOMATION_NOT_FOUND", "Automation was not found", 404)
        return value

    def update(
        self, project_id: str, automation_id: str, key: str, payload: dict[str, Any]
    ):
        if "expectedManagementRevision" not in payload:
            raise validation_error("expectedManagementRevision", "Required")
        expected = payload["expectedManagementRevision"]
        if type(expected) is not int or expected < 1:
            raise validation_error(
                "expectedManagementRevision", "Must be a positive integer"
            )
        data = validate_write(
            {
                key: value
                for key, value in payload.items()
                if key != "expectedManagementRevision"
            },
            project_id,
        )
        canonical = {
            "scope": "automation",
            "projectId": project_id,
            "automationId": automation_id,
            "request": {**data, "expectedManagementRevision": expected},
        }
        operation = _operation(
            key,
            "updateAutomation",
            project_id,
            automation_id,
            canonical,
            datetime.now(UTC),
        )
        return self.automations.update(
            project_id, automation_id, data, expected, operation
        )

    def validation(self, project_id: str, automation_id: str) -> AutomationValidation:
        automation = self.get(project_id, automation_id)
        now = datetime.now(UTC)
        if self.workflow_service is None or self.resource_query is None:
            issue = ValidationIssue(
                [], "CORE_UNAVAILABLE", "暂时无法检查运行条件，仍可保存管理配置"
            )
            return AutomationValidation("unavailable", False, False, [issue], [], now)
        assert self.resource_query is not None
        issues: list[ValidationIssue] = []
        workflow_blocked = False
        try:
            workflow = self.workflow_service.get(automation.workflow_id)
            prepare_run(workflow.document)
        except WorkflowError as error:
            workflow_blocked = True
            if getattr(error, "issues", None):
                issues.extend(
                    ValidationIssue(issue.path, issue.code, issue.message)
                    for issue in error.issues
                )
            elif getattr(error, "code", None) == "WORKFLOW_NOT_FOUND":
                issues.append(
                    ValidationIssue(
                        ["workflowId"],
                        "WORKFLOW_NOT_FOUND",
                        "Workflow was not found",
                        {"type": "workflow", "workflowId": automation.workflow_id},
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        ["workflowId"],
                        "WORKFLOW_UNAVAILABLE",
                        "Workflow could not be inspected",
                    )
                )
        if automation.environment_policy["source"] != "newFromProfile":
            issues.append(
                ValidationIssue(
                    ["environmentPolicy", "source"],
                    "ENVIRONMENT_SOURCE_NOT_SUPPORTED",
                    "当前仅支持从浏览器配置创建临时环境",
                )
            )
        for item in self.resource_query.inspect_resources(automation):
            issues.append(
                ValidationIssue(
                    item.get("path", []),
                    item["code"],
                    item["message"],
                    item.get("resource"),
                )
            )
        if self.capability_query is None:
            issues.append(ValidationIssue(
                [], "CORE_UNAVAILABLE", "运行准入尚未开放，仍可保存管理配置"
            ))
            return AutomationValidation("unavailable", False, False, issues, [], now)
        capabilities = self.capability_query.inspect_capabilities(
            automation.workflow_id
        )
        data_capability = next(
            (
                item
                for item in capabilities
                if item.get("capability") == "project.data"
            ),
            None,
        )
        if automation.input_plan["inputs"] and not (
            data_capability and data_capability.get("available")
        ):
            issues.append(
                ValidationIssue(
                    ["inputPlan", "inputs"],
                    "PM4_INPUTS_NOT_SUPPORTED",
                    "已保存数据输入；当前执行端未开放项目数据能力",
                )
            )
        for item in capabilities:
            if item.get("required") and not item.get("available"):
                issues.append(
                    ValidationIssue(
                        ["capabilityRequirements"],
                        "CAPABILITY_UNAVAILABLE",
                        item.get("reason")
                        or f"Capability {item['capability']} is unavailable",
                    )
                )
        blocker_codes = {
            "PM4_INPUTS_NOT_SUPPORTED",
            "ENVIRONMENT_SOURCE_NOT_SUPPORTED",
            "WORKFLOW_NOT_FOUND",
            "WORKFLOW_UNAVAILABLE",
            "CAPABILITY_UNAVAILABLE",
        }
        status = (
            "blocked"
            if workflow_blocked
            or any(issue.code in blocker_codes or issue.resource for issue in issues)
            else ("draft" if issues else "ready")
        )
        return AutomationValidation(
            status,
            status in {"ready", "draft"},
            status == "ready",
            issues,
            capabilities,
            now,
        )

    def _project(self, project_id):
        value = self.projects.get(project_id)
        if value is None or value.lifecycle_state == "deleted":
            raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
        return value

    def _writable_project(self, project_id):
        project = self._project(project_id)
        if project.lifecycle_state == "closing":
            raise ProjectError("PROJECT_CLOSING", "Project is closing", 423)
        if project.lifecycle_state != "active":
            raise ProjectError("LIFECYCLE_CONFLICT", "Project cannot be edited", 409)
        return project


def _operation(key, kind, project_id, automation_id, canonical, now):
    digest = hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    return ProjectOperation(
        str(uuid4()),
        project_id,
        key.strip(),
        kind,
        digest,
        "running",
        1,
        {"type": "automation", "projectId": project_id, "automationId": automation_id},
        None,
        None,
        now,
        now,
        None,
    )
