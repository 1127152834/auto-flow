from asyncio import CancelledError
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.proxies.errors import CredentialStoreError, ProxyError
from autoflow.domain.proxies.models import Connection, Health, Projection, ProxyGroup
from autoflow.domain.proxies.ports import (
    ProxyHealthProbe,
    ProxyPanelProvider,
    ProxyUnitOfWork,
)

from .connections import ConnectionService
from .groups import GroupService
from .health import HealthService
from .projections import ProjectionService
from .sync import SyncService, provider_error


class ProxyApplication:
    def __init__(
        self,
        uow_factory: Callable[[], ProxyUnitOfWork],
        credentials: CredentialStore,
        provider: ProxyPanelProvider,
        probe: ProxyHealthProbe | None = None,
    ):
        self._uow_factory = uow_factory
        self._credentials = credentials
        self._provider = provider
        self._probe = probe

    def list_connections(self) -> list[Connection]:
        with self._uow_factory() as uow:
            return ConnectionService(uow.repository, self._credentials).list()

    async def create_connection(self, name: str, api_key: str) -> Connection:
        await self._provider.verify(api_key.strip().encode())
        created = None
        try:
            with self._uow_factory() as uow:
                created = ConnectionService(uow.repository, self._credentials).create(name, api_key)
                uow.commit()
                return created
        except Exception:
            if created is not None:
                self._credentials.delete(created.secret_ref)
            raise

    def update_connection(self, connection_id: str, expected_revision: int, name: str) -> Connection:
        with self._uow_factory() as uow:
            updated = ConnectionService(uow.repository, self._credentials).update(
                connection_id, expected_revision, name
            )
            uow.commit()
            return updated

    async def replace_api_key(
        self, connection_id: str, expected_revision: int, api_key: str
    ) -> Connection:
        await self._provider.verify(api_key.strip().encode())
        new_ref = None
        old_ref = None
        try:
            with self._uow_factory() as uow:
                updated, old_ref, new_ref = ConnectionService(
                    uow.repository, self._credentials
                ).replace_api_key(connection_id, expected_revision, api_key)
                uow.commit()
        except Exception:
            if new_ref is not None:
                self._credentials.delete(new_ref)
            raise
        assert old_ref is not None
        try:
            self._credentials.delete(old_ref)
        except CredentialStoreUnavailableError:
            raise CredentialStoreError(
                "API key was replaced, but the previous secret could not be cleaned up",
                details={"replacement_completed": True},
            ) from None
        return updated

    async def verify_connection(self, connection_id: str) -> Connection:
        with self._uow_factory() as uow:
            service = ConnectionService(uow.repository, self._credentials)
            connection = service.get(connection_id)
            key = service.read_key(connection)
        try:
            await self._provider.verify(key)
        except ProxyError as exc:
            with self._uow_factory() as uow:
                uow.repository.fail_verification(
                    connection_id,
                    connection.secret_ref,
                    provider_error(exc),
                    datetime.now(UTC),
                )
                uow.commit()
            raise
        with self._uow_factory() as uow:
            connection = uow.repository.mark_connection_verified(
                connection_id, connection.secret_ref, datetime.now(UTC)
            )
            uow.commit()
            return connection

    def delete_connection(self, connection_id: str) -> None:
        deleted_secret = None
        try:
            with self._uow_factory() as uow:
                deleted_secret = ConnectionService(uow.repository, self._credentials).delete(connection_id)
                uow.commit()
        except Exception:
            if deleted_secret is not None:
                self._credentials.write(*deleted_secret)
            raise

    async def sync_connection(
        self, connection_id: str
    ) -> tuple[Connection, int, int, Literal["complete", "partial", "unknown"], int | None]:
        with self._uow_factory() as uow:
            service = ConnectionService(uow.repository, self._credentials)
            snapshot = service.get(connection_id)
            key = service.read_key(snapshot)
            sync_token = str(uuid4())
            active = uow.repository.begin_sync(
                connection_id,
                snapshot.secret_ref,
                snapshot.generation,
                sync_token,
                datetime.now(UTC),
            )
            uow.commit()
        try:
            page = await self._provider.list_proxies(key)
        except ProxyError as exc:
            self._record_sync_failure(
                connection_id, snapshot.secret_ref, active.generation, sync_token, provider_error(exc)
            )
            raise
        except CancelledError:
            self._record_sync_failure(
                connection_id,
                snapshot.secret_ref,
                active.generation,
                sync_token,
                provider_error(ProxyError("Proxy sync was cancelled")),
            )
            raise
        try:
            with self._uow_factory() as uow:
                active = uow.repository.validate_sync(
                    connection_id,
                    snapshot.secret_ref,
                    active.generation,
                    sync_token,
                )
                result = SyncService(uow.repository).apply(active, page, active.generation)
                uow.commit()
                return result
        except ProxyError:
            self._record_sync_failure(
                connection_id,
                snapshot.secret_ref,
                active.generation,
                sync_token,
                provider_error(ProxyError("Proxy sync failed")),
            )
            raise
        except Exception:
            self._record_sync_failure(
                connection_id,
                snapshot.secret_ref,
                active.generation,
                sync_token,
                provider_error(ProxyError("Proxy sync failed")),
            )
            raise

    def list_projections(self, **filters) -> tuple[list[Projection], int]:
        with self._uow_factory() as uow:
            return ProjectionService(uow.repository).list_projections(**filters)

    def get_projection(self, projection_id: str) -> Projection:
        with self._uow_factory() as uow:
            return ProjectionService(uow.repository).get(projection_id)

    def update_projection(self, projection_id: str, **changes) -> Projection:
        with self._uow_factory() as uow:
            projection = ProjectionService(uow.repository).update(projection_id, **changes)
            uow.commit()
            return projection

    def projection_references(self, projection_id: str):
        with self._uow_factory() as uow:
            return ProjectionService(uow.repository).references(projection_id)

    async def check_health(self, projection_id: str, protocol: Literal["http", "socks5"]) -> Health:
        if self._probe is None:
            from autoflow.domain.proxies.errors import CapabilityUnavailableError

            raise CapabilityUnavailableError("Local proxy health probe is unavailable")
        with self._uow_factory() as uow:
            target = HealthService(uow.repository).target(projection_id, protocol)
        health = await self._probe.probe(target)
        with self._uow_factory() as uow:
            health = HealthService(uow.repository).record(target, health)
            uow.commit()
            return health

    def list_groups(self, *, q: str | None, offset: int, limit: int) -> tuple[list[ProxyGroup], int]:
        with self._uow_factory() as uow:
            return GroupService(uow.repository).list_groups(q=q, offset=offset, limit=limit)

    def create_group(self, **values) -> ProxyGroup:
        with self._uow_factory() as uow:
            group = GroupService(uow.repository).create(**values)
            uow.commit()
            return group

    def get_group(self, group_id: str) -> ProxyGroup:
        with self._uow_factory() as uow:
            return GroupService(uow.repository).get(group_id)

    def update_group(self, group_id: str, **values) -> ProxyGroup:
        with self._uow_factory() as uow:
            group = GroupService(uow.repository).update(group_id, **values)
            uow.commit()
            return group

    def delete_group(self, group_id: str) -> None:
        with self._uow_factory() as uow:
            GroupService(uow.repository).delete(group_id)
            uow.commit()

    def group_references(self, group_id: str):
        with self._uow_factory() as uow:
            return GroupService(uow.repository).references(group_id)

    def _record_sync_failure(
        self,
        connection_id: str,
        secret_ref: str,
        generation: int,
        sync_token: str,
        error: dict,
    ) -> None:
        with self._uow_factory() as uow:
            uow.repository.fail_sync(
                connection_id,
                secret_ref,
                generation,
                sync_token,
                error,
                datetime.now(UTC),
            )
            uow.commit()
