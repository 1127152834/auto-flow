"""Remediation M1 R1-15: the web press_key node."""

from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.executors.web_basic import PressKeyExecutor
from autoflow.domain.workflows.execution import ExecutionContext


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page, self.selector = page, selector

    async def wait_for(self, **options: Any) -> None:
        if self.selector == "#missing":
            raise TimeoutError("waiting for #missing")
        self.page.calls.append(("wait", self.selector, options["state"]))

    async def press(self, key: str, *, timeout_ms: float | None = None) -> None:
        self.page.calls.append(("press", self.selector, key, timeout_ms))


class FakePage:
    id = "page-1"
    url = "about:blank"
    closed = False

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    async def keyboard_press(self, key: str) -> None:
        self.calls.append(("keyboard", key))


class FakeSession:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    def active_page(self) -> FakePage:
        return self.page


def _context(page: FakePage) -> ExecutionContext:
    return ExecutionContext(browser=FakeSession(page))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_element_mode_waits_for_the_element_then_presses_on_it():
    page = FakePage()
    result = await PressKeyExecutor().execute(
        {"key": "Enter", "targetType": "element", "selector": "#name", "timeout": 5},
        _context(page),
    )
    assert result.success, result.error
    assert page.calls == [("wait", "#name", "visible"), ("press", "#name", "Enter", 5000)]


@pytest.mark.asyncio
async def test_focused_mode_presses_on_the_page_and_supports_combinations():
    page = FakePage()
    result = await PressKeyExecutor().execute({"key": "Control+A"}, _context(page))
    assert result.success
    assert page.calls == [("keyboard", "Control+A")]


@pytest.mark.asyncio
async def test_timeout_zero_means_no_limit():
    page = FakePage()
    result = await PressKeyExecutor().execute(
        {"key": "Enter", "targetType": "element", "selector": "#name", "timeout": 0},
        _context(page),
    )
    assert result.success, result.error
    assert page.calls[-1] == ("press", "#name", "Enter", None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "reason"),
    [
        ({"key": ""}, "按键不能为空"),
        ({"key": "Enter", "targetType": "element"}, "元素模式需要选择器"),
        ({"key": "Enter", "targetType": "window"}, "不支持的按键目标"),
        (
            {"key": "Enter", "targetType": "element", "selector": "#missing"},
            "waiting for #missing",
        ),
    ],
)
async def test_invalid_or_failing_presses_report_the_reason(config, reason):
    result = await PressKeyExecutor().execute(config, _context(FakePage()))
    assert not result.success
    assert reason in (result.error or "")


def test_press_key_is_a_production_web_node():
    registry = build_production_executor_registry()
    assert "press_key" in registry.get_all_types()
    assert PressKeyExecutor().requires_browser
