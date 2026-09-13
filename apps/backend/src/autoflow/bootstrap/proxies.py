from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Literal

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
from autoflow.bootstrap.http_routes import ProxyHttpServices, register_proxy_routes
from autoflow.domain.profiles.errors import (
    ProxyUnavailable,
)
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.proxies.errors import ProxyError
from autoflow.infrastructure.credentials.system import SystemCredentialStore
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


def configure_proxy_management(app: FastAPI, database: Path) -> ProxyManagementRuntime:
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
    )
    operations = SqlAlchemyProxyOperations(session_factory)
    operations.recover()
    remote = ProxyRemoteControls(lambda: SqlAlchemyProxyUnitOfWork(session_factory), operations, credentials, provider)
    app.state.proxy_remote_controls = remote

    async def resolve(body: CopyCredentialRequest) -> str:
        projection = application.get_projection(str(body.proxy_id))
        value = await loader(projection)
        return format_proxy_credential(
            projection, value.username, value.password, protocol=body.protocol, format=body.format,
        )

    register_proxy_routes(app, ProxyHttpServices(application, remote, resolve))
    configure_proxy_validation(app)

    async def resolve_profile(
        profile: Profile, request_id: str
    ) -> ProfileBrowserProxy | None:
        spec = profile.spec
        if spec.proxy_mode == "none":
            return None
        try:
            if spec.proxy_mode == "pool":
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
            return ProfileBrowserProxy(
                f"{protocol}://{url.rsplit('@', 1)[-1]}", value.username, value.password
            )
        except ProxyUnavailable:
            raise
        except ProxyError:
            raise ProxyUnavailable from None

    async def close():
        try:
            await remote.close()
        finally:
            session_factory.dispose()
    return ProxyManagementRuntime(resolve_profile, close)
