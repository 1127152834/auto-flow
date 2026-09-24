from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors import face_trigger
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


class _Capture:
    def __init__(self, *, opened: bool = True, frames: list[Any] | None = None) -> None:
        self.opened = opened
        self.frames = list(frames or [])
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def read(self) -> tuple[bool, Any]:
        return (True, self.frames.pop(0)) if self.frames else (False, None)

    def release(self) -> None:
        self.released = True


@pytest.mark.asyncio
async def test_face_trigger_matches_and_releases_camera(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "face.png"
    target.write_bytes(b"face")
    capture = _Capture(frames=["frame"])
    monkeypatch.setattr(face_trigger, "_load_target_face", lambda _path: "target")
    monkeypatch.setattr(face_trigger, "_open_camera", lambda _index: capture)
    monkeypatch.setattr(
        face_trigger, "_find_match", lambda *_args: (0.75, (1, 2, 3, 4))
    )
    executor = build_production_executor_registry().get("face_trigger")
    assert executor is not None
    context = ExecutionContext()
    result = await executor.execute(
        {
            "targetFaceImage": str(target),
            "checkInterval": 0,
            "saveToVariable": "face",
        },
        context,
    )

    assert result.success is True
    assert result.data == {
        "matched": True,
        "confidence": 0.75,
        "face_location": {"top": 1, "right": 2, "bottom": 3, "left": 4},
    }
    assert context.variables["face"]["matched"] is True
    assert context.variables["face"]["timestamp"]
    assert capture.released is True


@pytest.mark.asyncio
async def test_face_trigger_validation_and_camera_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executor = build_production_executor_registry().get("face_trigger")
    assert executor is not None
    assert (await executor.execute({}, ExecutionContext())).error == (
        "目标人脸图片路径不能为空"
    )
    absent = tmp_path / "absent.png"
    assert (
        await executor.execute(
            {"targetFaceImage": str(absent)}, ExecutionContext()
        )
    ).error == f"目标人脸图片不存在: {absent}"

    target = tmp_path / "face.png"
    target.write_bytes(b"face")
    monkeypatch.setattr(face_trigger, "_load_target_face", lambda _path: None)
    no_face = await executor.execute(
        {"targetFaceImage": str(target)}, ExecutionContext()
    )
    assert no_face.error == "目标图片中未检测到人脸"

    capture = _Capture(opened=False)
    monkeypatch.setattr(face_trigger, "_load_target_face", lambda _path: "target")
    monkeypatch.setattr(face_trigger, "_open_camera", lambda _index: capture)
    camera_error = await executor.execute(
        {"targetFaceImage": str(target), "cameraIndex": 2}, ExecutionContext()
    )
    assert camera_error.error == "无法打开摄像头 2"
    assert capture.released is True
