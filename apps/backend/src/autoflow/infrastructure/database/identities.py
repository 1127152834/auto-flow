"""Identity persistence with the global seed registry (remediation M4 R4-01, R4-02)."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.identities.models import Identity
from autoflow.domain.identities.seeds import SEED_MAX, SEED_MIN, valid_seed
from autoflow.domain.projects.models import ProjectError

from .identity_models import IdentityRow, SeedRegistryRow

ALLOCATION_ATTEMPTS = 8
DEFAULT_HEALTH: dict[str, Any] = {"lastLoginSuccessAt": None, "consecutiveFailures": 0, "banned": False}


def _secure_randint(low: int, high: int) -> int:
    return low + secrets.randbelow(high - low + 1)


class SqlAlchemyIdentities:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def create(
        self, project_id: str, name: str, *, template_profile_id: str | None = None,
        region: dict[str, Any] | None = None, randint: Callable[[int, int], int] = _secure_randint,
        identity_id: str | None = None,
    ) -> Identity:
        """A new identity always gets a newly registered seed; the caller cannot choose one.

        With ``identity_id`` the call is idempotent: an identity already stored under that id is
        returned unchanged (a retried request or a re-run batch never makes a second identity).
        """
        if identity_id is not None and (existing := self.get(project_id, identity_id, missing_ok=True)) is not None:
            return existing
        for _attempt in range(ALLOCATION_ATTEMPTS):
            seed = randint(SEED_MIN, SEED_MAX)
            if not valid_seed(seed):
                raise ValueError("seed source returned a value outside the identity range")
            with self._factory() as session:
                try:
                    registry = SeedRegistryRow(id=str(uuid4()), seed_value=seed, legacy_shared=False, created_at=datetime.now(UTC))
                    session.add(registry)
                    session.flush()
                except IntegrityError:
                    session.rollback()
                    continue  # already registered, by anyone and at any time: draw again
                row = self._insert(session, project_id, name, registry.id, template_profile_id, region, identity_id)
                session.commit()
                return _identity(row, seed)
        raise ProjectError("SEED_ALLOCATION_FAILED", "暂时无法分配新的指纹种子，请重试", 503)

    def adopt_legacy_seed(
        self, project_id: str, name: str, seed: int, *, template_profile_id: str | None = None,
        region: dict[str, Any] | None = None,
    ) -> Identity:
        """Migration only: keep an older environment's seed, sharing its registration if it repeats."""
        if not valid_seed(seed):
            raise ValueError("legacy seed is outside the identity range")
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            registry = session.scalar(select(SeedRegistryRow).where(SeedRegistryRow.seed_value == seed))
            if registry is None:
                registry = SeedRegistryRow(id=str(uuid4()), seed_value=seed, legacy_shared=False, created_at=datetime.now(UTC))
                session.add(registry)
                session.flush()
            elif session.scalar(select(func.count()).select_from(IdentityRow).where(IdentityRow.seed_id == registry.id)):
                registry.legacy_shared = True
            row = self._insert(session, project_id, name, registry.id, template_profile_id, region)
            session.commit()
            return _identity(row, seed)

    def seed_report(self, project_id: str) -> list[dict[str, Any]]:
        """Seeds shared by more than one identity of the project (the migration report)."""
        with self._factory() as session:
            rows = session.execute(
                select(SeedRegistryRow.seed_value, IdentityRow.id)
                .join(IdentityRow, IdentityRow.seed_id == SeedRegistryRow.id)
                .where(SeedRegistryRow.legacy_shared.is_(True), IdentityRow.project_id == project_id)
                .order_by(SeedRegistryRow.seed_value)
            ).all()
        report: dict[int, list[str]] = {}
        for seed, identity_id in rows:
            report.setdefault(seed, []).append(identity_id)
        return [{"seed": seed, "legacyShared": True, "identities": sorted(ids)} for seed, ids in report.items()]

    def get(self, project_id: str, identity_id: str, *, missing_ok: bool = False) -> Identity | None:
        with self._factory() as session:
            found = session.execute(
                select(IdentityRow, SeedRegistryRow.seed_value)
                .join(SeedRegistryRow, SeedRegistryRow.id == IdentityRow.seed_id)
                .where(IdentityRow.id == identity_id, IdentityRow.project_id == project_id)
            ).first()
        if found is None:
            if missing_ok:
                return None
            raise ProjectError("IDENTITY_NOT_FOUND", "身份不存在", 404)
        return _identity(found[0], found[1])

    def require(self, project_id: str, identity_id: str) -> Identity:
        found = self.get(project_id, identity_id)
        assert found is not None
        return found

    def list(self, project_id: str) -> list[tuple[Identity, dict[str, Any]]]:
        """Identities with their health, region and whether their seed is a kept older duplicate."""
        with self._factory() as session:
            rows = session.execute(
                select(IdentityRow, SeedRegistryRow.seed_value, SeedRegistryRow.legacy_shared)
                .join(SeedRegistryRow, SeedRegistryRow.id == IdentityRow.seed_id)
                .where(IdentityRow.project_id == project_id)
                .order_by(IdentityRow.name_key)
            ).all()
        return [(_identity(row, seed), {"health": dict(row.health), "legacyShared": shared, "region": dict(row.region)}) for row, seed, shared in rows]

    def rename(self, project_id: str, identity_id: str, name: str) -> Identity:
        with self._factory() as session:
            row = self._row(session, project_id, identity_id)
            cleaned = _name(name)
            row.name, row.name_key, row.updated_at = cleaned, cleaned.casefold(), datetime.now(UTC)
            try:
                session.commit()
            except IntegrityError as error:
                raise _name_conflict() from error
        return self.require(project_id, identity_id)

    def regenerate_seed(self, project_id: str, identity_id: str, *, randint: Callable[[int, int], int] = _secure_randint) -> Identity:
        """Give the identity a brand-new seed; the old registration stays registered and is never reused."""
        for _attempt in range(ALLOCATION_ATTEMPTS):
            seed = randint(SEED_MIN, SEED_MAX)
            with self._factory() as session:
                row = self._row(session, project_id, identity_id)
                try:
                    registry = SeedRegistryRow(id=str(uuid4()), seed_value=seed, legacy_shared=False, created_at=datetime.now(UTC))
                    session.add(registry)
                    session.flush()
                except IntegrityError:
                    session.rollback()
                    continue
                row.seed_id, row.updated_at = registry.id, datetime.now(UTC)
                session.commit()
                return self.require(project_id, identity_id)
        raise ProjectError("SEED_ALLOCATION_FAILED", "暂时无法分配新的指纹种子，请重试", 503)

    def reset_health(self, project_id: str, identity_id: str) -> None:
        with self._factory() as session:
            row = self._row(session, project_id, identity_id)
            row.health, row.updated_at = dict(DEFAULT_HEALTH), datetime.now(UTC)
            session.commit()

    def delete(self, project_id: str, identity_id: str) -> None:
        with self._factory() as session:
            row = self._row(session, project_id, identity_id)
            if row.environment_id is not None:
                raise ProjectError("IDENTITY_HAS_ENVIRONMENT", "身份仍保存着登录环境，请先删除该环境", 409)
            session.delete(row)
            session.commit()

    @staticmethod
    def _row(session: Session, project_id: str, identity_id: str) -> IdentityRow:
        row = session.get(IdentityRow, identity_id)
        if row is None or row.project_id != project_id:
            raise ProjectError("IDENTITY_NOT_FOUND", "身份不存在", 404)
        return row

    def _insert(
        self, session: Session, project_id: str, name: str, seed_id: str,
        template_profile_id: str | None, region: dict[str, Any] | None, identity_id: str | None = None,
    ) -> IdentityRow:
        cleaned = _name(name)
        now = datetime.now(UTC)
        row = IdentityRow(
            id=identity_id or str(uuid4()), project_id=project_id, name=cleaned, name_key=cleaned.casefold(),
            template_profile_id=template_profile_id, seed_id=seed_id, region=dict(region or {}),
            proxy_binding=None, environment_id=None, health=dict(DEFAULT_HEALTH), created_at=now, updated_at=now,
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as error:
            session.rollback()
            raise _name_conflict() from error
        return row


def _name(value: str) -> str:
    cleaned = value.strip() if isinstance(value, str) else ""
    if not 1 <= len(cleaned) <= 80:
        raise ProjectError("VALIDATION_ERROR", "身份名称需为 1–80 个字符", 422, {"fields": {"name": "1–80 个字符"}})
    return cleaned


def _name_conflict() -> ProjectError:
    return ProjectError("IDENTITY_NAME_CONFLICT", "项目中已有同名身份", 409, {"fields": {"name": "名称已被使用"}})


def _identity(row: IdentityRow, seed: int) -> Identity:
    return Identity(
        row.id, row.project_id, row.name, seed, row.template_profile_id, row.environment_id,
        _aware(row.created_at), _aware(row.updated_at),
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
