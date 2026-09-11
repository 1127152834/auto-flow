from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from autoflow.domain.proxies.errors import ProxyError
from autoflow.domain.proxies.models import (
    Connection,
    Health,
    Projection,
    ProviderPage,
    ProviderProxy,
    unavailable_capabilities,
)
from autoflow.domain.proxies.ports import ProxyRepository


class SyncService:
    def __init__(self, repository: ProxyRepository):
        self.repository = repository

    def apply(
        self,
        connection: Connection,
        page: ProviderPage,
        generation: int,
    ) -> tuple[
        Connection,
        int,
        int,
        Literal["complete", "partial", "unknown"],
        int | None,
    ]:
        now = datetime.now(UTC)
        for item in page.items:
            current = self.repository.get_projection_by_provider_id(connection.id, item.provider_id)
            health = current.health if current and _same_connection_data(current, item) else Health()
            projection = Projection(
                id=current.id if current else str(uuid4()),
                connection_id=connection.id,
                provider_id=item.provider_id,
                name=item.name,
                name_override=current.name_override if current else None,
                enabled=current.enabled if current else True,
                remote_status=item.remote_status,
                remote_missing=False,
                carrier=item.carrier,
                city=item.city,
                region=item.region,
                exit_ip=item.exit_ip,
                http_endpoint=item.http_endpoint,
                socks5_endpoint=item.socks5_endpoint,
                credential_available=item.credential_available,
                health=health,
                subscription_expires_at=item.subscription_expires_at,
                last_synced_at=now,
                stale=False,
                revision=current.revision + 1 if current else 0,
                generation=generation,
                capabilities=current.capabilities if current else unavailable_capabilities(),
                created_at=current.created_at if current else now,
                updated_at=now,
                reference_count=current.reference_count if current else 0,
            )
            self.repository.upsert_projection(projection)
        missing = self.repository.finish_sync(connection.id, generation, page.completeness == "complete")
        assert connection.sync_token is not None
        updated = self.repository.complete_sync(
            connection.id, generation, connection.sync_token, now
        )
        return updated, len(page.items), missing, page.completeness, page.total


def provider_error(error: ProxyError) -> dict:
    return {
        "code": error.code,
        "message": str(error),
        "field_errors": error.details,
        "retry_after_seconds": getattr(error, "retry_after_seconds", None),
        "outcome_unknown": getattr(error, "outcome_unknown", False),
    }


def _same_connection_data(current: Projection, incoming: ProviderProxy) -> bool:
    return (
        current.http_endpoint == incoming.http_endpoint
        and current.socks5_endpoint == incoming.socks5_endpoint
        and current.credential_available == incoming.credential_available
        and current.exit_ip == incoming.exit_ip
    )
