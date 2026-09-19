"""Resolve a stored Google connection into an authorized Sheets client."""

from __future__ import annotations

from collections.abc import Callable

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_sync import SqlAlchemyProjectSync
from autoflow.providers.data import google_auth
from autoflow.providers.data.google_sheets import SheetsClient, SheetsTransport

TransportFactory = Callable[[Callable[[], str]], SheetsTransport]


class GoogleAccess:
    """The single place where a connection becomes a usable Sheets client."""

    def __init__(
        self,
        sync: SqlAlchemyProjectSync,
        credentials: CredentialStore,
        tokens: google_auth.TokenTransport,
        transports: TransportFactory,
    ) -> None:
        self._sync, self._credentials = sync, credentials
        self._tokens, self._transports = tokens, transports

    def credential(self, project: str, connection_id: str) -> google_auth.GoogleCredential:
        row = self._sync.connection(project, connection_id)
        try:
            raw = self._credentials.read(row.credential_key)
        except CredentialStoreUnavailableError as error:
            raise _unavailable() from error
        if raw is None:
            self._sync.set_connection_state(
                project, connection_id, state="missing", readable=False, writable=False
            )
            raise ProjectError(
                "GOOGLE_CREDENTIAL_MISSING", "该连接的凭据已不存在，请重新授权。", 409
            )
        try:
            return google_auth.GoogleCredential.from_secret(raw)
        except google_auth.GoogleAuthError as error:
            self._sync.set_connection_state(
                project, connection_id, state="invalid", readable=False, writable=False
            )
            raise ProjectError(error.code, error.message, 409) from error

    def client(self, project: str, connection_id: str) -> SheetsClient:
        credential = self.credential(project, connection_id)

        def token() -> str:
            try:
                return google_auth.access_token(credential, self._tokens)
            except google_auth.GoogleAuthError as error:
                self._sync.set_connection_state(
                    project,
                    connection_id,
                    state="loginRequired",
                    readable=False,
                    writable=credential.writable,
                )
                raise ProjectError(error.code, error.message, 409) from error

        return SheetsClient(self._transports(token))

    def require_writable(self, project: str, connection_id: str) -> None:
        if not self.credential(project, connection_id).writable:
            raise ProjectError(
                "GOOGLE_NOT_WRITABLE",
                "该连接只有读取权限，请重新授权并允许写入。",
                409,
            )


def _unavailable() -> ProjectError:
    return ProjectError(
        "CREDENTIAL_STORE_UNAVAILABLE", "当前系统凭据存储不可用。", 503
    )
