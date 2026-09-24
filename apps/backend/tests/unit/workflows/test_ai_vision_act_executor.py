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
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    async def invoke(
        self, model_id: str, payload: Mapping[str, Any]
    ) -> ModelInvocationResult:
        self.calls.append((model_id, payload))
        return ModelInvocationResult("vision", self.response, "", {}, "fixture://model")


class Mouse:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    async def move(self, x: float, y: float, **options: Any) -> None:
        self.calls.append(("move", x, y, options))

    async def click(
        self, x: float, y: float, *, button: str, click_count: int
    ) -> None:
        self.calls.append(("click", x, y, button, click_count))


class Page:
    def __init__(self) -> None:
        self.viewport_size = {"width": 1200, "height": 800}
        self.mouse = Mouse()

    async def screenshot(self, *, full_page: bool = False) -> bytes:
        assert full_page is False
        return b"PAGE"


class Browser:
    def __init__(self) -> None:
        self.page = Page()

    def current_page(self) -> Page:
        return self.page


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "button", "expected"),
    [
        ("locate", "left", []),
        ("move", "left", [("move", 600, 200, {})]),
        ("click", "middle", [("click", 600, 200, "middle", 1)]),
        ("double", "left", [("click", 600, 200, "left", 2)]),
        ("right", "left", [("click", 600, 200, "right", 1)]),
    ],
)
async def test_ai_vision_act_uses_cloakbrowser_page_coordinates(
    action: str, button: str, expected: list[tuple[Any, ...]]
) -> None:
    browser = Browser()
    models = Models('{"found":true,"x":500,"y":250}')
    context = ExecutionContext(browser=browser, models=models)
    executor = build_production_executor_registry().get("ai_vision_act")

    result = await executor.execute(
        {
            "modelId": "model-1",
            "instruction": "登录按钮",
            "action": action,
            "button": button,
            "variableName": "point",
        },
        context,
    )

    assert result.success is True
    assert result.data == {"x": 600, "y": 200}
    assert context.variables["point"] == {"found": True, "x": 600, "y": 200}
    assert browser.page.mouse.calls == expected
    messages = models.calls[0][1]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["content"][0]["image_url"]["url"].endswith("UEFHRQ==")


def test_ai_vision_act_is_registered_and_rejects_legacy_model_fields() -> None:
    executor = build_production_executor_registry().get("ai_vision_act")

    assert executor.requires_browser_for({}) is True
    assert executor.validate_config(
        {"apiUrl": "https://legacy.invalid", "model": "vision", "instruction": "按钮"}
    ) == (False, "请选择主应用中的模型")
