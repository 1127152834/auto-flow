"""Local change intents, remote sends and the confirmation evidence behind them."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from .bindings import SheetsBindingService
from .pending import pending


class SheetsSyncService:
    def __init__(
        self, sessions: sessionmaker[Session], bindings: SheetsBindingService
    ) -> None:
        self._sessions = sessions
        self._bindings = bindings

    def state(self, project_id: str, table_id: str) -> dict[str, Any]:
        raise pending("sync-state")

    def pull(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise pending("pull")

    def push(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise pending("push")

    def pause(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise pending("pause")

    def resume(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise pending("resume")

    def list_operations(
        self,
        project_id: str,
        table_id: str,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        raise pending("operations")

    def read_operation(
        self, project_id: str, table_id: str, sync_operation_id: str
    ) -> dict[str, Any]:
        raise pending("operations")

    def reconcile(
        self,
        project_id: str,
        table_id: str,
        sync_operation_id: str,
        key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raise pending("reconcile")

    def abandon(
        self,
        project_id: str,
        table_id: str,
        sync_operation_id: str,
        key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raise pending("abandon")
