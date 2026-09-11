from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.proxies.errors import (
    CredentialStoreError,
    ProxyInUseError,
    ProxyNotFoundError,
)
from autoflow.domain.proxies.models import Connection, unavailable_capabilities
from autoflow.domain.proxies.ports import ProxyRepository


class ConnectionService:
    def __init__(self, repository: ProxyRepository, credentials: CredentialStore):
        self.repository = repository
        self.credentials = credentials

    def create(self, name: str, api_key: str) -> Connection:
        key = api_key.strip().encode()
        now = datetime.now(UTC)
        connection_id = str(uuid4())
        secret_ref = f"proxypanel/{connection_id}/api-key"
        try:
            self.credentials.write(secret_ref, key)
        except CredentialStoreUnavailableError:
            raise CredentialStoreError("Credential store is unavailable") from None
        connection = Connection(
            id=connection_id,
            name=name.strip(),
            secret_ref=secret_ref,
            status="connected",
            revision=0,
            generation=0,
            sync_token=None,
            sync_started_at=None,
            last_verified_at=now,
            last_synced_at=None,
            last_error=None,
            capabilities=unavailable_capabilities(),
            created_at=now,
            updated_at=now,
        )
        try:
            self.repository.add_connection(connection)
        except Exception:
            self.credentials.delete(secret_ref)
            raise
        return connection

    def list(self) -> list[Connection]:
        return self.repository.list_connections()

    def get(self, connection_id: str) -> Connection:
        connection = self.repository.get_connection(connection_id)
        if connection is None:
            raise ProxyNotFoundError("ProxyPanel connection was not found")
        return connection

    def update(self, connection_id: str, expected_revision: int, name: str) -> Connection:
        connection = self.get(connection_id)
        self._check_revision(connection, expected_revision)
        updated = replace(
            connection,
            name=name.strip(),
            revision=connection.revision + 1,
            updated_at=datetime.now(UTC),
        )
        self.repository.save_connection(updated, expected_revision, connection.generation)
        return updated

    def replace_api_key(
        self, connection_id: str, expected_revision: int, api_key: str
    ) -> tuple[Connection, str, str]:
        connection = self.get(connection_id)
        self._check_revision(connection, expected_revision)
        key = api_key.strip().encode()
        new_secret_ref = f"proxypanel/{connection.id}/api-key/{uuid4()}"
        try:
            self.credentials.write(new_secret_ref, key)
        except CredentialStoreUnavailableError:
            raise CredentialStoreError("Credential store is unavailable") from None
        now = datetime.now(UTC)
        updated = replace(
            connection,
            secret_ref=new_secret_ref,
            status="connected",
            revision=connection.revision + 1,
            generation=connection.generation + 1,
            sync_token=None,
            sync_started_at=None,
            last_verified_at=now,
            last_error=None,
            updated_at=now,
        )
        try:
            self.repository.save_connection(updated, expected_revision, connection.generation)
            self.repository.mark_connection_projections_stale(connection_id, reset_health=True)
        except Exception:
            self.credentials.delete(new_secret_ref)
            raise
        return updated, connection.secret_ref, new_secret_ref

    def delete(self, connection_id: str) -> tuple[str, bytes]:
        connection = self.get(connection_id)
        reference_count = self.repository.connection_reference_count(connection_id)
        if reference_count:
            raise ProxyInUseError(
                "Connection has proxy references",
                details={"reference_count": reference_count},
            )
        try:
            secret = self.credentials.read(connection.secret_ref)
            if secret is None:
                raise CredentialStoreUnavailableError
            self.credentials.delete(connection.secret_ref)
        except CredentialStoreUnavailableError:
            raise CredentialStoreError("Credential store is unavailable") from None
        try:
            self.repository.delete_connection(connection_id)
        except Exception:
            self.credentials.write(connection.secret_ref, secret)
            raise
        return connection.secret_ref, secret

    def read_key(self, connection: Connection) -> bytes:
        try:
            key = self.credentials.read(connection.secret_ref)
        except CredentialStoreUnavailableError:
            raise CredentialStoreError("Credential store is unavailable") from None
        if not key:
            raise CredentialStoreError("ProxyPanel API key is unavailable")
        return key

    @staticmethod
    def _check_revision(connection: Connection, expected_revision: int) -> None:
        if connection.revision != expected_revision:
            from autoflow.domain.proxies.errors import RevisionConflictError

            raise RevisionConflictError("Connection revision is stale")
