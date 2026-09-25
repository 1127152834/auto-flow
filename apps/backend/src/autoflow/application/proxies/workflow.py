"""Owned worker access to the existing proxy commands, never a second provider client."""

from __future__ import annotations

import asyncio
import math
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from autoflow.domain.proxies.errors import (
    ProviderSchemaError,
    ProxyError,
    ProxyNotFoundError,
    RevisionConflictError,
)

from .remote_controls import ProxyRemoteControls
from .usage import ProxyUsage


def failure(error: ProxyError) -> dict[str, Any]:
    code = {
        "PROXYPANEL_RATE_LIMITED": "PROXY_RATE_LIMITED",
        "PROXYPANEL_AUTH_FAILED": "PROXY_AUTH_FAILED",
        "PROXY_IN_USE": "PROXY_BUSY",
        "OPERATION_IN_PROGRESS": "PROXY_BUSY",
    }.get(error.code, error.code)
    fatal = code in {
        "PROXY_AUTH_FAILED",
        "RESOURCE_NOT_FOUND",
        "VALIDATION_ERROR",
        "STALE_PROJECTION",
        "PROXYPANEL_NOT_FOUND",
        "PROXYPANEL_VALIDATION_ERROR",
        "CAPABILITY_UNAVAILABLE",
    }
    return {
        "code": code,
        "message": str(error),
        "retryAfterSeconds": getattr(error, "retry_after_seconds", None),
        "retryAllowed": not fatal,
        "outcomeUnknown": bool(getattr(error, "outcome_unknown", False)),
    }


def observation(state) -> dict[str, Any]:
    return {
        "exitIp": state.current_ip,
        "country": state.country,
        "city": state.proxy.city,
        "carrier": state.proxy.carrier,
        "locationGeneration": state.location_generation,
        "observedAt": datetime.now(UTC).isoformat(),
        "source": "provider_readback",
    }


def matches(state, target) -> bool:
    return bool(
        state.country == target.country
        and state.proxy.city in (target.cities or (target.city,))
        and (not target.carrier or state.proxy.carrier == target.carrier)
    )


class WorkflowProxyService:
    def __init__(self, remote: ProxyRemoteControls, usage: ProxyUsage, probe) -> None:
        self.remote, self.usage, self.probe = remote, usage, probe
        self._prepared: dict[str, dict[str, Any]] = {}

    def release(self, owner: str) -> None:
        for key, value in tuple(self._prepared.items()):
            if value["owner"] == owner:
                self._prepared.pop(key, None)
                self.usage.unclaim(key)
        self.usage.release(owner)

    async def call(self, owner: str, payload: dict[str, Any]) -> dict[str, Any]:
        method = payload.get("method")
        visit = payload.get("executionId")
        if not isinstance(visit, str) or not visit:
            raise ValueError("Proxy request has no node execution identity")
        token = f"{owner}:{payload.get('generation', 0)}:{visit}"
        if method == "finish":
            self._prepared.pop(token, None)
            self.usage.unclaim(token)
            return {}
        self._validate(payload)
        payload = {
            **payload,
            "_deadline": asyncio.get_running_loop().time()
            + float(payload["confirmationTimeoutSeconds"]),
        }
        try:
            async with asyncio.timeout(
                float(payload.get("confirmationTimeoutSeconds", 30))
            ):
                if method == "query":
                    return await self._query(owner, payload)
                if method == "prepare":
                    return await self._prepare(owner, token, payload)
                if method == "attempt":
                    return await self._attempt(owner, token, payload)
                raise ValueError("Unknown proxy method")
        except (asyncio.CancelledError, ProviderSchemaError):
            self._prepared.pop(token, None)
            self.usage.unclaim(token)
            raise
        except ProxyError as error:
            if method == "prepare":
                self._prepared.pop(token, None)
                self.usage.unclaim(token)
            prepared = self._prepared.get(token, {})
            operation_id = prepared.get("operationId")
            operation = (
                self.remote.operations.get(operation_id) if operation_id else None
            )
            return {
                "status": "failed",
                "operationId": operation_id,
                "error": failure(error),
                "requestsSent": self._count_request(prepared, operation),
            }
        except TimeoutError:
            if method == "prepare":
                self._prepared.pop(token, None)
                self.usage.unclaim(token)
            prepared = self._prepared.get(token, {})
            operation_id = prepared.get("operationId") or (
                payload.get("operationId") if method == "query" else None
            )
            prepared["reportedStatus"] = "unknown"
            operation = (
                self.remote.operations.get(operation_id) if operation_id else None
            )
            sent = self._count_request(prepared, operation)
            return {
                "status": "unknown" if operation else "failed",
                "operationId": operation_id,
                "requestsSent": sent,
                "error": {
                    "code": "PROXY_OUTCOME_UNKNOWN"
                    if operation
                    else "PROXY_QUERY_TIMEOUT",
                    "message": "代理操作确认超时；未重复发送",
                    "retryAfterSeconds": None,
                    "retryAllowed": True,
                    "outcomeUnknown": bool(operation),
                },
            }

    @staticmethod
    def _validate(payload):
        if payload.get("method") not in {"prepare", "attempt", "query"}:
            raise ValueError("Invalid proxy method")
        if payload.get("action") not in {"change_ip", "relocate", "query"}:
            raise ValueError("Invalid proxy action")
        if payload.get("target") not in {"current", "specified"}:
            raise ValueError("Invalid proxy target")
        for key in (
            "confirmationTimeoutSeconds",
            "retryIntervalSeconds",
            "maxAttempts",
        ):
            value = payload.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError("Invalid proxy numeric configuration")
        if not float(payload["maxAttempts"]).is_integer():
            raise ValueError("Invalid attempt count")
        if payload["target"] == "specified" and not isinstance(
            payload.get("proxyId"), str
        ):
            raise ValueError("Invalid proxy identity")
        if payload["action"] == "relocate" and not isinstance(
            payload.get("locationId"), str
        ):
            raise ValueError("Invalid location identity")
        if payload["method"] == "attempt":
            attempt = payload.get("attempt")
            if (
                isinstance(attempt, bool)
                or not isinstance(attempt, int)
                or not 1 <= attempt <= payload["maxAttempts"]
            ):
                raise ValueError("Invalid attempt identity")

    def _target(self, owner, payload):
        current = self.usage.bindings.get(owner)
        proxy_id = (
            current.id
            if payload.get("target", "current") == "current" and current
            else payload.get("proxyId")
        )
        if not isinstance(proxy_id, str) or not proxy_id:
            raise ProxyNotFoundError("当前任务未绑定代理，请选择指定代理")
        proxy, connection, _ = self.remote._context(proxy_id)
        is_current = bool(
            current and self.usage.identity(current) == self.usage.identity(proxy)
        )
        if (
            is_current
            and current is not None
            and (
                current.http_endpoint != proxy.http_endpoint
                or current.socks5_endpoint != proxy.socks5_endpoint
                or self.usage.versions.get(owner, connection.secret_ref)
                != connection.secret_ref
            )
        ):
            raise RevisionConflictError("会话代理连接已变化，不能控制旧绑定")
        return proxy, connection, is_current

    async def _prepare(self, owner, token, payload):
        if token in self._prepared:
            if self._prepared[token]["configuration"] != self._configuration(payload):
                raise ValueError("Proxy execution configuration changed")
            return self._prepared[token]["initial"]
        proxy, connection, current = self._target(owner, payload)
        self.usage.claim(proxy, owner, token)
        state, _ = await self.remote.state(proxy.id)
        target = None
        if payload["action"] == "relocate":
            target = next(
                (
                    item
                    for item in await self.remote.locations(proxy.connection_id)
                    if item.id == payload.get("locationId")
                ),
                None,
            )
            if target is None:
                raise ProxyNotFoundError("目标地点不存在")
        before = observation(state)
        if not current:
            before.update(await self._probe(proxy.id))
            if not before.get("exitIp") or before.get("error"):
                raise ProxyError("无法取得有效的初始出口 IP")
        initial = {
            "proxyId": proxy.id,
            "current": current,
            "before": before,
            "targetLocation": asdict(target) if target else None,
            "alreadySatisfied": bool(target and matches(state, target)),
            "error": None,
        }
        self._prepared[token] = {
            "owner": owner,
            "proxyId": proxy.id,
            "secretRef": connection.secret_ref,
            "action": payload["action"],
            "initial": initial,
            "target": target,
            "configuration": self._configuration(payload),
            "operationId": None,
            "countedOperations": set(),
        }
        return initial

    @staticmethod
    def _configuration(payload):
        return {
            key: payload.get(key)
            for key in (
                "action",
                "target",
                "proxyId",
                "locationId",
                "maxAttempts",
                "retryIntervalSeconds",
                "confirmationTimeoutSeconds",
            )
        }

    async def _probe(self, proxy_id):
        proxy, _, _ = self.remote._context(proxy_id)
        value = await self.probe.probe(proxy)
        return {
            "exitIp": value.exit_ip,
            "observedAt": value.checked_at.isoformat() if value.checked_at else None,
            "source": "local_probe",
            "error": value.error,
        }

    async def _query(self, owner, payload):
        proxy, _, _ = self._target(owner, payload)
        operation_id = payload.get("operationId")
        operation = self.remote.operations.get(operation_id) if operation_id else None
        if operation is not None and operation.target_id != proxy.id:
            raise RevisionConflictError("操作不属于所选代理")
        if operation is not None and operation.status == "unknown":
            operation = self.remote.reconcile(
                operation.id,
                confirmation_seconds=float(payload["confirmationTimeoutSeconds"]),
            )
            task = self.remote._tasks.get(operation.id)
            if task is not None:
                await asyncio.shield(task)
            operation = self.remote.operations.get(operation.id)
        state, latest = await self.remote.state(proxy.id)
        operation = operation or latest
        return {
            "status": operation.status if operation else "succeeded",
            "proxyId": proxy.id,
            "operationId": operation.id if operation else None,
            "after": observation(state),
            "cooldown": {
                "reason": state.rotation_blocked_reason,
                "retryAfterSeconds": state.retry_after_seconds,
            },
            "error": self._operation_error(operation) if operation else None,
        }

    @staticmethod
    def _operation_error(operation):
        if not operation.error:
            return None
        if operation.error["code"] in {
            "PROXY_COMMAND_ERROR",
            "PROXYPANEL_SCHEMA_UNSUPPORTED",
        }:
            raise RuntimeError("代理服务协议异常")
        raw = operation.error
        return {
            "code": {
                "PROXYPANEL_RATE_LIMITED": "PROXY_RATE_LIMITED",
                "PROXYPANEL_OUTCOME_UNKNOWN": "PROXY_OUTCOME_UNKNOWN",
            }.get(raw["code"], raw["code"]),
            "message": raw["message"],
            "retryAfterSeconds": raw.get("retry_after_seconds"),
            "retryAllowed": raw["code"]
            not in {
                "PROXYPANEL_AUTH_FAILED",
                "PROXYPANEL_VALIDATION_ERROR",
                "RESOURCE_NOT_FOUND",
                "STALE_PROJECTION",
                "CAPABILITY_UNAVAILABLE",
            },
            "outcomeUnknown": operation.status == "unknown",
        }

    async def _attempt(self, owner, token, payload):
        prepared = self._prepared.get(token)
        if prepared is None or prepared["owner"] != owner:
            raise RevisionConflictError("代理节点执行已失效")
        if prepared["configuration"] != self._configuration(payload):
            raise ValueError("Proxy execution configuration changed")
        proxy, _, _ = self.remote._context(prepared["proxyId"], prepared["secretRef"])
        self.usage.check(proxy, owner)
        budget = float(payload["confirmationTimeoutSeconds"])
        operation = None
        existing_id = prepared.get("operationId")
        if existing_id:
            operation = self.remote.operations.get(existing_id)
            if operation.status == "unknown":
                operation = self.remote.reconcile(
                    existing_id, confirmation_seconds=budget, retry_if_ready=True
                )
            elif operation.status == "failed" or (
                operation.status == "succeeded"
                and prepared.get("reportedStatus") == "succeeded"
            ):
                operation = None
        if operation is None:
            state, _ = await self.remote.state(proxy.id)
            if prepared["action"] == "change_ip" and state.rotation_blocked_reason in {
                "cooldown",
                "busy",
            }:
                return {
                    "status": "failed",
                    "requestsSent": 0,
                    "error": {
                        "code": "PROXY_COOLDOWN"
                        if state.rotation_blocked_reason == "cooldown"
                        else "PROXY_BUSY",
                        "message": "代理处于冷却期"
                        if state.rotation_blocked_reason == "cooldown"
                        else "代理正在切换",
                        "retryAfterSeconds": state.retry_after_seconds,
                        "retryAllowed": True,
                        "outcomeUnknown": False,
                    },
                }
            key = str(
                uuid5(NAMESPACE_URL, f"autoflow:proxy:{token}:{payload['attempt']}")
            )
            operation = self.remote.operations.find_key(key)
            if operation is None:
                if not payload.get("_alive", lambda: True)():
                    raise asyncio.CancelledError
                remaining = payload["_deadline"] - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError
                operation = self.remote.submit(
                    proxy.id,
                    prepared["action"],
                    {"location_id": prepared["target"].id}
                    if prepared["target"]
                    else {},
                    proxy.revision,
                    key,
                    confirmation_seconds=remaining,
                    retry_if_ready=True,
                    owner=owner,
                    is_active=lambda: (
                        self._prepared.get(token) is prepared
                        and asyncio.get_running_loop().time() < payload["_deadline"]
                        and payload.get("_alive", lambda: True)()
                    ),
                )
            prepared["operationId"] = operation.id
        task = self.remote._tasks.get(operation.id)
        if task is not None:
            await asyncio.shield(task)
        operation = self.remote.operations.get(operation.id)
        result = {
            "status": operation.status,
            "operationId": operation.id,
            "requestsSent": 0,
            "error": self._operation_error(operation),
        }
        if operation.status == "succeeded":
            state, _ = await self.remote.state(proxy.id)
            result["after"] = observation(state)
            if not prepared["initial"]["current"]:
                result["after"].update(await self._probe(proxy.id))
        result["requestsSent"] = self._count_request(prepared, operation)
        prepared["reportedStatus"] = operation.status
        return result

    @staticmethod
    def _count_request(prepared, operation):
        if operation is None or not operation.before.get("write_started"):
            return 0
        counted = prepared.setdefault("countedOperations", set())
        if operation.id in counted:
            return 0
        counted.add(operation.id)
        return 1
