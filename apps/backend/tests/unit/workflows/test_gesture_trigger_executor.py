from __future__ import annotations

from typing import Any

import pytest

from autoflow.application.workflows.executors import gesture_trigger
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


@pytest.mark.asyncio
async def test_gesture_trigger_executes_frontend_millisecond_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class Service:
        def wait_for_gesture(self, name: str, **kwargs: Any) -> dict[str, str]:
            captured.update(name=name, **kwargs)
            return {"gesture": name, "timestamp": "2026-09-21T00:00:00+00:00"}

    monkeypatch.setattr(gesture_trigger, "_worker_service", lambda: Service())
    context = ExecutionContext()
    executor = build_production_executor_registry().get("gesture_trigger")
    assert executor is not None
    result = await executor.execute(
        {
            "gestureName": "点赞",
            "cameraIndex": 2,
            "debugWindow": True,
            "confidenceThreshold": 0.75,
            "timeout": 60_000,
            "saveToVariable": "gesture_data",
        },
        context,
    )

    assert result.success
    assert captured["name"] == "点赞"
    assert captured["camera_index"] == 2
    assert captured["debug_window"] is True
    assert captured["confidence_threshold"] == 0.75
    assert captured["timeout"] == 60
    assert context.variables["gesture_data"]["gesture"] == "点赞"


@pytest.mark.asyncio
async def test_gesture_trigger_rejects_missing_name() -> None:
    executor = build_production_executor_registry().get("gesture_trigger")
    assert executor is not None
    result = await executor.execute({}, ExecutionContext())
    assert not result.success
    assert result.error == "手势名称不能为空"
