from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from autoflow.domain.proxies.errors import (
    InvalidProxyGroupError,
    NoAvailableProxyError,
    ProxyGroupInUseError,
    ProxyMemberRiskError,
    ProxyNotFoundError,
    RevisionConflictError,
    SelectionConflictError,
)
from autoflow.domain.proxies.models import Projection, ProxyGroup
from autoflow.domain.proxies.ports import (
    ProxyHealthProbe,
    ProxyRepository,
    ProxyUnitOfWork,
)


class GroupService:
    def __init__(self, repository: ProxyRepository):
        self.repository = repository

    def create(
        self,
        *,
        name: str,
        description: str,
        member_ids: list[str],
        acknowledge_risk: bool,
    ) -> ProxyGroup:
        self._validate_members(member_ids, acknowledge_risk)
        now = datetime.now(UTC)
        group = ProxyGroup(
            id=str(uuid4()),
            name=name.strip(),
            description=description,
            member_ids=tuple(member_ids),
            revision=0,
            cursor=0,
            cursor_revision=0,
            created_at=now,
            updated_at=now,
        )
        self.repository.add_group(group)
        return group

    def get(self, group_id: str) -> ProxyGroup:
        group = self.repository.get_group(group_id)
        if group is None:
            raise ProxyNotFoundError("Proxy group was not found")
        return group

    def list_groups(self, *, q: str | None, offset: int, limit: int) -> tuple[list[ProxyGroup], int]:
        return self.repository.list_groups(q=q, offset=offset, limit=limit)

    def update(
        self,
        group_id: str,
        *,
        expected_revision: int,
        name: str,
        description: str,
        member_ids: list[str],
        acknowledge_risk: bool,
    ) -> ProxyGroup:
        group = self.get(group_id)
        if group.revision != expected_revision:
            raise RevisionConflictError("Proxy group revision is stale")
        self._validate_members(member_ids, acknowledge_risk)
        updated = replace(
            group,
            name=name.strip(),
            description=description,
            member_ids=tuple(member_ids),
            revision=group.revision + 1,
            cursor=min(group.cursor, max(len(member_ids) - 1, 0)),
            cursor_revision=group.cursor_revision + 1,
            updated_at=datetime.now(UTC),
        )
        self.repository.save_group(updated, expected_revision)
        return updated

    def delete(self, group_id: str) -> None:
        self.get(group_id)
        references = self.repository.group_references(group_id)
        if references:
            raise ProxyGroupInUseError(
                "Proxy group is used by browser profiles",
                details={"reference_count": len(references)},
            )
        self.repository.delete_group(group_id)

    def references(self, group_id: str) -> list[tuple[str, str]]:
        self.get(group_id)
        return self.repository.group_references(group_id)

    def _validate_members(self, member_ids: list[str], acknowledge_risk: bool) -> None:
        if len(member_ids) != len(set(member_ids)):
            raise InvalidProxyGroupError("Proxy group members must be unique", details={"field": "member_ids"})
        members = {member.id: member for member in self.repository.get_projections(member_ids)}
        missing = [member_id for member_id in member_ids if member_id not in members]
        remote_missing = [member_id for member_id, member in members.items() if member.remote_missing]
        if missing or remote_missing:
            raise InvalidProxyGroupError(
                "Proxy group contains missing remote proxies",
                details={"member_ids": [*missing, *remote_missing]},
            )
        risky = [
            member_id
            for member_id in member_ids
            if _is_risky(members[member_id])
        ]
        if risky and not acknowledge_risk:
            raise ProxyMemberRiskError(
                "Proxy group contains untested or unavailable members",
                details={"member_ids": risky},
            )


class ResolveProxyForProfile:
    def __init__(self, uow_factory: Callable[[], ProxyUnitOfWork], probe: ProxyHealthProbe):
        self._uow_factory = uow_factory
        self._probe = probe

    async def resolve_group(self, group_id: str, request_id: str) -> Projection:
        with self._uow_factory() as uow:
            group = GroupService(uow.repository).get(group_id)
        for _ in range(max(1, len(group.member_ids) * 4)):
            with self._uow_factory() as uow:
                if existing := uow.repository.get_group_resolution(group_id, request_id):
                    return existing
                group = GroupService(uow.repository).get(group_id)
                candidates = uow.repository.list_group_candidates(group_id)
            if not candidates:
                raise NoAvailableProxyError("Proxy group has no available member")
            candidate = candidates[0]
            if candidate.health.state == "untested":
                health = await self._probe.probe(candidate)
                with self._uow_factory() as uow:
                    try:
                        uow.repository.save_health(
                            candidate.id,
                            candidate.revision,
                            health,
                            health.checked_at or datetime.now(UTC),
                        )
                        uow.commit()
                    except RevisionConflictError:
                        continue
                continue
            with self._uow_factory() as uow:
                try:
                    selected = uow.repository.commit_group_resolution(
                        group_id,
                        request_id,
                        candidate.id,
                        candidate.revision,
                        group.cursor_revision,
                    )
                    uow.commit()
                    return selected
                except SelectionConflictError:
                    continue
        raise SelectionConflictError("Proxy group selection changed too often; retry launch")


def _is_risky(member: Projection) -> bool:
    return not member.enabled or not member.credential_available or member.health.state != "healthy"
