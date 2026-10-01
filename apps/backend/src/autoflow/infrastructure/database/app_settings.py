"""Versioned application settings (remediation M1, R1-07). Revisions use compare-and-set."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from .models import Base


class AppSettingRow(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AppSettingConflict(Exception):
    def __init__(self, current_revision: int) -> None:
        super().__init__(f"Setting revision is stale (current {current_revision})")
        self.current_revision = current_revision


class SqlAlchemyAppSettings:
    """Owns its sessions, so every call is safe to run in a worker thread."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def get(self, key: str) -> tuple[Any | None, int]:
        with self._factory() as session:
            row = session.get(AppSettingRow, key)
            return (None, 0) if row is None else (row.value, row.revision)

    def put(self, key: str, value: Any, expected_revision: int) -> int:
        now = datetime.now(UTC)
        if expected_revision == 0:
            try:
                with self._factory.begin() as session:
                    session.add(AppSettingRow(key=key, value=value, revision=1, updated_at=now))
                return 1
            except IntegrityError:
                raise AppSettingConflict(self.get(key)[1]) from None
        with self._factory.begin() as session:
            updated = session.execute(
                update(AppSettingRow)
                .where(AppSettingRow.key == key, AppSettingRow.revision == expected_revision)
                .values(value=value, revision=expected_revision + 1, updated_at=now)
            ).rowcount
        if updated != 1:
            raise AppSettingConflict(self.get(key)[1])
        return expected_revision + 1
