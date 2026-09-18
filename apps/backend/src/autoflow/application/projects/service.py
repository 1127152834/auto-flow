import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from autoflow.domain.projects.models import (
    ProjectError,
    ProjectOperation,
    ProjectRecord,
)
from autoflow.domain.projects.ports import Projects

DEFAULT_RESOURCES = {
    "profileId": None,
    "proxy": {"mode": "sourceDefault"},
    "modelProviderId": None,
}
AVAILABILITY = {
    key: "available"
    for key in ("automations", "data", "runs", "environments", "statistics", "sync")
}


class ProjectService:
    def __init__(self, projects: Projects):
        self.projects = projects

    def create(self, key: str, payload: dict[str, Any]):
        data = _validated(payload, create=True)
        now = datetime.now(UTC)
        record = ProjectRecord(
            str(uuid4()),
            data["name"],
            data["description"],
            data["defaultResources"],
            1,
            "active",
            now,
            now,
        )
        operation = _operation(
            key,
            "createProject",
            {"scope": "workspace", "request": data},
            record.project_id,
            now,
        )
        saved, saved_operation = self.projects.create(record, operation)
        return saved, saved_operation, saved.project_id != record.project_id

    def update(self, project_id: str, key: str, payload: dict[str, Any]):
        if set(payload) == {"expectedManagementRevision"}:
            raise _validation("form", "At least one change is required")
        expected = payload.get("expectedManagementRevision")
        if type(expected) is not int or expected < 1:
            raise _validation(
                "expectedManagementRevision", "Must be a positive integer"
            )
        patch = _validated(
            {k: v for k, v in payload.items() if k != "expectedManagementRevision"},
            create=False,
        )
        now = datetime.now(UTC)
        operation = _operation(
            key,
            "updateProject",
            {
                "scope": "project",
                "target": project_id,
                "request": {**patch, "expectedManagementRevision": expected},
            },
            project_id,
            now,
        )
        saved, saved_operation = self.projects.update(
            project_id, patch, expected, operation
        )
        return saved, saved_operation

    def get(self, project_id):
        value = self.projects.get(project_id)
        if value is None or value.lifecycle_state == "deleted":
            raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
        return value

    def list(self, **query):
        return self.projects.list(**query)

    def open(self, project_id):
        return self.projects.open(project_id, datetime.now(UTC))

    def operation(self, operation_id=None, key=None, project_id=None, workspace=False):
        if project_id is not None:
            self.get(project_id)
        value = self.projects.get_operation(
            operation_id=operation_id,
            key=key,
            project_id=project_id,
            workspace=workspace,
        )
        if value is None:
            raise ProjectError("OPERATION_NOT_FOUND", "Operation was not found", 404)
        return value

    def operations(self, project_id, **query):
        self.get(project_id)
        return self.projects.list_operations(project_id=project_id, **query)

    def workspace_operation(self, key):
        return self.operation(key=key, workspace=True)


def _validated(payload: dict[str, Any], create: bool):
    allowed = {"name", "description", "defaultResources"}
    extra = set(payload) - allowed
    if extra:
        raise _validation(next(iter(extra)), "Unexpected field")
    result = dict(payload)
    if create and "name" not in result:
        raise _validation("name", "Required")
    if "name" in result:
        if not isinstance(result["name"], str):
            raise _validation("name", "Must be a string")
        result["name"] = result["name"].strip()
        if not 1 <= len(result["name"]) <= 36:
            raise _validation("name", "Must contain 1 to 36 Unicode code points")
    if create and "description" not in result:
        result["description"] = ""
    if "description" in result:
        if not isinstance(result["description"], str):
            raise _validation("description", "Must be a string")
        result["description"] = result["description"].strip()
        if len(result["description"]) > 120:
            raise _validation(
                "description", "Must contain at most 120 Unicode code points"
            )
    if create and "defaultResources" not in result:
        result["defaultResources"] = DEFAULT_RESOURCES.copy()
    if "defaultResources" in result:
        _resources(result["defaultResources"])
    return result


def _resources(value):
    if not isinstance(value, dict) or set(value) != {
        "profileId",
        "proxy",
        "modelProviderId",
    }:
        raise _validation(
            "defaultResources", "A complete resource selection is required"
        )
    from uuid import UUID

    for field in ("profileId", "modelProviderId"):
        if value[field] is not None:
            try:
                value[field] = str(UUID(value[field]))
            except (ValueError, TypeError):
                raise _validation(field, "Must be a UUID or null")
    proxy = value["proxy"]
    if not isinstance(proxy, dict) or proxy.get("mode") not in {
        "sourceDefault",
        "none",
        "fixed",
        "pool",
    }:
        raise _validation("proxy", "Invalid proxy mode")
    expected = (
        {"mode"}
        if proxy["mode"] in {"sourceDefault", "none"}
        else {"mode", "proxyId" if proxy["mode"] == "fixed" else "proxyPoolId"}
    )
    if set(proxy) != expected:
        raise _validation("proxy", "Proxy selection does not match mode")
    if len(expected) == 2:
        try:
            proxy[next(iter(expected - {"mode"}))] = str(
                UUID(proxy[next(iter(expected - {"mode"}))])
            )
        except (ValueError, TypeError):
            raise _validation("proxy", "Proxy reference must be a UUID")


def _validation(field, message):
    return ProjectError(
        "VALIDATION_ERROR",
        "Request validation failed",
        422,
        {
            "fields": {field: message},
            "domainCode": "validation_error",
            "retryable": False,
        },
    )


def _operation(key, kind, canonical, project_id, now):
    digest = hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
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
        {"type": "project", "projectId": project_id},
        None,
        None,
        now,
        now,
        None,
    )
