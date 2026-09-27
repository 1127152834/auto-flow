from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoflow.infrastructure.gesture import GestureRecognitionService


def _landmarks(offset: float = 0) -> list[list[float]]:
    return [[offset + index / 100, index / 200, -index / 300] for index in range(21)]


def test_custom_gesture_roundtrip_similarity_and_status(tmp_path: Path) -> None:
    data_file = tmp_path / "gestures.json"
    data_file.write_text(
        json.dumps({"点赞": _landmarks()}, ensure_ascii=False), encoding="utf-8"
    )
    service = GestureRecognitionService(data_file, tmp_path / "model.task")

    assert service.list_custom_gestures() == [{"name": "点赞", "type": "custom"}]
    assert service.match_gesture(_landmarks(), service.custom_gestures(), 0.6) == "点赞"
    assert service.calculate_similarity(_landmarks(), _landmarks()) == 1
    assert service.delete_gesture("点赞") is True
    assert service.delete_gesture("点赞") is False
    assert service.get_status() == {
        "is_running": False,
        "camera_index": 0,
        "debug_window": False,
        "gesture_count": 0,
    }


def test_wait_for_gesture_uses_camera_and_releases_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import cv2

    data_file = tmp_path / "gestures.json"
    data_file.write_text(json.dumps({"OK": _landmarks()}), encoding="utf-8")
    service = GestureRecognitionService(data_file, tmp_path / "model.task")
    points = [SimpleNamespace(x=p[0], y=p[1], z=p[2]) for p in _landmarks()]
    released = False

    class Capture:
        def isOpened(self) -> bool:
            return True

        def set(self, *_args: object) -> None:
            return None

        def read(self) -> tuple[bool, object]:
            return True, object()

        def release(self) -> None:
            nonlocal released
            released = True

    monkeypatch.setattr(cv2, "VideoCapture", lambda _index: Capture())
    monkeypatch.setattr(cv2, "flip", lambda frame, _axis: frame)
    monkeypatch.setattr(service, "_detect", lambda _frame: [points])

    result = service.wait_for_gesture(
        "OK",
        camera_index=0,
        debug_window=False,
        confidence_threshold=0.6,
        timeout=1,
        cancelled=lambda: False,
    )

    assert result["gesture"] == "OK"
    assert "timestamp" in result
    assert released is True
    assert service.get_status()["is_running"] is False


def test_invalid_persisted_landmarks_are_rejected(tmp_path: Path) -> None:
    data_file = tmp_path / "gestures.json"
    data_file.write_text('{"broken": [[0, 0, 0]]}', encoding="utf-8")
    service = GestureRecognitionService(data_file, tmp_path / "model.task")
    with pytest.raises(RuntimeError, match="关键点格式无效"):
        service.custom_gestures()
