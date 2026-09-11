from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from autoflow.application.proxies.connections import ConnectionService
from autoflow.application.proxies.groups import GroupService, ResolveProxyForProfile
from autoflow.application.proxies.sync import SyncService
from autoflow.domain.proxies.errors import RevisionConflictError, SelectionConflictError
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


class UnexpectedProbe:
    async def probe(self, projection):
        raise AssertionError(f"healthy projection {projection.id} must not be probed")


class FirstCandidateBarrier:
    def __init__(self) -> None:
        self._barrier = threading.Barrier(2)
        self._lock = threading.Lock()
        self._threads: set[int] = set()

    def wait_once_per_thread(self) -> None:
        thread_id = threading.get_ident()
        with self._lock:
            if thread_id in self._threads:
                return
            self._threads.add(thread_id)
        self._barrier.wait(timeout=5)


class BarrierRepository:
    def __init__(self, repository, barrier: FirstCandidateBarrier) -> None:
        self._repository = repository
        self._barrier = barrier

    def __getattr__(self, name):
        return getattr(self._repository, name)

    def list_group_candidates(self, group_id):
        candidates = self._repository.list_group_candidates(group_id)
        self._barrier.wait_once_per_thread()
        return candidates


class BarrierUnitOfWork:
    def __init__(self, factory, barrier: FirstCandidateBarrier) -> None:
        self._factory = factory
        self._barrier = barrier

    def __enter__(self):
        self._session = self._factory()
        self.repository = BarrierRepository(
            SqlAlchemyProxyRepository(self._session), self._barrier
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self._session.rollback()
        self._session.close()

    def commit(self):
        self._session.commit()

    def rollback(self):
        self._session.rollback()


def _connection() -> Connection:
    now = datetime.now(UTC)
    return Connection(
        id="connection-1",
        name="Main",
        secret_ref="proxypanel/connection-1/api-key",
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


def _create_healthy_group(factory):
    with factory.begin() as session:
        repository = SqlAlchemyProxyRepository(session)
        repository.add_connection(_connection())
        page = ProviderPage(
            tuple(
                ProviderProxy(
                    f"remote-{index}",
                    f"Proxy {index}",
                    http_endpoint=Endpoint(f"proxy-{index}.example", 8000 + index),
                    credential_available=True,
                )
                for index in (1, 2)
            ),
            "complete",
            2,
        )
        active = repository.begin_sync(
            "connection-1",
            "proxypanel/connection-1/api-key",
            0,
            "sync-group-members",
            datetime.now(UTC),
        )
        SyncService(repository).apply(active, page, active.generation)
        members = [
            repository.get_projection_by_provider_id("connection-1", f"remote-{index}")
            for index in (1, 2)
        ]
        assert all(member is not None for member in members)
        for member in members:
            assert member is not None
            repository.save_health(
                member.id,
                member.revision,
                Health(
                    state="healthy",
                    checked_at=datetime.now(UTC),
                    source="local_probe",
                ),
                datetime.now(UTC),
            )
        group = GroupService(repository).create(
            name="Round Robin",
            description="",
            member_ids=[member.id for member in members if member is not None],
            acknowledge_risk=False,
        )
        return group


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
                "connection-1",
                "proxypanel/connection-1/api-key",
                0,
                "sync-health-1",
                datetime.now(UTC),
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
                connection.id,
                connection.secret_ref,
                connection.generation,
                "sync-health-2",
                datetime.now(UTC),
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
                "connection-1",
                "proxypanel/connection-1/api-key",
                0,
                "sync-group-setup",
                datetime.now(UTC),
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
            now = datetime.now(UTC)
            old = repository.begin_sync(
                "connection-1",
                "proxypanel/connection-1/api-key",
                0,
                "expired-sync",
                now - timedelta(seconds=121),
            )
            active = repository.begin_sync(
                "connection-1",
                "proxypanel/connection-1/api-key",
                old.generation,
                "replacement-sync",
                now,
            )
            SyncService(repository).apply(active, page, active.generation)

        # This represents an older concurrent provider request returning after the
        # generation-one snapshot was already committed.
        with factory.begin() as session:
            SqlAlchemyProxyRepository(session).fail_sync(
                "connection-1",
                "proxypanel/connection-1/api-key",
                old.generation,
                "expired-sync",
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


def test_same_request_is_idempotent_across_stale_database_sessions(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    try:
        group = _create_healthy_group(factory)
        first = factory()
        second = factory()
        try:
            first_repository = SqlAlchemyProxyRepository(first)
            second_repository = SqlAlchemyProxyRepository(second)
            first_candidate = first_repository.list_group_candidates(group.id)[0]
            second_candidate = second_repository.list_group_candidates(group.id)[0]
            assert first_repository.get_group_resolution(group.id, "launch-1") is None
            assert second_repository.get_group_resolution(group.id, "launch-1") is None

            selected = first_repository.commit_group_resolution(
                group.id,
                "launch-1",
                first_candidate.id,
                first_candidate.revision,
                group.cursor_revision,
            )
            first.commit()
            repeated = second_repository.commit_group_resolution(
                group.id,
                "launch-1",
                second_candidate.id,
                second_candidate.revision,
                group.cursor_revision,
            )
            second.commit()

            assert repeated.id == selected.id
            with factory() as session:
                persisted = SqlAlchemyProxyRepository(session).get_group(group.id)
                assert persisted is not None and persisted.cursor_revision == 1
        finally:
            first.close()
            second.close()
    finally:
        factory.dispose()


def test_different_requests_cannot_claim_the_same_stale_cursor(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    try:
        group = _create_healthy_group(factory)
        first = factory()
        second = factory()
        try:
            first_repository = SqlAlchemyProxyRepository(first)
            second_repository = SqlAlchemyProxyRepository(second)
            first_candidate = first_repository.list_group_candidates(group.id)[0]
            stale_detail = second.get(ProxyGroupDetailRow, group.id)
            assert stale_detail is not None
            stale_candidate = second_repository.list_group_candidates(group.id)[0]

            first_repository.commit_group_resolution(
                group.id,
                "launch-1",
                first_candidate.id,
                first_candidate.revision,
                group.cursor_revision,
            )
            first.commit()
            with pytest.raises(SelectionConflictError):
                second_repository.commit_group_resolution(
                    group.id,
                    "launch-2",
                    stale_candidate.id,
                    stale_candidate.revision,
                    group.cursor_revision,
                )
            second.rollback()

            with factory.begin() as session:
                repository = SqlAlchemyProxyRepository(session)
                next_candidate = repository.list_group_candidates(group.id)[0]
                selected = repository.commit_group_resolution(
                    group.id,
                    "launch-2",
                    next_candidate.id,
                    next_candidate.revision,
                    repository.get_group(group.id).cursor_revision,  # type: ignore[union-attr]
                )
                assert selected.id != first_candidate.id
        finally:
            first.close()
            second.close()
    finally:
        factory.dispose()


def test_replacing_api_key_cancels_the_old_sync_lease(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    credentials = MemoryCredentials()
    credentials.write("proxypanel/connection-1/api-key", b"old-key")
    try:
        with factory.begin() as session:
            repository = SqlAlchemyProxyRepository(session)
            repository.add_connection(_connection())
            active = repository.begin_sync(
                "connection-1",
                "proxypanel/connection-1/api-key",
                0,
                "old-key-sync",
                datetime.now(UTC),
            )
            assert active.sync_token == "old-key-sync"

        with factory.begin() as session:
            updated, _, _ = ConnectionService(
                SqlAlchemyProxyRepository(session), credentials
            ).replace_api_key("connection-1", 0, "new-key")
            assert updated.sync_token is None
            assert updated.sync_started_at is None
    finally:
        factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("request_ids", "expected_distinct", "expected_cursor_revision"),
    [
        (("same-launch", "same-launch"), 1, 1),
        (("launch-1", "launch-2"), 2, 2),
    ],
)
async def test_application_resolution_is_atomic_after_concurrent_candidate_reads(
    tmp_path,
    request_ids,
    expected_distinct,
    expected_cursor_revision,
):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    try:
        group = _create_healthy_group(factory)
        barrier = FirstCandidateBarrier()
        resolver = ResolveProxyForProfile(
            lambda: BarrierUnitOfWork(factory, barrier),  # type: ignore[arg-type]
            UnexpectedProbe(),
        )

        async def resolve_in_thread(request_id):
            return await asyncio.to_thread(
                lambda: asyncio.run(resolver.resolve_group(group.id, request_id))
            )

        selected = await asyncio.gather(
            *(resolve_in_thread(request_id) for request_id in request_ids)
        )
        assert len({projection.id for projection in selected}) == expected_distinct
        with factory() as session:
            persisted = SqlAlchemyProxyRepository(session).get_group(group.id)
            assert persisted is not None
            assert persisted.cursor_revision == expected_cursor_revision
    finally:
        factory.dispose()
