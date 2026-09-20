from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from autoflow.application.workflows.executors.network_monitor import (
    NetworkMonitorStartExecutor,
    NetworkMonitorStopExecutor,
    NetworkMonitorWaitExecutor,
)
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import CloakBrowserWorkflowSession

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_network_monitor_harness.py")


def _source_result(operation: str) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(FROZEN_HARNESS)],
        input=json.dumps({"operation": operation}),
        text=True, encoding="utf-8",
        capture_output=True,
        check=True,
        env=environment,
    )
    return json.loads(completed.stdout.splitlines()[-1])


def _without_timestamps(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_timestamps(item)
            for key, item in value.items()
            if key != "timestamp"
        }
    if isinstance(value, list):
        return [_without_timestamps(item) for item in value]
    return value


class _RawPage:
    def __init__(self) -> None:
        self.url = "https://local.test"
        self.listeners: dict[str, list[Any]] = {}

    def is_closed(self) -> bool:
        return False

    def on(self, name: str, listener: Any) -> None:
        self.listeners.setdefault(name, []).append(listener)

    def remove_listener(self, name: str, listener: Any) -> None:
        self.listeners.get(name, []).remove(listener)

    def emit_request(self, url: str, resource_type: str = "fetch") -> None:
        request = SimpleNamespace(
            url=url,
            method="GET",
            resource_type=resource_type,
            headers={"accept": "application/json"},
        )
        for listener in list(self.listeners.get("request", [])):
            listener(request)


class _RawContext:
    def __init__(self) -> None:
        self.pages = [_RawPage()]


def _context() -> tuple[ExecutionContext, _RawPage]:
    raw = _RawContext()
    return (
        ExecutionContext(browser=CloakBrowserWorkflowSession.from_context(raw)),
        raw.pages[0],
    )


def test_network_monitor_start_wait_and_stop_preserve_frozen_contract() -> None:
    async def scenario() -> tuple[Any, Any, Any, ExecutionContext]:
        context, page = _context()
        started = await NetworkMonitorStartExecutor().execute(
            {"monitorId": "orders", "filterType": "api", "urlPattern": "/api/"},
            context,
        )
        page.emit_request("https://local.test/api/orders")
        page.emit_request("https://local.test/logo.png", "image")
        waited = await NetworkMonitorWaitExecutor().execute(
            {
                "monitorId": "orders",
                "urlPattern": "orders",
                "timeout": 1,
                "captureMode": "first",
                "variableName": "request",
            },
            context,
        )
        stopped = await NetworkMonitorStopExecutor().execute(
            {"monitorId": "orders", "variableName": "allRequests"}, context
        )
        return started, waited, stopped, context

    started, waited, stopped, context = asyncio.run(scenario())

    assert started.success is True
    assert started.message == (
        "网络监听已启动（ID: orders，类型=api，URL包含='/api/'），"
        "将持续捕获请求直到停止"
    )
    assert waited.success is True
    assert waited.data["count"] == 1
    assert waited.data["requests"][0]["url"] == "https://local.test/api/orders"
    assert context.variables["request"]["url"] == "https://local.test/api/orders"
    assert stopped.success is True
    assert stopped.data["count"] == 1
    assert context.variables["allRequests"][0]["url"] == (
        "https://local.test/api/orders"
    )
    assert context.network_monitors == {}

    target = {
        "started": {
            "success": started.success,
            "message": started.message,
            "error": started.error,
            "data": started.data,
        },
        "waited": {
            "success": waited.success,
            "message": waited.message,
            "error": waited.error,
            "data": waited.data,
        },
        "stopped": {
            "success": stopped.success,
            "message": stopped.message,
            "error": stopped.error,
            "data": stopped.data,
        },
        "variables": context.variables,
    }
    assert _without_timestamps(target) == _source_result("chain")


def test_network_monitor_errors_match_frozen_messages() -> None:
    async def scenario() -> tuple[Any, Any, Any]:
        context, _ = _context()
        empty = await NetworkMonitorStartExecutor().execute(
            {"monitorId": ""}, context
        )
        missing_pattern = await NetworkMonitorWaitExecutor().execute(
            {"monitorId": "default", "urlPattern": ""}, context
        )
        missing_monitor = await NetworkMonitorStopExecutor().execute(
            {"monitorId": "missing"}, context
        )
        return empty, missing_pattern, missing_monitor

    empty, missing_pattern, missing_monitor = asyncio.run(scenario())
    assert empty.error == "监听器ID不能为空"
    assert missing_pattern.error == "URL匹配模式不能为空"
    assert missing_monitor.error == "监听器 'missing' 不存在"
    assert {
        "start": {
            "success": empty.success,
            "message": empty.message,
            "error": empty.error,
            "data": empty.data,
        },
        "wait": {
            "success": missing_pattern.success,
            "message": missing_pattern.message,
            "error": missing_pattern.error,
            "data": missing_pattern.data,
        },
        "stop": {
            "success": missing_monitor.success,
            "message": missing_monitor.message,
            "error": missing_monitor.error,
            "data": missing_monitor.data,
        },
    } == _source_result("errors")


def test_network_monitor_replacing_id_stops_old_listener() -> None:
    async def scenario() -> tuple[_RawPage, ExecutionContext, Any]:
        context, page = _context()
        executor = NetworkMonitorStartExecutor()
        await executor.execute({"monitorId": "same"}, context)
        old = context.network_monitors["same"]
        replaced = await executor.execute({"monitorId": "same"}, context)
        assert old.active is False
        return page, context, replaced

    page, context, replaced = asyncio.run(scenario())
    assert replaced.success is True
    assert len(page.listeners["request"]) == 1
    assert context.network_monitors["same"].active is True


def test_network_monitor_wait_can_stop_after_first_capture() -> None:
    async def scenario() -> tuple[Any, ExecutionContext]:
        context, page = _context()
        await NetworkMonitorStartExecutor().execute({"monitorId": "once"}, context)
        page.emit_request("https://local.test/ready")
        result = await NetworkMonitorWaitExecutor().execute(
            {
                "monitorId": "once",
                "urlPattern": "ready",
                "timeout": 1,
                "stopAfterCapture": True,
            },
            context,
        )
        return result, context

    result, context = asyncio.run(scenario())
    assert result.success is True
    assert result.data["stopped"] is True
    assert "once" not in context.network_monitors


def test_network_monitor_wait_propagates_workflow_cancellation() -> None:
    class Cancelled:
        def raise_if_cancelled(self) -> None:
            raise asyncio.CancelledError

    async def scenario() -> None:
        context, page = _context()
        context.cancellation = Cancelled()  # type: ignore[assignment]
        await NetworkMonitorStartExecutor().execute({"monitorId": "cancel"}, context)
        try:
            await NetworkMonitorWaitExecutor().execute(
                {"monitorId": "cancel", "urlPattern": "never", "timeout": 60},
                context,
            )
        except asyncio.CancelledError:
            assert context.network_monitors == {}
            assert page.listeners["request"] == []
            raise

    try:
        asyncio.run(scenario())
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("network monitor wait must propagate cancellation")


def test_network_monitor_wait_releases_an_overflowed_monitor() -> None:
    async def scenario() -> tuple[Any, ExecutionContext]:
        context, _ = _context()
        await NetworkMonitorStartExecutor().execute(
            {"monitorId": "bounded"}, context
        )
        monitor = context.network_monitors["bounded"]
        monitor._overflowed = True  # type: ignore[attr-defined]
        result = await NetworkMonitorWaitExecutor().execute(
            {
                "monitorId": "bounded",
                "urlPattern": "never",
                "timeout": 60,
            },
            context,
        )
        return result, context

    result, context = asyncio.run(scenario())
    assert result.success is False
    assert result.error == "网络监听数据超过工作流安全限制"
    assert context.network_monitors == {}
