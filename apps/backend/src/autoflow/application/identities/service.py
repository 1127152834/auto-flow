"""Identity management for a project (remediation M4 R4-09)."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities

MAX_BATCH = 1000


def seed_fingerprint(seed: int) -> str:
    """A short, stable label for a seed; the raw value never needs to reach the page."""
    return hashlib.sha256(f"autoflow-seed:{seed}".encode()).hexdigest()[:10]


class IdentityService:
    def __init__(self, identities: SqlAlchemyIdentities, projects: Any, records: Any = None) -> None:
        self.identities, self.projects, self.records = identities, projects, records

    def list(self, project_id: str) -> list[dict[str, Any]]:
        self._project(project_id)
        return [_view(identity, extra) for identity, extra in self.identities.list(project_id)]

    def create(self, project_id: str, key: str, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Idempotent by key: the same key always names the same identity."""
        self._writable(project_id)
        identity_id = str(uuid5(NAMESPACE_URL, f"autoflow:{project_id}:identity:{key}"))
        existing = self.identities.get(project_id, identity_id, missing_ok=True)
        if existing is not None:
            return self._one(project_id, existing.identity_id), True
        created = self.identities.create(
            project_id, payload.get("name", ""), template_profile_id=payload.get("templateProfileId"),
            region=payload.get("region"), identity_id=identity_id,
        )
        return self._one(project_id, created.identity_id), False

    def create_from_records(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """One identity per data row; a row that already has one keeps it (re-running creates nothing)."""
        self._writable(project_id)
        rows = payload.get("rows")
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_BATCH:
            raise ProjectError("VALIDATION_ERROR", f"一次最多为 {MAX_BATCH} 行创建身份", 422, {"fields": {"rows": "1–1000 行"}})
        table_id = payload.get("tableId")
        if not isinstance(table_id, str) or not table_id:
            raise ProjectError("VALIDATION_ERROR", "请选择数据表", 422, {"fields": {"tableId": "必填"}})
        created = kept = 0
        identities = []
        for row in rows:
            key, name = row.get("recordKey"), row.get("name")
            if not isinstance(key, str) or not key or not isinstance(name, str):
                raise ProjectError("VALIDATION_ERROR", "每行需要记录键和名称", 422, {"fields": {"rows": "记录键与名称必填"}})
            identity_id = str(uuid5(NAMESPACE_URL, f"autoflow:{project_id}:identity-row:{table_id}:{key}"))
            existing = self.identities.get(project_id, identity_id, missing_ok=True)
            if existing is None:
                existing = self.identities.create(
                    project_id, name, template_profile_id=payload.get("templateProfileId"),
                    region=payload.get("region"), identity_id=identity_id,
                )
                created += 1
            else:
                kept += 1
            identities.append({"recordKey": key, "identityId": existing.identity_id})
        return {"created": created, "kept": kept, "identities": identities}

    def rename(self, project_id: str, identity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._writable(project_id)
        self.identities.rename(project_id, identity_id, payload.get("name", ""))
        return self._one(project_id, identity_id)

    def regenerate_seed(self, project_id: str, identity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Needs an explicit confirmation: sites that remember the device may ask to verify again."""
        self._writable(project_id)
        if payload.get("confirmRegenerate") is not True:
            raise ProjectError(
                "CONFIRMATION_REQUIRED", "重新生成指纹会让网站把它当作新设备，可能要求重新验证，请确认后再操作", 422,
                {"fields": {"confirmRegenerate": "需要确认"}},
            )
        self.identities.regenerate_seed(project_id, identity_id)
        return self._one(project_id, identity_id)

    def reset_health(self, project_id: str, identity_id: str) -> dict[str, Any]:
        self._writable(project_id)
        self.identities.reset_health(project_id, identity_id)
        return self._one(project_id, identity_id)

    def delete(self, project_id: str, identity_id: str) -> None:
        self._writable(project_id)
        self.identities.delete(project_id, identity_id)

    def _one(self, project_id: str, identity_id: str) -> dict[str, Any]:
        for identity, extra in self.identities.list(project_id):
            if identity.identity_id == identity_id:
                return _view(identity, extra)
        raise ProjectError("IDENTITY_NOT_FOUND", "身份不存在", 404)

    def _project(self, project_id: str) -> Any:
        value = self.projects.get(project_id)
        if value is None or value.lifecycle_state == "deleted":
            raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
        return value

    def _writable(self, project_id: str) -> None:
        project = self._project(project_id)
        if project.lifecycle_state == "closing":
            raise ProjectError("PROJECT_CLOSING", "Project is closing", 423)
        if project.lifecycle_state != "active":
            raise ProjectError("LIFECYCLE_CONFLICT", "Project cannot be edited", 409)


def _view(identity: Any, extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "identityId": identity.identity_id,
        "projectId": identity.project_id,
        "name": identity.name,
        "seedFingerprint": seed_fingerprint(identity.seed),
        "legacySharedSeed": bool(extra["legacyShared"]),
        "templateProfileId": identity.template_profile_id,
        "environmentId": identity.environment_id,
        "region": extra["region"],
        "health": extra["health"],
        "createdAt": identity.created_at,
        "updatedAt": identity.updated_at,
    }
