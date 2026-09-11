from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal

from autoflow.domain.proxies.errors import (
    CapabilityUnavailableError,
    ProxyNotFoundError,
)
from autoflow.domain.proxies.models import Health, Projection
from autoflow.domain.proxies.ports import ProxyRepository


class HealthService:
    def __init__(self, repository: ProxyRepository):
        self.repository = repository

    def target(self, projection_id: str, protocol: Literal["http", "socks5"]) -> Projection:
        projection = self.repository.get_projection(projection_id)
        if projection is None:
            raise ProxyNotFoundError("Proxy was not found")
        if protocol == "http" and projection.http_endpoint is None:
            raise CapabilityUnavailableError("HTTP proxy endpoint is unavailable")
        if protocol == "socks5" and projection.socks5_endpoint is None:
            raise CapabilityUnavailableError("SOCKS5 proxy endpoint is unavailable")
        return replace(
            projection,
            http_endpoint=projection.http_endpoint if protocol == "http" else None,
            socks5_endpoint=projection.socks5_endpoint if protocol == "socks5" else None,
        )

    def record(self, projection: Projection, health: Health) -> Health:
        if health.checked_at is None:
            health = replace(health, checked_at=datetime.now(UTC))
        assert health.checked_at is not None
        self.repository.save_health(
            projection.id,
            projection.revision,
            health,
            health.checked_at,
        )
        return health
