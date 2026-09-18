"""Table bindings, source structure inspection and identity verification."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from .connections import SheetsConnectionService
from .pending import pending


class SheetsBindingService:
    def __init__(
        self, sessions: sessionmaker[Session], connections: SheetsConnectionService
    ) -> None:
        self._sessions = sessions
        self._connections = connections

    def inspect(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise pending("inspections")

    def put_binding(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise pending("bindings")

    def delete_binding(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise pending("bindings")

    def read_binding(self, project_id: str, table_id: str) -> dict[str, Any] | None:
        raise pending("bindings")
