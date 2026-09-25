"""Proxy nodes: freeze inputs once, validate observed outcomes, retry finitely."""

from __future__ import annotations

import asyncio
import math
from time import time
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult

_sleep = asyncio.sleep


def _number(
    value: Any, context: ExecutionContext, *, integer: bool = False
) -> float | int:
    value = context.resolve_value(value)
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise TypeError("时间必须为正数，最大尝试次数必须为正整数")
    number = float(value)
    if not math.isfinite(number) or number <= 0 or integer and not number.is_integer():
        raise ValueError("时间必须为正数，最大尝试次数必须为正整数")
    return int(number) if integer else number


def _text(value: Any, context: ExecutionContext) -> str:
    value = context.resolve_value(value)
    if not isinstance(value, str) or not value.strip() or "${" in value or "{" in value:
        raise ValueError("代理参数未解析或为空")
    return value.strip()


def _error(
    code: str, message: str, *, retry: bool = False, unknown: bool = False
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryAllowed": retry,
        "retryAfterSeconds": None,
        "outcomeUnknown": unknown,
    }


class ProxyControlExecutor(ModuleExecutor):
    action = "query"

    @property
    def module_type(self) -> str:
        return {
            "query": "proxy_query",
            "change_ip": "proxy_change_ip",
            "relocate": "proxy_change_location",
        }[self.action]

    def requires_browser_for(self, config: dict[str, Any]) -> bool:
        return config.get("target", "current") == "current"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        variable = config.get("resultVariable") or self.module_type + "_result"
        output: dict[str, Any] = {
            "status": "failed",
            "action": self.action,
            "proxyId": None,
            "operationId": None,
            "attemptsUsed": 0,
            "requestsSent": 0,
            "configuration": {},
            "before": None,
            "after": None,
            "targetLocation": None,
            "changed": False,
            "error": None,
        }
        if not isinstance(variable, str) or not variable.strip():
            return ModuleResult(False, error="代理结果变量名称无效")
        context.set_variable(variable, output.copy())
        captured = config.get("failureMode", "raise") == "capture"
        prepared = False
        gateway = context.proxy_control
        probe = context.proxy_probe or getattr(context.browser, "probe_proxy", None)
        # Capture node identity before the first await; parallel branches have their own visits.
        node_id, visit_id = context.proxy_visit.get()
        identity = {
            "nodeId": node_id or context.current_node_id,
            "executionId": visit_id or context.current_execution_id,
        }
        settings: dict[str, Any] = {}
        try:
            target = config.get("target", "current")
            if target not in {"current", "specified"} or config.get(
                "failureMode", "raise"
            ) not in {"raise", "capture"}:
                raise ValueError("代理目标或失败处理方式无效")
            settings = {
                "target": target,
                "proxyId": _text(config.get("proxyId"), context)
                if target == "specified"
                else None,
                "retryIntervalSeconds": _number(
                    config.get("retryIntervalSeconds", 10), context
                ),
                "maxAttempts": _number(
                    config.get("maxAttempts", 5), context, integer=True
                ),
                "confirmationTimeoutSeconds": _number(
                    config.get("confirmationTimeoutSeconds", 30), context
                ),
                "locationId": _text(config.get("locationId"), context)
                if self.action == "relocate"
                else None,
                "operationId": _text(config["operationId"], context)
                if config.get("operationId")
                else None,
            }
        except (ValueError, TypeError, OverflowError):
            output["error"] = _error(
                "VALIDATION_ERROR", "代理配置无效：检查变量、目标和正数时间／正整数次数"
            )
        else:
            if self.action != "query" and context.proxy_activity:
                output["error"] = _error(
                    "PROXY_BUSY", "同一浏览器有并行操作", retry=True
                )
            elif gateway is None:
                output["error"] = _error(
                    "PROXY_CONTROL_UNAVAILABLE", "当前执行环境未接入代理控制"
                )
            else:

                async def call(method: str, **values: Any) -> dict[str, Any]:
                    if context.cancellation is not None:
                        context.cancellation.raise_if_cancelled()
                    return await gateway(
                        {
                            **identity,
                            **settings,
                            "action": self.action,
                            "method": method,
                            **values,
                        }
                    )

                if self.action != "query":
                    context.proxy_activity.add("proxy-switch")
                try:
                    output["configuration"] = dict(settings)
                    if self.action == "query":
                        output.update(await call("query"))
                    else:
                        initial = await call("prepare")
                        output.update(initial)
                        prepared = not bool(initial.get("error"))
                        if prepared:
                            if initial.get("current"):
                                if probe is None:
                                    raise RuntimeError("当前代理缺少会话出口探测能力")
                                output["before"] = {
                                    **(output.get("before") or {}),
                                    **await probe(False),
                                }
                            if not (output.get("before") or {}).get("exitIp") or (
                                output.get("before") or {}
                            ).get("error"):
                                output["error"] = _error(
                                    "PROXY_PROBE_FAILED", "无法取得有效的初始出口 IP"
                                )
                            elif initial.get("alreadySatisfied"):
                                output.update(
                                    status="succeeded",
                                    changed=False,
                                    after=output["before"],
                                )
                            else:
                                await self._attempts(
                                    context, call, output, initial, settings, probe
                                )
                finally:
                    if self.action != "query":
                        context.proxy_activity.discard("proxy-switch")
                    if prepared:
                        # The host also releases on confirmed worker cleanup if this pipe is lost.
                        await gateway({**identity, "method": "finish"})
        if self.action != "query" and output["status"] in {"queued", "running"}:
            output["status"] = "unknown"
        success = output["status"] in {"succeeded", "queued", "running"}
        if not success and self.action != "query":
            error = output.get("error") or _error(
                "PROXY_OUTCOME_UNKNOWN", "操作结果尚未确认", unknown=True
            )
            output["error"] = {
                **error,
                "lastCode": error["code"],
                "code": "PROXY_IP_SWITCH_FAILED"
                if self.action == "change_ip"
                else "PROXY_LOCATION_SWITCH_FAILED",
            }
        context.set_variable(variable, output)
        return ModuleResult(
            success=success or captured,
            message="代理操作完成"
            if success
            else "操作失败，结果已捕获"
            if captured
            else "",
            error=None if success or captured else str(output["error"]["code"]),
            data=output,
            log_level="warning" if not success and captured else None,
        )

    async def _attempts(self, context, call, output, initial, settings, probe):
        pending = None
        for attempt in range(1, settings["maxAttempts"] + 1):
            round_started = asyncio.get_running_loop().time()
            value = await call("attempt", attempt=attempt, operationId=pending)
            output["attemptsUsed"] = attempt
            output["requestsSent"] += value.pop("requestsSent", 0)
            output.update(value)
            if value["status"] == "succeeded":
                if initial.get("current"):
                    remaining = max(
                        0,
                        settings["confirmationTimeoutSeconds"]
                        - (asyncio.get_running_loop().time() - round_started),
                    )
                    try:
                        async with asyncio.timeout(remaining):
                            observed = await probe(True)
                    except TimeoutError:
                        observed = {"exitIp": None, "error": "PROXY_PROBE_TIMEOUT"}
                    output["after"] = {**(output.get("after") or {}), **observed}
                before, after = output.get("before") or {}, output.get("after") or {}
                if not after.get("exitIp") or after.get("error"):
                    output.update(
                        status="failed",
                        error=_error(
                            "PROXY_PROBE_FAILED", "新出口验证失败", retry=True
                        ),
                    )
                elif self.action == "change_ip" and after["exitIp"] == before.get(
                    "exitIp"
                ):
                    output.update(
                        status="failed",
                        error=_error(
                            "PROXY_IP_UNCHANGED", "出口 IP 仍与初始 IP 相同", retry=True
                        ),
                    )
                else:
                    output.update(status="succeeded", changed=True, error=None)
                    return
            pending = (
                output.get("operationId")
                if value["status"] in {"unknown", "queued", "running"}
                else None
            )
            error = output.get("error") or _error(
                "PROXY_OUTCOME_UNKNOWN", "操作结果尚未确认", retry=True, unknown=True
            )
            output["error"] = error
            if context.events is not None:
                node_id, visit_id = context.proxy_visit.get()
                await context.events.publish(
                    {
                        "type": "execution:log",
                        "level": "info",
                        "isSystemLog": True,
                        "details": {
                            "proxyRetryAt": (time() + settings["retryIntervalSeconds"])
                            * 1000
                        }
                        if attempt < settings["maxAttempts"]
                        and error.get("retryAllowed", True)
                        else {},
                        "nodeId": node_id or context.current_node_id,
                        "executionId": visit_id or context.current_execution_id,
                        "message": f"代理切换第 {attempt}/{settings['maxAttempts']} 轮：{error['message']}"
                        + (
                            f"；{settings['retryIntervalSeconds']} 秒后重试"
                            if attempt < settings["maxAttempts"]
                            and error.get("retryAllowed", True)
                            else ""
                        ),
                    }
                )
            if (
                not error.get("retryAllowed", True)
                or attempt == settings["maxAttempts"]
            ):
                return
            await _sleep(settings["retryIntervalSeconds"])


class ProxyChangeIPExecutor(ProxyControlExecutor):
    action = "change_ip"


class ProxyChangeLocationExecutor(ProxyControlExecutor):
    action = "relocate"


class ProxyQueryExecutor(ProxyControlExecutor):
    action = "query"


PROXY_EXECUTORS = (
    ProxyChangeIPExecutor,
    ProxyChangeLocationExecutor,
    ProxyQueryExecutor,
)
