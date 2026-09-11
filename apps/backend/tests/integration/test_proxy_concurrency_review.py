from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from autoflow.application.proxies.connections import ConnectionService
from autoflow.application.proxies.groups import GroupService
from autoflow.application.proxies.sync import SyncService
from autoflow.domain.proxies.errors import RevisionConflictError
from autoflow.domain.proxies.models import (
    Connection,
    Endpoint,
    Health,
    ProviderPage,
    ProviderProxy,
    unavailable_capabilities,
)
from autoflow.infrastructure.database.proxies import SqlAlchemyProxyRepository
from autoflow.infrastructure.database.proxy_models import (
    ProxyConnectionRow,
    ProxyGroupDetailRow,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


class MemoryCredentials:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def read(self, key: str) -> bytes | None:
        return self.values.get(key)

    def write(self, key: str, value: bytes) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


class PageProvider:
    def __init__(self, page: ProviderPage) -> None:
        self.page = page

    async def verify(self, api_key: bytes) -> ProviderPage:
        return ProviderPage((), "unknown")

    async def list_proxies(self, api_key: bytes) -> ProviderPage:
        return self.page


def _connection() -> Connection:
    now = datetime.now(UTC)
    return Connection(
        id="connection-1",
        name="Main",
        secret_ref="proxypanel/connection-1/api-key",
        status="connected",
        revision=0,
        generation=0,
        last_verified_at=now,
        last_synced_at=None,
        last_error=None,
        capabilities=unavailable_capabilities(),
        created_at=now,
        updated_at=now,
    )


def test_sqlite_foreign_keys_are_enabled_for_every_runtime_session(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    try:
        with factory() as session:
            assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    finally:
        factory.dispose()


def test_connection_revision_is_a_database_compare_and_swap(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    credentials = MemoryCredentials()
    try:
        with factory.begin() as session:
            SqlAlchemyProxyRepository(session).add_connection(_connection())

        first = factory()
        second = factory()
        try:
            # Keep both ORM rows alive so both services operate on revision zero.
            first_row = first.get(ProxyConnectionRow, "connection-1")
            second_row = second.get(ProxyConnectionRow, "connection-1")
            assert first_row is not None and second_row is not None
            ConnectionService(SqlAlchemyProxyRepository(first), credentials).update(
                "connection-1", 0, "First writer"
            )
            first.commit()

            with pytest.raises(RevisionConflictError):
                ConnectionService(SqlAlchemyProxyRepository(second), credentials).update(
                    "connection-1", 0, "Stale writer"
                )
                second.commit()
        finally:
            first.close()
            second.close()
    finally:
        factory.dispose()


def test_sync_invalidates_health_when_connection_material_changes(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    provider = PageProvider(
        ProviderPage(
            (ProviderProxy("remote-1", "One", http_endpoint=Endpoint("old.example", 8000), credential_available=True),),
            "complete",
            1,
        )
    )
    try:
        with factory.begin() as session:
            repository = SqlAlchemyProxyRepository(session)
            repository.add_connection(_connection())
            active = repository.begin_sync(
                "connection-1", "proxypanel/connection-1/api-key", 0
            )
            SyncService(repository).apply(active, provider.page, active.generation)
            projection = repository.get_projection_by_provider_id("connection-1", "remote-1")
            assert projection is not None
            repository.save_health(
                projection.id,
                projection.revision,
                Health(state="healthy", checked_at=datetime.now(UTC), source="local_probe"),
                datetime.now(UTC),
            )

        provider.page = ProviderPage(
            (ProviderProxy("remote-1", "One", http_endpoint=Endpoint("new.example", 9000), credential_available=True),),
            "complete",
            1,
        )
        with factory.begin() as session:
            repository = SqlAlchemyProxyRepository(session)
            connection = repository.get_connection("connection-1")
            assert connection is not None
            active = repository.begin_sync(
                connection.id, connection.secret_ref, connection.generation
            )
            SyncService(repository).apply(active, provider.page, active.generation)
            projection = repository.get_projection_by_provider_id("connection-1", "remote-1")
            assert projection is not None
            assert projection.http_endpoint == Endpoint("new.example", 9000)
            assert projection.health == Health()
    finally:
        factory.dispose()


def test_group_revision_is_a_database_compare_and_swap(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    try:
        with factory.begin() as session:
            repository = SqlAlchemyProxyRepository(session)
            repository.add_connection(_connection())
            projection = ProviderProxy("remote-1", "One")
            active = repository.begin_sync(
                "connection-1", "proxypanel/connection-1/api-key", 0
            )
            SyncService(repository).apply(
                active, ProviderPage((projection,), "complete", 1), active.generation
            )
            member = repository.get_projection_by_provider_id("connection-1", "remote-1")
            assert member is not None
            group = GroupService(repository).create(
                name="Group", description="", member_ids=[member.id], acknowledge_risk=True
            )

        first = factory()
        second = factory()
        try:
            first_row = first.get(ProxyGroupDetailRow, group.id)
            second_row = second.get(ProxyGroupDetailRow, group.id)
            assert first_row is not None and second_row is not None
            GroupService(SqlAlchemyProxyRepository(first)).update(
                group.id,
                expected_revision=0,
                name="First writer",
                description="",
                member_ids=list(group.member_ids),
                acknowledge_risk=True,
            )
            first.commit()
            with pytest.raises(RevisionConflictError):
                GroupService(SqlAlchemyProxyRepository(second)).update(
                    group.id,
                    expected_revision=0,
                    name="Stale writer",
                    description="",
                    member_ids=list(group.member_ids),
                    acknowledge_risk=True,
                )
                second.commit()
        finally:
            first.close()
            second.close()
    finally:
        factory.dispose()


def test_late_failed_sync_cannot_poison_a_newer_successful_snapshot(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    page = ProviderPage(
        (
            ProviderProxy(
                "remote-1",
                "One",
                http_endpoint=Endpoint("proxy.example", 8000),
                credential_available=True,
            ),
        ),
        "complete",
        1,
    )
    try:
        with factory.begin() as session:
            repository = SqlAlchemyProxyRepository(session)
            repository.add_connection(_connection())
            active = repository.begin_sync(
                "connection-1", "proxypanel/connection-1/api-key", 0
            )
            SyncService(repository).apply(active, page, active.generation)

        # This represents an older concurrent provider request returning after the
        # generation-one snapshot was already committed.
        with factory.begin() as session:
            SqlAlchemyProxyRepository(session).fail_sync(
                "connection-1",
                "proxypanel/connection-1/api-key",
                {"code": "PROXYPANEL_UNAVAILABLE", "message": "sync failed"},
                datetime.now(UTC),
            )

        with factory() as session:
            repository = SqlAlchemyProxyRepository(session)
            connection = repository.get_connection("connection-1")
            projection = repository.get_projection_by_provider_id(
                "connection-1", "remote-1"
            )
            assert connection is not None and connection.status == "connected"
            assert projection is not None and not projection.stale
    finally:
        factory.dispose()
