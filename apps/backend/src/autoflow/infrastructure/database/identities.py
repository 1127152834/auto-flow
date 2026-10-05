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
    ) -> Identity:
        """A new identity always gets a newly registered seed; the caller cannot choose one."""
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
                row = self._insert(session, project_id, name, registry.id, template_profile_id, region)
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

    def _insert(
        self, session: Session, project_id: str, name: str, seed_id: str,
        template_profile_id: str | None, region: dict[str, Any] | None,
    ) -> IdentityRow:
        cleaned = name.strip()
        if not 1 <= len(cleaned) <= 80:
            raise ProjectError("VALIDATION_ERROR", "身份名称需为 1–80 个字符", 422, {"fields": {"name": "1–80 个字符"}})
        now = datetime.now(UTC)
        row = IdentityRow(
            id=str(uuid4()), project_id=project_id, name=cleaned, name_key=cleaned.casefold(),
            template_profile_id=template_profile_id, seed_id=seed_id, region=dict(region or {}),
            proxy_binding=None, environment_id=None, health=dict(DEFAULT_HEALTH), created_at=now, updated_at=now,
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as error:
            session.rollback()
            raise ProjectError("IDENTITY_NAME_CONFLICT", "项目中已有同名身份", 409, {"fields": {"name": "名称已被使用"}}) from error
        return row


def _identity(row: IdentityRow, seed: int) -> Identity:
    return Identity(
        row.id, row.project_id, row.name, seed, row.template_profile_id, row.environment_id,
        _aware(row.created_at), _aware(row.updated_at),
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
