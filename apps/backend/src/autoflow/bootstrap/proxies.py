from collections.abc import Callable
from functools import cached_property
from pathlib import Path

from fastapi import FastAPI

from autoflow.adapters.http.internal_proxy_credentials import (
    CopyCredentialRequest,
    internal_proxy_credentials_router,
)
from autoflow.adapters.http.proxies import proxy_router
from autoflow.adapters.http.proxy_validation import configure_proxy_validation
from autoflow.application.proxies.credential_loader import ProxyCredentialLoader
from autoflow.application.proxies.credentials import format_proxy_credential
from autoflow.application.proxies.facade import ProxyApplication
from autoflow.infrastructure.credentials.system import SystemCredentialStore
from autoflow.infrastructure.database.proxies import (
    SqlAlchemyProxyUnitOfWork,
)
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


def configure_proxy_management(app: FastAPI, database: Path) -> Callable[[], None]:
    session_factory = create_session_factory(database)
    credentials = LazySystemCredentialStore()
    provider = ProxyPanelReadProvider()
    loader = ProxyCredentialLoader(
        lambda: SqlAlchemyProxyUnitOfWork(session_factory), credentials, provider
    )
    application = ProxyApplication(
        uow_factory=lambda: SqlAlchemyProxyUnitOfWork(session_factory),
        credentials=credentials,
        provider=provider,
        probe=HttpProxyProbe(credentials, load_credentials=loader),
    )
    app.include_router(proxy_router(application=application))

    async def resolve(body: CopyCredentialRequest) -> str:
        projection = application.get_projection(str(body.proxy_id))
        value = await loader(projection)
        return format_proxy_credential(
            projection, value.username, value.password, protocol=body.protocol, format=body.format,
        )

    app.include_router(internal_proxy_credentials_router(resolve))
    configure_proxy_validation(app)
    return session_factory.dispose
