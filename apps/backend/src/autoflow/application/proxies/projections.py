from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from autoflow.domain.proxies.errors import ProxyNotFoundError, RevisionConflictError
from autoflow.domain.proxies.models import Projection
from autoflow.domain.proxies.ports import ProxyRepository


class ProjectionService:
    def __init__(self, repository: ProxyRepository):
        self.repository = repository

    def get(self, projection_id: str) -> Projection:
        projection = self.repository.get_projection(projection_id)
        if projection is None:
            raise ProxyNotFoundError("Proxy was not found")
        return projection

    def list_projections(self, **filters) -> tuple[list[Projection], int]:
        return self.repository.list_projections(**filters)

    def update(
        self,
        projection_id: str,
        *,
        expected_revision: int,
        name_override: str | None,
        enabled: bool | None,
        change_name: bool,
    ) -> Projection:
        projection = self.get(projection_id)
        if projection.revision != expected_revision:
            raise RevisionConflictError("Proxy revision is stale")
        updated = replace(
            projection,
            name_override=name_override if change_name else projection.name_override,
            enabled=enabled if enabled is not None else projection.enabled,
            revision=projection.revision + 1,
            updated_at=datetime.now(UTC),
        )
        self.repository.save_projection(updated, expected_revision)
        return updated

    def references(self, projection_id: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        self.get(projection_id)
        return self.repository.projection_references(projection_id)
