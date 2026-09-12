"""Fetch data-plane credentials only for an explicitly used proxy."""

from collections.abc import Callable
from typing import Protocol

from autoflow.domain.credentials import CredentialStore
from autoflow.domain.proxies.errors import (
    CapabilityUnavailableError,
    RevisionConflictError,
)
from autoflow.domain.proxies.models import Projection, ProviderCredentials
from autoflow.domain.proxies.ports import ProxyUnitOfWork

from .connections import ConnectionService


class CredentialProvider(Protocol):
    async def get_credentials(
        self, api_key: bytes, provider_id: str
    ) -> ProviderCredentials: ...


class ProxyCredentialLoader:
    def __init__(
        self,
        uow_factory: Callable[[], ProxyUnitOfWork],
        credentials: CredentialStore,
        provider: CredentialProvider,
    ):
        self._uow_factory = uow_factory
        self._credentials = credentials
        self._provider = provider

    async def __call__(self, projection: Projection) -> ProviderCredentials:
        if (
            projection.remote_missing
            or projection.stale
            or not projection.credential_available
        ):
            raise CapabilityUnavailableError("代理已过期或连接信息已失效，请刷新代理")
        with self._uow_factory() as uow:
            service = ConnectionService(uow.repository, self._credentials)
            connection = service.get(projection.connection_id)
            key = service.read_key(connection)
        value = await self._provider.get_credentials(key, projection.provider_id)
        if (
            projection.http_endpoint and value.http_endpoint != projection.http_endpoint
        ) or (
            projection.socks5_endpoint
            and value.socks5_endpoint != projection.socks5_endpoint
        ):
            raise RevisionConflictError("代理端点已变化，请刷新代理后重试")
        with self._uow_factory() as uow:
            current = uow.repository.get_projection(projection.id)
            latest = uow.repository.get_connection(projection.connection_id)
            if (
                current is None
                or latest is None
                or current.revision != projection.revision
                or latest.secret_ref != connection.secret_ref
                or latest.generation != connection.generation
            ):
                raise RevisionConflictError("连接或代理已变化，请刷新后重试")
        return value
