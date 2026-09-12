import ipaddress
import json
from typing import Literal
from urllib.parse import quote

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.proxies.errors import (
    CapabilityUnavailableError,
    CredentialStoreError,
    ProxyNotFoundError,
)
from autoflow.domain.proxies.models import Projection
from autoflow.domain.proxies.ports import ProxyRepository


def resolve_proxy_credential(
    repository: ProxyRepository,
    credentials: CredentialStore,
    *,
    proxy_id: str,
    protocol: Literal["http", "socks5"],
    format: Literal["username", "password", "url"],
) -> str:
    """Resolve a single value for the authenticated desktop host, never the renderer."""
    projection = repository.get_projection(proxy_id)
    if projection is None:
        raise ProxyNotFoundError("代理不存在")
    endpoint = projection.http_endpoint if protocol == "http" else projection.socks5_endpoint
    if not projection.credential_available or endpoint is None:
        raise CapabilityUnavailableError("此代理的凭据尚不可用")
    try:
        raw = credentials.read(f"proxy-endpoint:{proxy_id}")
        if raw is None:
            raise CredentialStoreError("代理凭据尚未保存，请重新同步凭据")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError
        username, password = value.get("username"), value.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            raise TypeError
    except (CredentialStoreUnavailableError, ValueError, TypeError, UnicodeError):
        raise CredentialStoreError("无法读取代理凭据") from None
    return format_proxy_credential(projection, username, password, protocol=protocol, format=format)


def format_proxy_credential(
    projection: Projection,
    username: str,
    password: str,
    *,
    protocol: Literal["http", "socks5"],
    format: Literal["username", "password", "url"],
) -> str:
    endpoint = projection.http_endpoint if protocol == "http" else projection.socks5_endpoint
    if endpoint is None or not projection.credential_available:
        raise CapabilityUnavailableError("此代理的凭据尚不可用")
    if format == "username":
        return username
    if format == "password":
        return password
    host = endpoint.host
    if (
        not host or not 1 <= endpoint.port <= 65535
        or any(ord(char) < 33 or char in "/\\@?#[]" for char in host)
    ):
        raise CapabilityUnavailableError("代理地址格式不可用")
    if ":" in host:
        try:
            host = f"[{ipaddress.IPv6Address(host)}]"
        except ValueError:
            raise CapabilityUnavailableError("代理地址格式不可用") from None
    return f"{protocol}://{quote(username, safe='')}:{quote(password, safe='')}@{host}:{endpoint.port}"
