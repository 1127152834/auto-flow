from __future__ import annotations

import asyncio
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import CloakBrowserWorkflowSession

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_network_capture_harness.py")


def _executor() -> Any:
    try:
        module = importlib.import_module(
            "autoflow.application.workflows.executors.network_capture"
        )
    except ModuleNotFoundError:
        pytest.fail("NetworkCaptureExecutor has not been migrated")
    return module.NetworkCaptureExecutor()


def _source_result(payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(FROZEN_HARNESS)],
        input=json.dumps(payload),
        text=True, encoding="utf-8",
        capture_output=True,
        check=True,
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout.splitlines()[-1])


class _RawPage:
    def __init__(self, requests: list[dict[str, str]] | None = None) -> None:
        self.url = "https://local.test"
        self._requests = requests or []
        self.listeners: dict[str, list[Any]] = {}

    def is_closed(self) -> bool:
        return False

    def on(self, name: str, listener: Any) -> None:
        self.listeners.setdefault(name, []).append(listener)
        if name == "request":
            for request in self._requests:
                listener(SimpleNamespace(headers={}, method="GET", **request))

    def remove_listener(self, name: str, listener: Any) -> None:
        self.listeners.get(name, []).remove(listener)


class _RawContext:
    def __init__(self, page: _RawPage) -> None:
        self.pages = [page]


def _context(
    requests: list[dict[str, str]] | None = None,
) -> tuple[ExecutionContext, _RawPage]:
    page = _RawPage(requests)
    raw = _RawContext(page)
    return (
        ExecutionContext(browser=CloakBrowserWorkflowSession.from_context(raw)),
        page,
    )


def _result_payload(result: Any) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
    }


def _target_result(payload: dict[str, Any]) -> dict[str, Any]:
    async def scenario() -> dict[str, Any]:
        context, page = _context(payload.get("requests", []))
        if not payload.get("page", True):
            context.browser = None
        result = await _executor().execute(payload["config"], context)
        return {
            "result": _result_payload(result),
            "variables": context.variables,
            "listener_count": len(page.listeners.get("request", [])),
        }

    return asyncio.run(scenario())


def test_network_capture_defaults_match_frozen_browser_contract() -> None:
    payload = {
        "config": {"variableName": "captured", "captureDuration": 0},
        "requests": [
            {
                "url": "https://local.test/api/items",
                "resource_type": "fetch",
            },
            {
                "url": "https://local.test/api/items",
                "resource_type": "fetch",
            },
            {
                "url": "https://local.test/logo.png",
                "resource_type": "image",
            },
        ],
    }

    target = _target_result(payload)

    assert target == _source_result(payload)
    assert target["variables"] == {
        "captured": [
            "https://local.test/api/items",
            "https://local.test/logo.png",
        ]
    }
    assert target["listener_count"] == 0


@pytest.mark.parametrize(
    ("filter_type", "expected_url"),
    [
        ("img", "https://local.test/assets/Logo.png"),
        ("media", "https://local.test/assets/Logo.mp4"),
    ],
)
def test_network_capture_browser_filters_match_frozen_contract(
    filter_type: str, expected_url: str
) -> None:
    payload = {
        "config": {
            "captureMode": "browser",
            "filterType": filter_type,
            "searchKeyword": "logo",
            "captureDuration": 0,
            "variableName": "matches",
        },
        "requests": [
            {
                "url": "https://local.test/assets/logo.json",
                "resource_type": "fetch",
            },
            {
                "url": "https://local.test/assets/banner.png",
                "resource_type": "image",
            },
            {
                "url": expected_url,
                "resource_type": "image" if filter_type == "img" else "media",
            },
            {
                "url": expected_url,
                "resource_type": "image" if filter_type == "img" else "media",
            },
        ],
    }

    target = _target_result(payload)

    assert target == _source_result(payload)
    assert target["variables"] == {"matches": [expected_url]}


@pytest.mark.parametrize(
    "payload",
    [
        {"config": {"captureDuration": 0}},
        {
            "config": {"variableName": "captured", "captureDuration": 0},
            "page": False,
        },
    ],
)
def test_network_capture_validation_errors_match_frozen_contract(
    payload: dict[str, Any],
) -> None:
    assert _target_result(payload) == _source_result(payload)


@pytest.mark.parametrize("capture_mode", ["system", "proxy"])
def test_network_capture_rejects_modes_outside_approved_web_scope(
    capture_mode: str,
) -> None:
    context = ExecutionContext()

    result = asyncio.run(
        _executor().execute(
            {"captureMode": capture_mode, "variableName": "captured"}, context
        )
    )

    assert result.success is False
    assert result.error == (
        "CapabilityUnavailable: 当前 AutoFlow Web 自动化范围"
        f"不支持 {capture_mode} 抓包模式"
    )
    assert context.variables == {}


def test_network_capture_cancellation_stops_request_watch() -> None:
    class Cancelled:
        @property
        def cancelled(self) -> bool:
            return True

        def raise_if_cancelled(self) -> None:
            raise asyncio.CancelledError

    async def scenario() -> tuple[ExecutionContext, _RawPage]:
        context, page = _context()
        context.cancellation = Cancelled()
        try:
            await _executor().execute(
                {
                    "captureMode": "browser",
                    "captureDuration": 60,
                    "variableName": "captured",
                },
                context,
            )
        except asyncio.CancelledError:
            return context, page
        raise AssertionError("network capture must propagate cancellation")

    context, page = asyncio.run(scenario())
    assert context.variables == {}
    assert page.listeners["request"] == []


def test_network_capture_reports_provider_errors_without_writing_variable() -> None:
    page = SimpleNamespace(
        begin_request_watch=lambda **_options: (_ for _ in ()).throw(
            RuntimeError("watch unavailable")
        )
    )
    browser = SimpleNamespace(current_page=lambda: page)
    context = ExecutionContext(browser=browser)

    result = asyncio.run(
        _executor().execute({"captureDuration": 0, "variableName": "captured"}, context)
    )

    assert result.success is False
    assert result.error == "网络抓包启动失败: watch unavailable"
    assert context.variables == {}


def test_network_capture_stops_overflowed_watch_without_writing_variable() -> None:
    class OverflowedWatch:
        active = True
        overflowed = True
        stopped = False

        def captured_requests(self) -> list[dict[str, Any]]:
            return []

        def matching_requests(self, url_pattern: str) -> list[dict[str, Any]]:
            return []

        def stop(self) -> None:
            self.stopped = True

    watch = OverflowedWatch()
    page = SimpleNamespace(begin_request_watch=lambda **_options: watch)
    browser = SimpleNamespace(current_page=lambda: page)
    context = ExecutionContext(browser=browser)

    result = asyncio.run(
        _executor().execute({"captureDuration": 0, "variableName": "captured"}, context)
    )

    assert result.success is False
    assert result.error == "网络抓包数据超过工作流安全限制"
    assert watch.stopped is True
    assert context.variables == {}
