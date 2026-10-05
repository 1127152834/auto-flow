import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import FastAPI

from autoflow.adapters.http.internal_proxy_credentials import (
    CopyCredentialRequest,
)
from autoflow.adapters.http.proxy_validation import configure_proxy_validation
from autoflow.application.proxies.credential_loader import ProxyCredentialLoader
from autoflow.application.proxies.credentials import format_proxy_credential
from autoflow.application.proxies.facade import ProxyApplication
from autoflow.application.proxies.groups import ResolveProxyForProfile
from autoflow.application.proxies.remote_controls import ProxyRemoteControls
from autoflow.application.proxies.workflow import WorkflowProxyService
from autoflow.bootstrap.http_routes import ProxyHttpServices, register_proxy_routes
from autoflow.domain.identities.proxy_binding import Member, choose_member
from autoflow.domain.identities.proxy_binding import bind as bind_member
from autoflow.domain.profiles.errors import (
    ProxyUnavailable,
)
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.projects.ports import ProjectResourceReferences
from autoflow.domain.proxies.errors import ProxyError
from autoflow.infrastructure.credentials.system import SystemCredentialStore
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.proxies import (
    SqlAlchemyProxyUnitOfWork,
)
from autoflow.infrastructure.database.proxy_operations import SqlAlchemyProxyOperations
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.providers.proxy.probe import HttpProxyProbe
from autoflow.providers.proxy.proxypanel import ProxyPanelReadProvider


class LazySystemCredentialStore:
    """Keep offline/local management usable when the OS vault is locked or absent."""

    @cached_property
    def _store(self) -> SystemCredentialStore:
        return SystemCredentialStore()

    def read(self, key: str) -> bytes | None:
        return self._store.read(key)

    def write(self, key: str, value: bytes) -> None:
        self._store.write(key, value)

    def delete(self, key: str) -> None:
        self._store.delete(key)


@dataclass(frozen=True)
class ProxyManagementRuntime:
    resolve_profile: Callable[[Profile, str], Awaitable[ProfileBrowserProxy | None]]
    close: Callable[[], Awaitable[None]]
    workflow: WorkflowProxyService


def configure_proxy_management(
    app: FastAPI,
    database: Path,
    references: ProjectResourceReferences | None = None,
    *,
    session_factory: Any | None = None,
) -> ProxyManagementRuntime:
    # Remediation M1 R1-13: share the application's engine; only a factory created here is disposed here.
    owns_factory = session_factory is None
    if session_factory is None:
        session_factory = create_session_factory(database)
    credentials = LazySystemCredentialStore()
    provider = ProxyPanelReadProvider()
    loader = ProxyCredentialLoader(
        lambda: SqlAlchemyProxyUnitOfWork(session_factory), credentials, provider
    )
    probe = HttpProxyProbe(credentials, load_credentials=loader)
    application = ProxyApplication(
        uow_factory=lambda: SqlAlchemyProxyUnitOfWork(session_factory),
        credentials=credentials,
        provider=provider,
        probe=probe,
        references=references,
    )
    operations = SqlAlchemyProxyOperations(session_factory)
    operations.recover()
    remote = ProxyRemoteControls(lambda: SqlAlchemyProxyUnitOfWork(session_factory), operations, credentials, provider)
    app.state.proxy_remote_controls = remote
    workflow = WorkflowProxyService(remote, remote.usage, probe)

    async def resolve(body: CopyCredentialRequest) -> str:
        projection = application.get_projection(str(body.proxy_id))
        value = await loader(projection)
        return format_proxy_credential(
            projection, value.username, value.password, protocol=body.protocol, format=body.format,
        )

    register_proxy_routes(app, ProxyHttpServices(application, remote, resolve))
    configure_proxy_validation(app)

    identities = SqlAlchemyIdentities(session_factory)

    def sticky_member(identity_id: str, pool_id: str) -> Any:
        """Remediation M4 R4-04: the identity's own pool member, bound on first use."""
        for _attempt in range(4):
            binding = identities.proxy_binding(identity_id)
            with cast(Any, SqlAlchemyProxyUnitOfWork)(session_factory) as uow:
                candidates = uow.repository.list_group_candidates(pool_id)
            members = [
                Member(item.id, item.region, item.credential_available and item.health.state != "unhealthy")
                for item in candidates
            ]
            choice = choose_member(binding, pool_id, members)
            if choice.outcome in {"confirm", "unavailable"} or choice.member_id is None:
                raise ProxyUnavailable(choice.reason or "身份的代理不可用")
            chosen = next(item for item in candidates if item.id == choice.member_id)
            if choice.outcome in {"bind", "replace"}:
                member = next(item for item in members if item.member_id == chosen.id)
                if not identities.swap_proxy_binding(identity_id, binding, bind_member(pool_id, member, binding)):
                    continue  # another run bound it first; use what it stored
            return chosen
        raise ProxyUnavailable("身份的代理绑定频繁变化，请重试")

    async def resolve_profile(
        profile: Profile, request_id: str, identity_id: str | None = None,
    ) -> ProfileBrowserProxy | None:
        spec = profile.spec
        if spec.proxy_mode == "none":
            return None
        try:
            if spec.proxy_mode == "pool" and identity_id is not None:
                if spec.proxy_pool_id is None:
                    raise ProxyUnavailable
                projection = await asyncio.to_thread(sticky_member, identity_id, spec.proxy_pool_id)
            elif spec.proxy_mode == "pool":
                if spec.proxy_pool_id is None:
                    raise ProxyUnavailable
                projection = await ResolveProxyForProfile(
                    lambda: SqlAlchemyProxyUnitOfWork(session_factory), probe
                ).resolve_group(spec.proxy_pool_id, request_id)
            else:
                if spec.proxy_id is None:
                    raise ProxyUnavailable
                projection = application.get_projection(spec.proxy_id)
                if not projection.enabled:
                    raise ProxyUnavailable
            value = await loader(projection)
            protocol: Literal["socks5", "http"] = (
                "socks5" if projection.socks5_endpoint else "http"
            )
            if projection.socks5_endpoint is None and projection.http_endpoint is None:
                raise ProxyUnavailable
            url = format_proxy_credential(
                projection,
                value.username,
                value.password,
                protocol=protocol,
                format="url",
            )
            if operations.active(projection.id) is not None:
                raise ProxyUnavailable
            _, connection, _ = remote._context(projection.id)
            remote.usage.bind(request_id, projection, connection_version=connection.secret_ref)
            return ProfileBrowserProxy(
                f"{protocol}://{url.rsplit('@', 1)[-1]}", value.username, value.password, projection.id
            )
        except ProxyUnavailable:
            raise
        except ProxyError:
            raise ProxyUnavailable from None

    async def close():
        try:
            await remote.close()
        finally:
            if owns_factory:
                session_factory.dispose()
    return ProxyManagementRuntime(resolve_profile, close, workflow)
