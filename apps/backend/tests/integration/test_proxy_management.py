from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from autoflow.application.proxies.connections import ConnectionService
from autoflow.application.proxies.facade import ProxyApplication
from autoflow.application.proxies.groups import GroupService
from autoflow.application.proxies.projections import ProjectionService
from autoflow.application.proxies.sync import SyncService
from autoflow.domain.proxies.errors import (
    OperationInProgressError,
    ProviderAuthenticationError,
    ProxyGroupInUseError,
    ProxyMemberRiskError,
    RevisionConflictError,
)
from autoflow.domain.proxies.models import ProviderPage, ProviderProxy
from autoflow.infrastructure.database.models import ProfileRow
from autoflow.infrastructure.database.proxies import (
    SqlAlchemyProxyRepository,
    SqlAlchemyProxyUnitOfWork,
)
from autoflow.infrastructure.database.proxy_models import ProxyProjectionRow
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


class MemoryCredentials:
    def __init__(self):
        self.values = {}

    def read(self, key):
        return self.values.get(key)

    def write(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


class PageProvider:
    def __init__(self, page):
        self.page = page

    async def verify(self, api_key):
        return ProviderPage((), "unknown")

    async def list_proxies(self, api_key):
        return self.page


class AuthenticationFailureProvider(PageProvider):
    async def verify(self, api_key):
        raise ProviderAuthenticationError("Authentication failed")


@pytest.mark.asyncio
async def test_full_and_partial_sync_preserve_local_values_and_tombstone_only_complete(tmp_path: Path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    credentials = MemoryCredentials()
    provider = PageProvider(ProviderPage((ProviderProxy("one", "One"), ProviderProxy("two", "Two")), "complete", 2))
    with factory.begin() as session:
        connection = ConnectionService(SqlAlchemyProxyRepository(session), credentials).create("Main", "secret")
    with factory.begin() as session:
        repository = SqlAlchemyProxyRepository(session)
        active = repository.begin_sync(
            connection.id, connection.secret_ref, connection.generation, "sync-1", datetime.now(UTC)
        )
        SyncService(repository).apply(active, provider.page, active.generation)
        one = repository.get_projection_by_provider_id(connection.id, "one")
        assert one is not None
        repository.save_projection(
            type(one)(
                **{
                    **one.__dict__,
                    "name_override": "Pinned",
                    "enabled": False,
                    "revision": one.revision + 1,
                }
            ),
            one.revision,
        )

    provider.page = ProviderPage((ProviderProxy("one", "Renamed"),), "partial", None)
    with factory.begin() as session:
        repository = SqlAlchemyProxyRepository(session)
        current = repository.get_connection(connection.id)
        assert current is not None
        active = repository.begin_sync(
            connection.id, current.secret_ref, current.generation, "sync-2", datetime.now(UTC)
        )
        SyncService(repository).apply(active, provider.page, active.generation)
        one = repository.get_projection_by_provider_id(connection.id, "one")
        two = repository.get_projection_by_provider_id(connection.id, "two")
        assert one and one.display_name == "Pinned" and not one.enabled
        assert two and two.stale and not two.remote_missing

    provider.page = ProviderPage((), "complete", 0)
    with factory.begin() as session:
        repository = SqlAlchemyProxyRepository(session)
        current = repository.get_connection(connection.id)
        assert current is not None
        active = repository.begin_sync(
            connection.id, current.secret_ref, current.generation, "sync-3", datetime.now(UTC)
        )
        _, count, missing, completeness, total = SyncService(repository).apply(
            active, provider.page, active.generation
        )
        projections, matched = repository.list_projections(offset=0, limit=1)
        assert (count, missing, completeness, total, matched) == (0, 2, "complete", 0, 2)
        assert len(projections) == 1
        assert all(item.remote_missing for item in repository.list_projections(offset=0, limit=50)[0])
    factory.dispose()


@pytest.mark.asyncio
async def test_group_risk_offset_and_profile_reference_protection(tmp_path: Path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    credentials = MemoryCredentials()
    provider = PageProvider(ProviderPage((ProviderProxy("one", "One"),), "complete", 1))
    with factory.begin() as session:
        connection = ConnectionService(SqlAlchemyProxyRepository(session), credentials).create("Main", "secret")
    with factory.begin() as session:
        repository = SqlAlchemyProxyRepository(session)
        active = repository.begin_sync(
            connection.id, connection.secret_ref, connection.generation, "sync-1", datetime.now(UTC)
        )
        SyncService(repository).apply(active, provider.page, active.generation)
        projection = repository.get_projection_by_provider_id(connection.id, "one")
        assert projection is not None
        groups = GroupService(repository)
        with pytest.raises(ProxyMemberRiskError):
            groups.create(name="Risky", description="", member_ids=[projection.id], acknowledge_risk=False)
        group = groups.create(name="Accepted", description="local", member_ids=[projection.id], acknowledge_risk=True)
        items, count = groups.list_groups(q=None, offset=1, limit=10)
        assert items == [] and count == 1
        now = datetime.now(UTC)
        session.add(ProfileRow(
            id="profile-1",
            name="Browser",
            spec={"proxy_pool_id": group.id},
            fingerprint_seed=1,
            created_at=now,
            updated_at=now,
        ))
    with factory.begin() as session, pytest.raises(ProxyGroupInUseError):
        GroupService(SqlAlchemyProxyRepository(session)).delete(group.id)
    factory.dispose()


def test_projection_revision_and_sync_generation_are_database_compare_and_swap(tmp_path: Path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    credentials = MemoryCredentials()
    page = ProviderPage((ProviderProxy("one", "One"),), "complete", 1)
    with factory.begin() as session:
        repository = SqlAlchemyProxyRepository(session)
        connection = ConnectionService(repository, credentials).create("Main", "secret")
        active = repository.begin_sync(
            connection.id, connection.secret_ref, connection.generation, "sync-1", datetime.now(UTC)
        )
        SyncService(repository).apply(active, page, active.generation)

    first = factory()
    second = factory()
    try:
        first_row = first.scalar(ProxyProjectionRow.__table__.select().where(ProxyProjectionRow.provider_id == "one"))
        second_row = second.scalar(ProxyProjectionRow.__table__.select().where(ProxyProjectionRow.provider_id == "one"))
        assert first_row is not None and second_row is not None
        projection_id = first_row
        first_projection = ProjectionService(SqlAlchemyProxyRepository(first)).get(projection_id)
        second_projection = ProjectionService(SqlAlchemyProxyRepository(second)).get(projection_id)
        ProjectionService(SqlAlchemyProxyRepository(first)).update(
            projection_id,
            expected_revision=first_projection.revision,
            name_override="First",
            enabled=None,
            change_name=True,
        )
        first.commit()
        with pytest.raises(RevisionConflictError):
            ProjectionService(SqlAlchemyProxyRepository(second)).update(
                projection_id,
                expected_revision=second_projection.revision,
                name_override="Stale",
                enabled=None,
                change_name=True,
            )
        second.rollback()
    finally:
        first.close()
        second.close()

    slow = factory()
    fast = factory()
    try:
        slow_repository = SqlAlchemyProxyRepository(slow)
        fast_repository = SqlAlchemyProxyRepository(fast)
        slow_snapshot = slow_repository.get_connection(connection.id)
        fast_snapshot = fast_repository.get_connection(connection.id)
        assert slow_snapshot and fast_snapshot
        winner = fast_repository.begin_sync(
            connection.id,
            fast_snapshot.secret_ref,
            fast_snapshot.generation,
            "fast-sync",
            datetime.now(UTC),
        )
        SyncService(fast_repository).apply(
            winner,
            ProviderPage((ProviderProxy("one", "Newest"), ProviderProxy("two", "Two")), "complete", 2),
            winner.generation,
        )
        fast.commit()
        with pytest.raises(OperationInProgressError):
            slow_repository.begin_sync(
                connection.id,
                slow_snapshot.secret_ref,
                slow_snapshot.generation,
                "slow-sync",
                datetime.now(UTC),
            )
        slow.rollback()
    finally:
        slow.close()
        fast.close()
    with factory() as session:
        projections, count = SqlAlchemyProxyRepository(session).list_projections(offset=0, limit=50)
        assert count == 2
        assert {projection.name for projection in projections} == {"Newest", "Two"}
        assert not any(projection.remote_missing for projection in projections)
    factory.dispose()


def test_projection_stale_is_derived_after_five_minutes_without_clearing_data(tmp_path: Path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    credentials = MemoryCredentials()
    with factory.begin() as session:
        repository = SqlAlchemyProxyRepository(session)
        connection = ConnectionService(repository, credentials).create("Main", "secret")
        active = repository.begin_sync(
            connection.id, connection.secret_ref, 0, "sync-1", datetime.now(UTC)
        )
        SyncService(repository).apply(
            active,
            ProviderPage((ProviderProxy("one", "One", city="Shanghai"),), "complete", 1),
            active.generation,
        )
        projection = repository.get_projection_by_provider_id(connection.id, "one")
        assert projection is not None
        row = session.get(ProxyProjectionRow, projection.id)
        assert row is not None
        row.last_synced_at = datetime.now(UTC) - timedelta(minutes=6)
        row.stale = False
    with factory() as session:
        stale = SqlAlchemyProxyRepository(session).get_projection(projection.id)
        assert stale is not None and stale.stale and stale.city == "Shanghai"
    with factory.begin() as session:
        row = session.get(ProxyProjectionRow, projection.id)
        assert row is not None
        row.last_synced_at = datetime.now(UTC) - timedelta(minutes=4)
    with factory() as session:
        fresh = SqlAlchemyProxyRepository(session).get_projection(projection.id)
        assert fresh is not None and not fresh.stale
    factory.dispose()


@pytest.mark.asyncio
async def test_failed_verification_marks_same_key_connection_failed_and_preserves_projection(tmp_path: Path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    credentials = MemoryCredentials()
    page = ProviderPage((ProviderProxy("one", "One"),), "complete", 1)
    with factory.begin() as session:
        repository = SqlAlchemyProxyRepository(session)
        connection = ConnectionService(repository, credentials).create("Main", "secret")
        active = repository.begin_sync(
            connection.id, connection.secret_ref, 0, "sync-1", datetime.now(UTC)
        )
        SyncService(repository).apply(active, page, active.generation)
    application = ProxyApplication(
        lambda: SqlAlchemyProxyUnitOfWork(factory),
        credentials,
        AuthenticationFailureProvider(page),
    )
    with pytest.raises(ProviderAuthenticationError):
        await application.verify_connection(connection.id)
    with factory() as session:
        repository = SqlAlchemyProxyRepository(session)
        failed = repository.get_connection(connection.id)
        projection = repository.get_projection_by_provider_id(connection.id, "one")
        assert failed is not None and failed.status == "failed"
        assert projection is not None and projection.stale
    factory.dispose()
