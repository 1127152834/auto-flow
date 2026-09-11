from datetime import UTC, datetime

import pytest

from autoflow.application.proxies.groups import GroupService, ResolveProxyForProfile
from autoflow.domain.proxies.errors import ProxyMemberRiskError
from autoflow.domain.proxies.models import (
    Endpoint,
    Health,
    Projection,
    ProxyGroup,
    unavailable_capabilities,
)


def _projection(proxy_id: str, *, health: str = "untested") -> Projection:
    now = datetime.now(UTC)
    return Projection(
        id=proxy_id,
        connection_id="connection-1",
        provider_id=f"remote-{proxy_id}",
        name=proxy_id,
        name_override=None,
        enabled=True,
        remote_status=None,
        remote_missing=False,
        carrier=None,
        city=None,
        region=None,
        exit_ip=None,
        http_endpoint=Endpoint("proxy.example", 8000),
        socks5_endpoint=None,
        credential_available=True,
        health=Health(state=health),  # type: ignore[arg-type]
        subscription_expires_at=None,
        last_synced_at=now,
        stale=False,
        revision=0,
        generation=1,
        capabilities=unavailable_capabilities(),
        created_at=now,
        updated_at=now,
    )


class MemoryRepository:
    def __init__(self):
        self.projections = {item.id: item for item in (_projection("p1"), _projection("p2"))}
        self.groups = {}
        self.resolutions = {}
        self.next_index = 0

    def get_projections(self, ids):
        return [self.projections[item] for item in ids if item in self.projections]

    def add_group(self, group):
        self.groups[group.id] = group

    def get_group(self, group_id):
        return self.groups.get(group_id)

    def get_group_resolution(self, group_id, request_id):
        proxy_id = self.resolutions.get((group_id, request_id))
        return self.projections.get(proxy_id)

    def list_group_candidates(self, group_id):
        group = self.groups[group_id]
        ids = [*group.member_ids[group.cursor :], *group.member_ids[: group.cursor]]
        return [self.projections[item] for item in ids]

    def commit_group_resolution(
        self,
        group_id,
        request_id,
        projection_id,
        expected_revision,
        expected_cursor_revision,
    ):
        key = (group_id, request_id)
        if key not in self.resolutions:
            self.resolutions[key] = projection_id
            group = self.groups[group_id]
            self.groups[group_id] = ProxyGroup(
                **{
                    **group.__dict__,
                    "cursor": (group.member_ids.index(projection_id) + 1) % len(group.member_ids),
                    "cursor_revision": group.cursor_revision + 1,
                }
            )
        return self.projections[self.resolutions[key]]

    def save_health(self, projection_id, expected_revision, health, checked_at):
        self.projections[projection_id] = Projection(
            **{
                **self.projections[projection_id].__dict__,
                "health": health,
                "revision": expected_revision + 1,
            }
        )


class MemoryUnitOfWork:
    def __init__(self, repository):
        self.repository = repository

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self):
        pass

    def rollback(self):
        pass


class HealthyProbe:
    async def probe(self, projection):
        return Health(state="healthy", checked_at=datetime.now(UTC), source="local_probe")


@pytest.mark.asyncio
async def test_group_requires_risk_confirmation_and_resolution_is_round_robin_idempotent():
    repository = MemoryRepository()
    groups = GroupService(repository)  # type: ignore[arg-type]
    with pytest.raises(ProxyMemberRiskError) as exc_info:
        groups.create(name="Local", description="", member_ids=["p1", "p2"], acknowledge_risk=False)
    assert exc_info.value.details == {"member_ids": ["p1", "p2"]}

    group = groups.create(name="Local", description="", member_ids=["p1", "p2"], acknowledge_risk=True)
    resolver = ResolveProxyForProfile(
        lambda: MemoryUnitOfWork(repository), HealthyProbe()  # type: ignore[arg-type]
    )
    first = await resolver.resolve_group(group.id, "launch-1")
    repeated = await resolver.resolve_group(group.id, "launch-1")
    second = await resolver.resolve_group(group.id, "launch-2")
    assert first.id == repeated.id == "p1"
    assert second.id == "p2"
