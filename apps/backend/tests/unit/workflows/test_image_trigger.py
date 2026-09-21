from __future__ import annotations

from pathlib import Path

import pytest

from autoflow.application.workflows.executors import image_trigger
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


@pytest.mark.asyncio
async def test_image_trigger_maps_match_position_region_and_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    template = tmp_path / "target.png"
    template.write_bytes(b"image")
    monkeypatch.setattr(
        image_trigger, "_load_template", lambda _path: ("target", 20, 10)
    )
    monkeypatch.setattr(
        image_trigger, "_capture_screen", lambda _region: ("screen", 100, 200)
    )
    monkeypatch.setattr(
        image_trigger, "_best_match", lambda _screen, _template: (0.92, (5, 7))
    )
    executor = build_production_executor_registry().get("image_trigger")
    assert executor is not None
    context = ExecutionContext()
    result = await executor.execute(
        {
            "imagePath": str(template),
            "confidence": 0.8,
            "searchRegion": {"x": 100, "y": 200, "width": 300, "height": 400},
            "saveToVariable": "match",
        },
        context,
    )

    assert result.success is True
    assert result.data == {"x": 115, "y": 212, "confidence": 0.92}
    assert context.variables["match"] == result.data
    assert "位置: (115, 212)" in result.message


@pytest.mark.asyncio
async def test_image_trigger_validation_and_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executor = build_production_executor_registry().get("image_trigger")
    assert executor is not None
    missing = await executor.execute({}, ExecutionContext())
    assert missing.error == "图像路径不能为空"
    absent = await executor.execute(
        {"imagePath": str(tmp_path / "absent.png")}, ExecutionContext()
    )
    assert absent.error == f"图像文件不存在: {tmp_path / 'absent.png'}"

    template = tmp_path / "target.png"
    template.write_bytes(b"image")
    times = iter((0.0, 2.0))
    monkeypatch.setattr(image_trigger, "_monotonic", lambda: next(times))
    monkeypatch.setattr(image_trigger, "_load_template", lambda _path: ("target", 1, 1))
    timed_out = await executor.execute(
        {"imagePath": str(template), "timeout": 1}, ExecutionContext()
    )
    assert timed_out.error == "图像触发器超时（1秒），最高匹配度: 0.00%"
