from __future__ import annotations

from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


class Locator:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    @property
    def first(self) -> Locator:
        return self

    async def wait_for(self, **_options: Any) -> None:
        if self.error:
            raise self.error


class Page:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.expression = ""
        self.wait_error: Exception | None = None

    def locator(self, _selector: str) -> Locator:
        return Locator(self.wait_error)

    async def evaluate(self, expression: str) -> Any:
        self.expression = expression
        if self.error:
            raise self.error
        return self.result


class Browser:
    def __init__(self, page: Page) -> None:
        self.page = page

    def active_page(self) -> Page:
        return self.page


@pytest.mark.asyncio
async def test_element_change_trigger_maps_child_mutation_and_variables() -> None:
    observer = {
        "success": True,
        "changes": [{"type": "childList", "addedCount": 1, "removedCount": 0}],
        "addedNodes": [
            {"tagName": "li", "className": "item", "id": "new", "textContent": "新增"}
        ],
        "removedNodes": [],
        "newElementSelector": "#new",
        "newElementText": "新增",
        "currentChildCount": 2,
        "initialChildCount": 1,
        "mutationCount": 1,
    }
    page = Page(observer)
    context = ExecutionContext(browser=Browser(page))  # type: ignore[arg-type]
    executor = build_production_executor_registry().get("element_change_trigger")

    assert executor is not None
    result = await executor.execute(
        {
            "selector": "#list",
            "observeType": "childList",
            "timeout": 5,
            "saveNewElementSelector": "new_selector",
            "saveChangeInfo": "change",
        },
        context,
    )

    assert result.success is True
    assert result.message == "子元素变化触发器已触发: 新增1个元素"
    assert context.variables["new_selector"] == "#new"
    assert context.variables["change"]["previousCount"] == 1
    assert result.data["newElementText"] == "新增"
    assert '"selector": "#list"' in page.expression
    assert '"observeType": "childList"' in page.expression


@pytest.mark.asyncio
async def test_element_change_trigger_reports_missing_target_and_timeout() -> None:
    executor = build_production_executor_registry().get("element_change_trigger")
    assert executor is not None
    missing = await executor.execute({}, ExecutionContext())
    assert missing.error == "元素选择器不能为空"

    page = Page()
    page.wait_error = RuntimeError("missing")
    not_found = await executor.execute(
        {"selector": "#missing"},
        ExecutionContext(browser=Browser(page)),  # type: ignore[arg-type]
    )
    assert not_found.error == "未找到元素: #missing"

    timeout_page = Page(error=RuntimeError("监控超时（2秒）"))
    timed_out = await executor.execute(
        {"selector": "#list", "timeout": 2},
        ExecutionContext(browser=Browser(timeout_page)),  # type: ignore[arg-type]
    )
    assert timed_out.error == "子元素变化触发器超时（2秒）"
