"""Custom hand-gesture recognition migrated from WebRPA@5ccb900e.

Source: backend/app/services/gesture_recognition_service.py.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock


class GestureBusyError(RuntimeError):
    pass


class GestureNotFoundError(RuntimeError):
    pass


def gesture_model_path() -> Path:
    configured = os.environ.get("AUTOFLOW_GESTURE_MODEL_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return (
        Path(__file__).resolve().parents[2]
        / "resources"
        / "mediapipe"
        / "hand_landmarker.task"
    )


class GestureRecognitionService:
    """Workspace-owned gesture definitions with per-operation camera ownership."""

    def __init__(self, data_file: Path, model_path: Path | None = None) -> None:
        self._data_file = data_file.resolve()
        self._model_path = (model_path or gesture_model_path()).resolve()
        self._status_file = self._data_file.with_name("recognition-status.json")
        self._camera_lock_file = self._data_file.with_name("camera.lock")
        self._data_lock_file = self._data_file.with_name("definitions.lock")
        self._landmarker: Any = None
        self._landmarker_lock = Lock()

    def custom_gestures(self) -> dict[str, list[list[float]]]:
        if not self._data_file.exists():
            return {}
        try:
            raw = json.loads(self._data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"自定义手势数据无法读取: {error}") from error
        if not isinstance(raw, dict):
            raise TypeError("自定义手势数据格式无效")
        gestures: dict[str, list[list[float]]] = {}
        for name, landmarks in raw.items():
            if not isinstance(name, str) or not name.strip():
                raise RuntimeError("自定义手势名称无效")
            gestures[name] = _validated_landmarks(landmarks)
        return gestures

    def list_custom_gestures(self) -> list[dict[str, str]]:
        return [
            {"name": name, "type": "custom"}
            for name in self.custom_gestures()
        ]

    def delete_gesture(self, gesture_name: str) -> bool:
        lock = self._acquire_data()
        try:
            gestures = self.custom_gestures()
            if gesture_name not in gestures:
                return False
            del gestures[gesture_name]
            self._save_unlocked(gestures)
            return True
        finally:
            lock.release()

    def get_status(self) -> dict[str, Any]:
        try:
            status = json.loads(self._status_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            status = {}
        running = (
            isinstance(status, dict)
            and isinstance(status.get("pid"), int)
            and _pid_alive(status["pid"])
        )
        return {
            "is_running": running,
            "camera_index": int(status.get("camera_index", 0)) if running else 0,
            "debug_window": bool(status.get("debug_window", False)) if running else False,
            "gesture_count": len(self.custom_gestures()),
        }

    def record_gesture(
        self, gesture_name: str, camera_index: int = 0, timeout: float = 30
    ) -> bool:
        name = gesture_name.strip()
        if not name:
            raise ValueError("手势名称不能为空")
        lock = self._acquire_camera()
        capture = None
        window_name = "Gesture Recording - Press SPACE to confirm, ESC to cancel"
        token = uuid4().hex
        try:
            import cv2  # type: ignore[import-untyped]

            capture = cv2.VideoCapture(camera_index)
            if not capture.isOpened():
                return False
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
            self._write_status(token, camera_index, True)
            deadline = time.monotonic() + timeout if timeout > 0 else None
            recorded: list[list[float]] | None = None
            while deadline is None or time.monotonic() < deadline:
                read, frame = capture.read()
                if not read:
                    break
                frame = cv2.flip(frame, 1)
                hands = self._detect(frame)
                if hands:
                    recorded = self.normalize_landmarks(hands[0])
                    _draw_hand(cv2, frame, hands[0])
                    prompt = "Hand detected! Press SPACE to save"
                    color = (0, 255, 0)
                else:
                    prompt = "No hand detected. Show your hand gesture."
                    color = (0, 0, 255)
                cv2.putText(
                    frame, prompt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2
                )
                cv2.putText(
                    frame,
                    f"Recording: {name}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    return False
                if key == 32 and recorded:
                    self._store_gesture(name, recorded)
                    return True
            return False
        finally:
            if capture is not None:
                capture.release()
            try:
                import cv2  # type: ignore[import-untyped]

                cv2.destroyAllWindows()
            except ImportError:
                pass
            self.close()
            self._clear_status(token)
            lock.release()

    def wait_for_gesture(
        self,
        gesture_name: str,
        *,
        camera_index: int,
        debug_window: bool,
        confidence_threshold: float,
        timeout: float,
        cancelled: Callable[[], bool],
    ) -> dict[str, str]:
        gestures = self.custom_gestures()
        if gesture_name not in gestures:
            raise GestureNotFoundError(
                f"自定义手势不存在: {gesture_name}，请先录制该手势"
            )
        lock = self._acquire_camera()
        capture = None
        window_name = "Gesture Recognition (Press ESC to stop)"
        token = uuid4().hex
        try:
            import cv2  # type: ignore[import-untyped]

            capture = cv2.VideoCapture(camera_index)
            if not capture.isOpened():
                raise RuntimeError(f"无法启动手势识别，请检查摄像头 {camera_index}")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            if debug_window:
                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
            self._write_status(token, camera_index, debug_window)
            started = time.monotonic()
            while timeout <= 0 or time.monotonic() - started < timeout:
                if cancelled():
                    raise InterruptedError("手势识别已取消")
                read, frame = capture.read()
                if not read:
                    time.sleep(0.03)
                    continue
                frame = cv2.flip(frame, 1)
                hands = self._detect(frame)
                matched = None
                for hand in hands:
                    current = self.normalize_landmarks(hand)
                    matched = self.match_gesture(
                        current, gestures, confidence_threshold
                    )
                    if matched:
                        break
                if debug_window:
                    if hands:
                        _draw_hand(cv2, frame, hands[0])
                    cv2.putText(
                        frame,
                        f"Matched: {matched}" if matched else "No gesture matched",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0) if matched else (0, 0, 255),
                        2,
                    )
                    cv2.imshow(window_name, frame)
                    if cv2.waitKey(1) & 0xFF == 27:
                        raise InterruptedError("用户停止手势识别")
                else:
                    time.sleep(0.03)
                if matched == gesture_name:
                    return {
                        "gesture": matched,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
            raise TimeoutError(f"手势触发器超时（{timeout:g}秒）")
        finally:
            if capture is not None:
                capture.release()
            if debug_window:
                try:
                    import cv2  # type: ignore[import-untyped]

                    cv2.destroyAllWindows()
                except ImportError:
                    pass
            self.close()
            self._clear_status(token)
            lock.release()

    @staticmethod
    def normalize_landmarks(landmarks: Sequence[Any]) -> list[list[float]]:
        if not landmarks:
            return []
        wrist = landmarks[0]
        return [
            [
                float(point.x) - float(wrist.x),
                float(point.y) - float(wrist.y),
                float(point.z) - float(wrist.z),
            ]
            for point in landmarks
        ]

    @staticmethod
    def calculate_similarity(
        first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]
    ) -> float:
        if not first or len(first) != len(second):
            return 0.0
        distance = sum(
            math.sqrt(sum((a - b) ** 2 for a, b in zip(one, two, strict=True)))
            for one, two in zip(first, second, strict=True)
        )
        return math.exp(-(distance / len(first)) * 10)

    @classmethod
    def match_gesture(
        cls,
        current: Sequence[Sequence[float]],
        gestures: dict[str, list[list[float]]],
        threshold: float,
    ) -> str | None:
        best_name = None
        best_similarity = 0.0
        for name, saved in gestures.items():
            similarity = cls.calculate_similarity(current, saved)
            if similarity > best_similarity and similarity >= threshold:
                best_name, best_similarity = name, similarity
        return best_name

    def _detect(self, frame: Any) -> list[Any]:
        import cv2  # type: ignore[import-untyped]
        import mediapipe as mp  # type: ignore[import-untyped]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        return list(self._get_landmarker().detect(image).hand_landmarks)

    def _get_landmarker(self) -> Any:
        if self._landmarker is not None:
            return self._landmarker
        with self._landmarker_lock:
            if self._landmarker is None:
                if not self._model_path.is_file():
                    raise RuntimeError(
                        f"Hand landmarker model not found at {self._model_path}"
                    )
                python = importlib.import_module("mediapipe.tasks.python")
                vision = importlib.import_module("mediapipe.tasks.python.vision")

                options = vision.HandLandmarkerOptions(
                    base_options=python.BaseOptions(
                        model_asset_path=str(self._model_path)
                    ),
                    num_hands=1,
                    min_hand_detection_confidence=0.5,
                    min_hand_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._landmarker = vision.HandLandmarker.create_from_options(options)
        return self._landmarker

    def close(self) -> None:
        with self._landmarker_lock:
            landmarker, self._landmarker = self._landmarker, None
            if landmarker is not None:
                landmarker.close()

    def _store_gesture(self, name: str, landmarks: list[list[float]]) -> None:
        lock = self._acquire_data()
        try:
            gestures = self.custom_gestures()
            gestures[name] = landmarks
            self._save_unlocked(gestures)
        finally:
            lock.release()

    def _save_unlocked(self, gestures: dict[str, list[list[float]]]) -> None:
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._data_file.with_name(f".{self._data_file.name}.{uuid4().hex}")
        temporary.write_text(
            json.dumps(gestures, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self._data_file)

    def _acquire_camera(self) -> ExclusiveFileLock:
        lock = ExclusiveFileLock(self._camera_lock_file)
        if not lock.acquire():
            raise GestureBusyError("摄像头正在被手势录制或识别使用")
        return lock

    def _acquire_data(self) -> ExclusiveFileLock:
        lock = ExclusiveFileLock(self._data_lock_file)
        if not lock.acquire():
            raise GestureBusyError("自定义手势数据正在更新")
        return lock

    def _write_status(
        self, token: str, camera_index: int, debug_window: bool
    ) -> None:
        self._status_file.parent.mkdir(parents=True, exist_ok=True)
        self._status_file.write_text(
            json.dumps(
                {
                    "token": token,
                    "pid": os.getpid(),
                    "camera_index": camera_index,
                    "debug_window": debug_window,
                }
            ),
            encoding="utf-8",
        )

    def _clear_status(self, token: str) -> None:
        try:
            current = json.loads(self._status_file.read_text(encoding="utf-8"))
            if current.get("token") == token:
                self._status_file.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError, AttributeError):
            return


def _validated_landmarks(value: Any) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != 21:
        raise RuntimeError("自定义手势关键点格式无效")
    output: list[list[float]] = []
    for point in value:
        if not isinstance(point, list) or len(point) != 3:
            raise RuntimeError("自定义手势关键点格式无效")
        coordinates = [float(item) for item in point]
        if not all(math.isfinite(item) for item in coordinates):
            raise RuntimeError("自定义手势关键点包含无效数值")
        output.append(coordinates)
    return output


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
)


def _draw_hand(cv2: Any, frame: Any, landmarks: Sequence[Any]) -> None:
    for landmark in landmarks:
        cv2.circle(
            frame,
            (int(landmark.x * frame.shape[1]), int(landmark.y * frame.shape[0])),
            5,
            (0, 255, 0),
            -1,
        )
    for start_index, end_index in _CONNECTIONS:
        start, end = landmarks[start_index], landmarks[end_index]
        cv2.line(
            frame,
            (int(start.x * frame.shape[1]), int(start.y * frame.shape[0])),
            (int(end.x * frame.shape[1]), int(end.y * frame.shape[0])),
            (255, 0, 0),
            2,
        )
