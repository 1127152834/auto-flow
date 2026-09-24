from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.models import ModelInvocationResult
from autoflow.domain.workflows.execution import ExecutionContext


class Models:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    async def invoke(
        self, model_id: str, payload: Mapping[str, Any]
    ) -> ModelInvocationResult:
        self.calls.append((model_id, payload))
        return ModelInvocationResult(
            "fixture", self.responses.pop(0), "", {}, "fixture://model"
        )


class Page:
    def __init__(self, url: str, html: str) -> None:
        self.id = url
        self.url = url
        self.html = html
        self.goto_calls: list[str] = []
        self.closed = False

    async def goto(self, url: str, *, wait_until: str, timeout_ms: float) -> None:
        self.goto_calls.append(url)
        self.url = url

    async def content(self) -> str:
        return self.html

    async def close(self) -> None:
        self.closed = True


class Browser:
    def __init__(self) -> None:
        self.current = Page("https://example.test/current", "<html>current</html>")
        self.created: list[Page] = []

    def current_page(self) -> Page:
        return self.current

    async def new_page(self) -> Page:
        page = Page("about:blank", "<html><button id='login'>登录</button></html>")
        self.created.append(page)
        self.current = page
        return page

    def select_page(self, page_id: str) -> Page:
        assert page_id == "https://example.test/current"
        self.current = Page("https://example.test/current", "<html>current</html>")
        return self.current


@pytest.mark.asyncio
async def test_ai_smart_scraper_uses_current_cloakbrowser_html_and_managed_model():
    browser = Browser()
    models = Models(['{"items":["一","二"]}'])
    context = ExecutionContext(browser=browser, models=models)
    executor = build_production_executor_registry().get("ai_smart_scraper")

    result = await executor.execute(
        {
            "modelId": "model-1",
            "url": "https://example.test/current",
            "prompt": "提取列表",
            "variableName": "items",
            "waitTime": 0,
        },
        context,
    )

    assert result.success is True
    assert context.variables["items"] == {"items": ["一", "二"]}
    assert browser.created == []
    assert models.calls[0][0] == "model-1"
    assert "<html>current</html>" in models.calls[0][1]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_ai_element_selector_uses_temporary_cloakbrowser_page_and_closes_it():
    browser = Browser()
    models = Models(['{"selector":"#login","description":"登录按钮","confidence":96}'])
    context = ExecutionContext(browser=browser, models=models)
    executor = build_production_executor_registry().get("ai_element_selector")

    result = await executor.execute(
        {
            "modelId": "model-1",
            "url": "https://example.test/login",
            "elementDescription": "登录按钮",
            "variableName": "selector",
            "waitTime": 0,
        },
        context,
    )

    assert result.success is True
    assert result.data == "#login"
    assert context.variables["selector"] == "#login"
    assert browser.created[0].goto_calls == ["https://example.test/login"]
    assert browser.created[0].closed is True
    assert browser.current.url == "https://example.test/current"


@pytest.mark.parametrize("module_type", ["ai_smart_scraper", "ai_element_selector"])
def test_ai_scraper_family_is_registered_and_requires_managed_model(module_type: str):
    executor = build_production_executor_registry().get(module_type)

    assert executor.requires_browser_for({}) is True
    assert executor.validate_config(
        {"apiUrl": "https://legacy.invalid", "apiKey": "secret"}
    ) == (False, "请选择主应用中的模型")
