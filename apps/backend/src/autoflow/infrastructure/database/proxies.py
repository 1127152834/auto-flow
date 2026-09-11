from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from autoflow.domain.proxies.errors import (
    OperationInProgressError,
    ProxyNotFoundError,
    RevisionConflictError,
    SelectionConflictError,
)
from autoflow.domain.proxies.models import (
    Capability,
    Connection,
    Endpoint,
    Health,
    Projection,
    ProxyGroup,
)

from .models import ProfileRow, ProxyPoolRow, ProxyRow
from .proxy_models import (
    ProxyConnectionRow,
    ProxyGroupDetailRow,
    ProxyGroupMemberRow,
    ProxyGroupResolutionRow,
    ProxyProjectionRow,
)


class SqlAlchemyProxyRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_connection(self, connection: Connection) -> None:
        self.session.add(_connection_row(connection))
        self.session.flush()

    def get_connection(self, connection_id: str) -> Connection | None:
        row = self.session.get(ProxyConnectionRow, connection_id)
        return _connection(row) if row else None

    def list_connections(self) -> list[Connection]:
        rows = self.session.scalars(
            select(ProxyConnectionRow).order_by(ProxyConnectionRow.created_at, ProxyConnectionRow.id)
        )
        return [_connection(row) for row in rows]

    def save_connection(
        self, connection: Connection, expected_revision: int, expected_generation: int
    ) -> None:
        result = self.session.execute(
            update(ProxyConnectionRow)
            .where(
                ProxyConnectionRow.id == connection.id,
                ProxyConnectionRow.revision == expected_revision,
                ProxyConnectionRow.generation == expected_generation,
            )
            .values(**_connection_values(connection))
        )
        if _rowcount(result) != 1:
            if self.session.get(ProxyConnectionRow, connection.id) is None:
                raise ProxyNotFoundError("ProxyPanel connection was not found")
            raise RevisionConflictError("Connection revision is stale")
        self.session.expire_all()
        self.session.flush()

    def mark_connection_verified(
        self, connection_id: str, secret_ref: str, verified_at: datetime
    ) -> Connection:
        result = self.session.execute(
            update(ProxyConnectionRow)
            .where(
                ProxyConnectionRow.id == connection_id,
                ProxyConnectionRow.secret_ref == secret_ref,
            )
            .values(
                status="connected",
                last_verified_at=verified_at,
                last_error=None,
                updated_at=verified_at,
            )
        )
        if _rowcount(result) != 1:
            raise RevisionConflictError("Connection changed while verification was running")
        self.session.expire_all()
        connection = self.get_connection(connection_id)
        assert connection is not None
        return connection

    def fail_verification(
        self,
        connection_id: str,
        secret_ref: str,
        error: dict,
        failed_at: datetime,
    ) -> None:
        result = self.session.execute(
            update(ProxyConnectionRow)
            .where(
                ProxyConnectionRow.id == connection_id,
                ProxyConnectionRow.secret_ref == secret_ref,
            )
            .values(status="failed", last_error=error, updated_at=failed_at)
        )
        if _rowcount(result) == 1:
            self.mark_connection_projections_stale(connection_id)

    def begin_sync(
        self,
        connection_id: str,
        secret_ref: str,
        expected_generation: int,
        sync_token: str,
        started_at: datetime,
    ) -> Connection:
        result = self.session.execute(
            update(ProxyConnectionRow)
            .where(
                ProxyConnectionRow.id == connection_id,
                ProxyConnectionRow.secret_ref == secret_ref,
                ProxyConnectionRow.generation == expected_generation,
                or_(
                    ProxyConnectionRow.sync_token.is_(None),
                    ProxyConnectionRow.sync_started_at < started_at - timedelta(seconds=120),
                ),
            )
            .values(
                generation=expected_generation + 1,
                sync_token=sync_token,
                sync_started_at=started_at,
            )
        )
        if _rowcount(result) != 1:
            current = self.get_connection(connection_id)
            if current is None:
                raise ProxyNotFoundError("ProxyPanel connection was not found")
            if current.secret_ref != secret_ref:
                raise RevisionConflictError("Connection credentials changed while sync was running")
            raise OperationInProgressError("A newer proxy sync already completed")
        self.session.expire_all()
        connection = self.get_connection(connection_id)
        assert connection is not None
        return connection

    def validate_sync(
        self, connection_id: str, secret_ref: str, generation: int, sync_token: str
    ) -> Connection:
        row = self.session.scalar(
            select(ProxyConnectionRow).where(
                ProxyConnectionRow.id == connection_id,
                ProxyConnectionRow.secret_ref == secret_ref,
                ProxyConnectionRow.generation == generation,
                ProxyConnectionRow.sync_token == sync_token,
            )
        )
        if row is None:
            raise OperationInProgressError("Proxy sync lease is no longer active")
        return _connection(row)

    def complete_sync(
        self, connection_id: str, generation: int, sync_token: str, synced_at: datetime
    ) -> Connection:
        result = self.session.execute(
            update(ProxyConnectionRow)
            .where(
                ProxyConnectionRow.id == connection_id,
                ProxyConnectionRow.generation == generation,
                ProxyConnectionRow.sync_token == sync_token,
            )
            .values(
                status="connected",
                last_synced_at=synced_at,
                last_error=None,
                updated_at=synced_at,
                sync_token=None,
                sync_started_at=None,
            )
        )
        if _rowcount(result) != 1:
            raise OperationInProgressError("Proxy sync result was superseded")
        self.session.expire_all()
        connection = self.get_connection(connection_id)
        assert connection is not None
        return connection

    def fail_sync(
        self,
        connection_id: str,
        secret_ref: str,
        generation: int,
        sync_token: str,
        error: dict,
        failed_at: datetime,
    ) -> None:
        result = self.session.execute(
            update(ProxyConnectionRow)
            .where(
                ProxyConnectionRow.id == connection_id,
                ProxyConnectionRow.secret_ref == secret_ref,
                ProxyConnectionRow.generation == generation,
                ProxyConnectionRow.sync_token == sync_token,
            )
            .values(
                status="failed",
                last_error=error,
                updated_at=failed_at,
                sync_token=None,
                sync_started_at=None,
            )
        )
        if _rowcount(result) == 1:
            self.mark_connection_projections_stale(connection_id)

    def delete_connection(self, connection_id: str) -> None:
        proxy_ids = list(
            self.session.scalars(
                select(ProxyProjectionRow.proxy_id).where(ProxyProjectionRow.connection_id == connection_id)
            )
        )
        if proxy_ids:
            self.session.execute(delete(ProxyGroupResolutionRow).where(ProxyGroupResolutionRow.proxy_id.in_(proxy_ids)))
            self.session.execute(delete(ProxyProjectionRow).where(ProxyProjectionRow.connection_id == connection_id))
            self.session.execute(delete(ProxyRow).where(ProxyRow.id.in_(proxy_ids)))
        self.session.execute(delete(ProxyConnectionRow).where(ProxyConnectionRow.id == connection_id))
        self.session.flush()

    def connection_reference_count(self, connection_id: str) -> int:
        proxy_ids = set(
            self.session.scalars(
                select(ProxyProjectionRow.proxy_id).where(ProxyProjectionRow.connection_id == connection_id)
            )
        )
        if not proxy_ids:
            return 0
        group_ids = set(
            self.session.scalars(
                select(ProxyGroupMemberRow.group_id).where(ProxyGroupMemberRow.proxy_id.in_(proxy_ids))
            )
        )
        profiles = list(self.session.scalars(select(ProfileRow)))
        profile_refs = sum(
            1
            for profile in profiles
            if profile.spec.get("proxy_id") in proxy_ids or profile.spec.get("proxy_pool_id") in group_ids
        )
        return profile_refs + len(group_ids)

    def mark_connection_projections_stale(
        self, connection_id: str, *, reset_health: bool = False
    ) -> None:
        values: dict[str, Any] = {
            "stale": True,
            "revision": ProxyProjectionRow.revision + 1,
            "updated_at": datetime.now(UTC),
        }
        if reset_health:
            values.update(
                health_state="untested",
                health_latency_ms=None,
                health_exit_ip=None,
                health_checked_at=None,
                health_source="none",
                health_error=None,
            )
        self.session.execute(
            update(ProxyProjectionRow)
            .where(ProxyProjectionRow.connection_id == connection_id)
            .values(**values)
        )

    def upsert_projection(self, projection: Projection) -> None:
        base = self.session.get(ProxyRow, projection.id)
        if base is None:
            self.session.add(ProxyRow(id=projection.id, name=projection.display_name, enabled=projection.enabled))
        else:
            self.session.execute(
                update(ProxyRow)
                .where(ProxyRow.id == projection.id)
                .values(name=projection.display_name, enabled=projection.enabled)
            )
        row = self.session.get(ProxyProjectionRow, projection.id)
        if row is None:
            self.session.add(_projection_row(projection))
        else:
            result = self.session.execute(
                update(ProxyProjectionRow)
                .where(
                    ProxyProjectionRow.proxy_id == projection.id,
                    ProxyProjectionRow.revision == projection.revision - 1,
                )
                .values(**_projection_values(projection))
            )
            if _rowcount(result) != 1:
                raise RevisionConflictError("Proxy changed while sync was being applied")
            self.session.expire_all()
        self.session.flush()

    def finish_sync(self, connection_id: str, generation: int, complete: bool) -> int:
        unseen = list(
            self.session.scalars(
                select(ProxyProjectionRow).where(
                    ProxyProjectionRow.connection_id == connection_id,
                    ProxyProjectionRow.generation < generation,
                )
            )
        )
        for row in unseen:
            if complete:
                changed = not row.remote_missing or row.stale
                row.remote_missing = True
                row.stale = False
            else:
                changed = not row.stale
                row.stale = True
            if changed:
                row.revision += 1
                row.updated_at = datetime.now(UTC)
        self.session.flush()
        return sum(
            1
            for row in self.session.scalars(
                select(ProxyProjectionRow).where(
                    ProxyProjectionRow.connection_id == connection_id,
                    ProxyProjectionRow.remote_missing.is_(True),
                )
            )
        )

    def get_projection(self, projection_id: str) -> Projection | None:
        row = self.session.get(ProxyProjectionRow, projection_id)
        return self._projection(row) if row else None

    def get_projection_by_provider_id(self, connection_id: str, provider_id: str) -> Projection | None:
        row = self.session.scalar(
            select(ProxyProjectionRow).where(
                ProxyProjectionRow.connection_id == connection_id,
                ProxyProjectionRow.provider_id == provider_id,
            )
        )
        return self._projection(row) if row else None

    def list_projections(
        self,
        *,
        connection_id: str | None = None,
        q: str | None = None,
        carrier: str | None = None,
        city: str | None = None,
        health: str | None = None,
        enabled: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Projection], int]:
        statement = select(ProxyProjectionRow)
        if connection_id is not None:
            statement = statement.where(ProxyProjectionRow.connection_id == connection_id)
        rows = list(self.session.scalars(statement.order_by(ProxyProjectionRow.created_at, ProxyProjectionRow.proxy_id)))
        projections = [self._projection(row) for row in rows]
        needle = q.casefold().strip() if q else None
        matches = [
            projection
            for projection in projections
            if (needle is None or any(needle in (value or "").casefold() for value in (
                projection.display_name, projection.city, projection.carrier, projection.exit_ip
            )))
            and (carrier is None or projection.carrier == carrier)
            and (city is None or projection.city == city)
            and (health is None or projection.health.state == health)
            and (enabled is None or projection.enabled is enabled)
        ]
        return matches[offset : offset + limit], len(matches)

    def save_projection(self, projection: Projection, expected_revision: int) -> None:
        values = _projection_values(projection)
        result = self.session.execute(
            update(ProxyProjectionRow)
            .where(
                ProxyProjectionRow.proxy_id == projection.id,
                ProxyProjectionRow.revision == expected_revision,
            )
            .values(**values)
        )
        if _rowcount(result) != 1:
            if self.session.get(ProxyProjectionRow, projection.id) is None:
                raise ProxyNotFoundError("Proxy was not found")
            raise RevisionConflictError("Proxy revision is stale")
        self.session.execute(
            update(ProxyRow)
            .where(ProxyRow.id == projection.id)
            .values(name=projection.display_name, enabled=projection.enabled)
        )
        self.session.expire_all()
        self.session.flush()

    def projection_references(self, projection_id: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        profiles = [
            (row.id, row.name)
            for row in self.session.scalars(select(ProfileRow))
            if row.spec.get("proxy_id") == projection_id
        ]
        group_ids = list(
            self.session.scalars(
                select(ProxyGroupMemberRow.group_id).where(ProxyGroupMemberRow.proxy_id == projection_id)
            )
        )
        groups = []
        if group_ids:
            groups = [
                (row.id, row.name)
                for row in self.session.scalars(select(ProxyPoolRow).where(ProxyPoolRow.id.in_(group_ids)))
            ]
        return profiles, groups

    def add_group(self, group: ProxyGroup) -> None:
        self.session.add(ProxyPoolRow(id=group.id, name=group.name))
        self.session.add(_group_detail_row(group))
        self._replace_members(group)
        self.session.flush()

    def get_group(self, group_id: str) -> ProxyGroup | None:
        detail = self.session.get(ProxyGroupDetailRow, group_id)
        base = self.session.get(ProxyPoolRow, group_id)
        if detail is None or base is None:
            return None
        members = tuple(
            self.session.scalars(
                select(ProxyGroupMemberRow.proxy_id)
                .where(ProxyGroupMemberRow.group_id == group_id)
                .order_by(ProxyGroupMemberRow.position)
            )
        )
        return ProxyGroup(
            id=group_id,
            name=base.name,
            description=detail.description,
            member_ids=members,
            revision=detail.revision,
            cursor=detail.cursor,
            cursor_revision=detail.cursor_revision,
            created_at=_required_aware(detail.created_at),
            updated_at=_required_aware(detail.updated_at),
            reference_count=len(self.group_references(group_id)),
        )

    def list_groups(self, *, q: str | None, offset: int, limit: int) -> tuple[list[ProxyGroup], int]:
        ids = list(
            self.session.scalars(
                select(ProxyGroupDetailRow.proxy_pool_id).order_by(
                    ProxyGroupDetailRow.created_at,
                    ProxyGroupDetailRow.proxy_pool_id,
                )
            )
        )
        groups = [group for group_id in ids if (group := self.get_group(group_id)) is not None]
        if q:
            needle = q.casefold().strip()
            groups = [group for group in groups if needle in group.name.casefold() or needle in group.description.casefold()]
        return groups[offset : offset + limit], len(groups)

    def save_group(self, group: ProxyGroup, expected_revision: int) -> None:
        result = self.session.execute(
            update(ProxyGroupDetailRow)
            .where(
                ProxyGroupDetailRow.proxy_pool_id == group.id,
                ProxyGroupDetailRow.revision == expected_revision,
                ProxyGroupDetailRow.cursor_revision == group.cursor_revision - 1,
            )
            .values(
                description=group.description,
                revision=group.revision,
                cursor=group.cursor,
                cursor_revision=group.cursor_revision,
                updated_at=group.updated_at,
            )
        )
        if _rowcount(result) != 1:
            if self.session.get(ProxyGroupDetailRow, group.id) is None:
                raise ProxyNotFoundError("Proxy group was not found")
            raise RevisionConflictError("Proxy group revision is stale")
        self.session.execute(
            update(ProxyPoolRow).where(ProxyPoolRow.id == group.id).values(name=group.name)
        )
        self._replace_members(group)
        self.session.expire_all()
        self.session.flush()

    def delete_group(self, group_id: str) -> None:
        self.session.execute(delete(ProxyGroupResolutionRow).where(ProxyGroupResolutionRow.group_id == group_id))
        self.session.execute(delete(ProxyGroupMemberRow).where(ProxyGroupMemberRow.group_id == group_id))
        self.session.execute(delete(ProxyGroupDetailRow).where(ProxyGroupDetailRow.proxy_pool_id == group_id))
        self.session.execute(delete(ProxyPoolRow).where(ProxyPoolRow.id == group_id))
        self.session.flush()

    def group_references(self, group_id: str) -> list[tuple[str, str]]:
        return [
            (row.id, row.name)
            for row in self.session.scalars(select(ProfileRow))
            if row.spec.get("proxy_pool_id") == group_id
        ]

    def get_projections(self, projection_ids) -> list[Projection]:
        return [projection for projection_id in projection_ids if (projection := self.get_projection(projection_id))]

    def get_group_resolution(self, group_id: str, request_id: str) -> Projection | None:
        row = self.session.get(ProxyGroupResolutionRow, (group_id, request_id))
        return self.get_projection(row.proxy_id) if row else None

    def list_group_candidates(self, group_id: str) -> list[Projection]:
        group = self.get_group(group_id)
        if group is None:
            raise ProxyNotFoundError("Proxy group was not found")
        ordered_ids = [*group.member_ids[group.cursor :], *group.member_ids[: group.cursor]]
        return [
            projection
            for projection_id in ordered_ids
            if (projection := self.get_projection(projection_id))
            and projection.enabled
            and not projection.remote_missing
            and projection.credential_available
            and projection.health.state in {"healthy", "untested"}
        ]

    def commit_group_resolution(
        self,
        group_id: str,
        request_id: str,
        projection_id: str,
        expected_revision: int,
        expected_cursor_revision: int,
    ) -> Projection:
        if existing := self.get_group_resolution(group_id, request_id):
            return existing
        group = self.get_group(group_id)
        projection = self.get_projection(projection_id)
        if group is None or projection is None or projection_id not in group.member_ids:
            raise ProxyNotFoundError("Proxy group member was not found")
        if (
            group.cursor_revision != expected_cursor_revision
            or projection.revision != expected_revision
            or not projection.enabled
            or projection.remote_missing
            or not projection.credential_available
            or projection.health.state != "healthy"
        ):
            raise SelectionConflictError("Proxy group member changed before selection")
        next_cursor = (group.member_ids.index(projection_id) + 1) % len(group.member_ids)
        result = self.session.execute(
            update(ProxyGroupDetailRow)
            .where(
                ProxyGroupDetailRow.proxy_pool_id == group_id,
                ProxyGroupDetailRow.cursor_revision == expected_cursor_revision,
            )
            .values(cursor=next_cursor, cursor_revision=group.cursor_revision + 1)
        )
        if _rowcount(result) != 1:
            self.session.expire_all()
            if existing := self.get_group_resolution(group_id, request_id):
                return existing
            raise SelectionConflictError("Proxy group cursor changed concurrently")
        self.session.add(
            ProxyGroupResolutionRow(
                group_id=group_id,
                request_id=request_id,
                proxy_id=projection_id,
                created_at=datetime.now(UTC),
            )
        )
        self.session.flush()
        return projection

    def save_health(
        self,
        projection_id: str,
        expected_revision: int,
        health: Health,
        checked_at: datetime,
    ) -> None:
        result = self.session.execute(
            update(ProxyProjectionRow)
            .where(
                ProxyProjectionRow.proxy_id == projection_id,
                ProxyProjectionRow.revision == expected_revision,
            )
            .values(
                health_state=health.state,
                health_latency_ms=health.latency_ms,
                health_exit_ip=health.exit_ip,
                health_checked_at=health.checked_at or checked_at,
                health_source=health.source,
                health_error=health.error,
                revision=expected_revision + 1,
            )
        )
        if _rowcount(result) != 1:
            if self.session.get(ProxyProjectionRow, projection_id) is None:
                raise ProxyNotFoundError("Proxy was not found")
            raise RevisionConflictError("Proxy changed while health check was running")
        self.session.expire_all()
        self.session.flush()

    def _replace_members(self, group: ProxyGroup) -> None:
        self.session.execute(delete(ProxyGroupMemberRow).where(ProxyGroupMemberRow.group_id == group.id))
        self.session.add_all(
            ProxyGroupMemberRow(group_id=group.id, proxy_id=proxy_id, position=position)
            for position, proxy_id in enumerate(group.member_ids)
        )

    def _projection(self, row: ProxyProjectionRow) -> Projection:
        base = self.session.get(ProxyRow, row.proxy_id)
        assert base is not None
        profiles, groups = self.projection_references(row.proxy_id)
        last_synced_at = _aware(row.last_synced_at)
        stale = row.stale or last_synced_at is None
        if last_synced_at is not None:
            stale = stale or datetime.now(UTC) - last_synced_at > timedelta(minutes=5)
        return Projection(
            id=row.proxy_id,
            connection_id=row.connection_id,
            provider_id=row.provider_id,
            name=row.remote_name,
            name_override=row.name_override,
            enabled=base.enabled,
            remote_status=row.remote_status,
            remote_missing=row.remote_missing,
            carrier=row.carrier,
            city=row.city,
            region=row.region,
            exit_ip=row.exit_ip,
            http_endpoint=_endpoint(row.http_host, row.http_port),
            socks5_endpoint=_endpoint(row.socks5_host, row.socks5_port),
            credential_available=row.credential_available,
            health=Health(
                state=row.health_state,  # type: ignore[arg-type]
                latency_ms=row.health_latency_ms,
                exit_ip=row.health_exit_ip,
                checked_at=_aware(row.health_checked_at),
                source=row.health_source,  # type: ignore[arg-type]
                error=row.health_error,
            ),
            subscription_expires_at=_aware(row.subscription_expires_at),
            last_synced_at=last_synced_at,
            stale=stale,
            revision=row.revision,
            generation=row.generation,
            capabilities=_capabilities(row.capabilities),
            created_at=_required_aware(row.created_at),
            updated_at=_required_aware(row.updated_at),
            reference_count=len(profiles) + len(groups),
        )


class SqlAlchemyProxyUnitOfWork:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def __enter__(self):
        self._session = self._session_factory()
        self.repository = SqlAlchemyProxyRepository(self._session)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()


def _connection_row(connection: Connection) -> ProxyConnectionRow:
    return ProxyConnectionRow(id=connection.id, **_connection_values(connection))


def _connection_values(connection: Connection) -> dict[str, Any]:
    return {
        "name": connection.name,
        "secret_ref": connection.secret_ref,
        "status": connection.status,
        "revision": connection.revision,
        "generation": connection.generation,
        "sync_token": connection.sync_token,
        "sync_started_at": connection.sync_started_at,
        "last_verified_at": connection.last_verified_at,
        "last_synced_at": connection.last_synced_at,
        "last_error": connection.last_error,
        "capabilities": [asdict(capability) for capability in connection.capabilities],
        "created_at": connection.created_at,
        "updated_at": connection.updated_at,
    }


def _connection(row: ProxyConnectionRow) -> Connection:
    return Connection(
        id=row.id,
        name=row.name,
        secret_ref=row.secret_ref,
        status=row.status,  # type: ignore[arg-type]
        revision=row.revision,
        generation=row.generation,
        sync_token=row.sync_token,
        sync_started_at=_aware(row.sync_started_at),
        last_verified_at=_aware(row.last_verified_at),
        last_synced_at=_aware(row.last_synced_at),
        last_error=row.last_error,
        capabilities=_capabilities(row.capabilities),
        created_at=_required_aware(row.created_at),
        updated_at=_required_aware(row.updated_at),
    )


def _projection_row(projection: Projection) -> ProxyProjectionRow:
    return ProxyProjectionRow(proxy_id=projection.id, **_projection_values(projection))


def _projection_values(projection: Projection) -> dict[str, Any]:
    return {
        "connection_id": projection.connection_id,
        "provider_id": projection.provider_id,
        "remote_name": projection.name,
        "name_override": projection.name_override,
        "remote_status": projection.remote_status,
        "remote_missing": projection.remote_missing,
        "carrier": projection.carrier,
        "city": projection.city,
        "region": projection.region,
        "exit_ip": projection.exit_ip,
        "http_host": projection.http_endpoint.host if projection.http_endpoint else None,
        "http_port": projection.http_endpoint.port if projection.http_endpoint else None,
        "socks5_host": projection.socks5_endpoint.host if projection.socks5_endpoint else None,
        "socks5_port": projection.socks5_endpoint.port if projection.socks5_endpoint else None,
        "credential_available": projection.credential_available,
        "health_state": projection.health.state,
        "health_latency_ms": projection.health.latency_ms,
        "health_exit_ip": projection.health.exit_ip,
        "health_checked_at": projection.health.checked_at,
        "health_source": projection.health.source,
        "health_error": projection.health.error,
        "subscription_expires_at": projection.subscription_expires_at,
        "last_synced_at": projection.last_synced_at,
        "stale": projection.stale,
        "revision": projection.revision,
        "generation": projection.generation,
        "capabilities": [asdict(capability) for capability in projection.capabilities],
        "created_at": projection.created_at,
        "updated_at": projection.updated_at,
    }


def _group_detail_row(group: ProxyGroup) -> ProxyGroupDetailRow:
    return ProxyGroupDetailRow(
        proxy_pool_id=group.id,
        description=group.description,
        revision=group.revision,
        cursor=group.cursor,
        cursor_revision=group.cursor_revision,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _capabilities(values: list[dict[str, Any]]) -> tuple[Capability, ...]:
    return tuple(Capability(**value) for value in values)


def _endpoint(host: str | None, port: int | None) -> Endpoint | None:
    return Endpoint(host, port) if host is not None and port is not None else None


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _required_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _rowcount(result) -> int:
    return int(getattr(result, "rowcount", 0))
