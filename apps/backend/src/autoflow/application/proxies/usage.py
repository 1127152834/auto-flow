"""Sidecar-owned proxy users; durable remote-operation locks remain authoritative."""

from __future__ import annotations

from collections.abc import Callable

from autoflow.domain.proxies.errors import ProxyInUseError
from autoflow.domain.proxies.models import Projection


class ProxyUsage:
    def __init__(self) -> None:
        self.unconfirmed_users: Callable[[], bool] = lambda: False
        self.bindings: dict[str, Projection] = {}
        self.versions: dict[str, str] = {}
        self.controls: dict[tuple[str, str], tuple[str | None, str]] = {}

    @staticmethod
    def identity(proxy: Projection) -> tuple[str, str]:
        return proxy.connection_id, proxy.provider_id

    def bind(
        self, owner: str, proxy: Projection, *, connection_version: str | None = None
    ) -> None:
        if self.unconfirmed_users():
            raise ProxyInUseError("遗留浏览器清理尚未确认，代理控制暂不可用")
        if self.identity(proxy) in self.controls:
            raise ProxyInUseError("代理正在切换，暂不能启动新会话")
        self.bindings[owner] = proxy
        if connection_version is not None:
            self.versions[owner] = connection_version

    def check(self, proxy: Projection, owner: str | None) -> None:
        if self.unconfirmed_users():
            raise ProxyInUseError("遗留浏览器清理尚未确认，代理控制暂不可用")
        identity = self.identity(proxy)
        users = {
            key
            for key, value in self.bindings.items()
            if self.identity(value) == identity
        }
        control = self.controls.get(identity)
        if users - ({owner} if owner else set()) or (
            control is not None and control[0] != owner
        ):
            raise ProxyInUseError("代理正在被其他会话或操作使用")
        if owner is None and control is not None:
            raise ProxyInUseError("代理已有进行中的操作")

    def claim(self, proxy: Projection, owner: str | None, token: str) -> None:
        self.check(proxy, owner)
        identity = self.identity(proxy)
        if identity in self.controls and self.controls[identity] != (owner, token):
            raise ProxyInUseError("同一代理不能并行切换")
        self.controls[identity] = owner, token

    def unclaim(self, token: str) -> None:
        for key, value in tuple(self.controls.items()):
            if value[1] == token:
                self.controls.pop(key, None)

    def release(self, owner: str) -> None:
        self.bindings.pop(owner, None)
        self.versions.pop(owner, None)
        for key, value in tuple(self.controls.items()):
            if value[0] == owner:
                self.controls.pop(key, None)
