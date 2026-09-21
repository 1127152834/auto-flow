from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import DesktopActionResult, ExecutionContext


class DesktopActions:
    def __init__(self, result: DesktopActionResult | None = None) -> None:
        self.result = result or DesktopActionResult(True)
        self.requests: list[tuple[str, Mapping[str, Any], float]] = []

    async def perform(
        self,
        action: str,
        payload: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> DesktopActionResult:
        self.requests.append((action, payload, timeout_seconds))
        return self.result


@pytest.mark.asyncio
async def test_clipboard_nodes_use_platform_bridge_and_protect_values() -> None:
    registry = build_production_executor_registry()
    actions = DesktopActions()
    context = ExecutionContext(variables={"text": "你好"}, desktop_actions=actions)

    written = await registry.get("set_clipboard").execute(
        {"contentType": "text", "textContent": "{text}"}, context
    )
    assert written.success is True
    assert actions.requests == [("clipboard_write_text", {"text": "你好"}, 60)]

    context.desktop_actions = DesktopActions(DesktopActionResult(True, "复制内容"))
    read = await registry.get("get_clipboard").execute(
        {"variableName": "clipboard"}, context
    )
    assert read.success is True
    assert context.variables["clipboard"] == "复制内容"
    assert "clipboard" in context.sensitive_variables
    assert context.node_uses_sensitive_values is True


@pytest.mark.asyncio
async def test_clipboard_rejects_missing_and_sensitive_values() -> None:
    executor = build_production_executor_registry().get("set_clipboard")
    assert (await executor.execute({}, ExecutionContext())).error == "文本内容不能为空"
    actions = DesktopActions()
    context = ExecutionContext(
        variables={"secret": "value"},
        sensitive_variables={"secret"},
        desktop_actions=actions,
    )
    result = await executor.execute({"textContent": "{secret}"}, context)
    assert result.error == "剪贴板内容不能包含凭据或敏感变量"
    assert actions.requests == []


@pytest.mark.asyncio
async def test_sound_and_notification_keep_source_defaults() -> None:
    actions = DesktopActions()
    context = ExecutionContext(desktop_actions=actions)
    registry = build_production_executor_registry()

    sound = await registry.get("play_sound").execute({}, context)
    notification = await registry.get("system_notification").execute(
        {"notifyMessage": "完成", "duration": 0}, context
    )

    assert sound.data == {"count": 1}
    assert notification.data == {
        "title": "WebRPA通知",
        "message": "完成",
        "duration": 5,
    }
    assert actions.requests == [
        ("beep", {"count": 1, "interval": 0.3}, 60),
        (
            "notification",
            {
                "title": "WebRPA通知",
                "message": "完成",
                "duration": 5,
                "playSound": True,
            },
            60,
        ),
    ]


@pytest.mark.asyncio
async def test_platform_failure_is_a_node_failure() -> None:
    actions = DesktopActions(DesktopActionResult(False, error="系统拒绝"))
    result = (
        await build_production_executor_registry()
        .get("play_sound")
        .execute({}, ExecutionContext(desktop_actions=actions))
    )
    assert result.success is False
    assert result.error == "系统拒绝"
