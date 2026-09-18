"""Google connections owned by a project. Credentials never leave the keystore."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.credentials import CredentialStore

from .pending import pending


class SheetsConnectionService:
    def __init__(
        self, sessions: sessionmaker[Session], credentials: CredentialStore
    ) -> None:
        self._sessions = sessions
        self._credentials = credentials

    def list_connections(self, project_id: str) -> dict[str, Any]:
        raise pending("connections")

    def create_connection(
        self, project_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise pending("connections")

    def delete_connection(
        self, project_id: str, connection_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise pending("connections")
