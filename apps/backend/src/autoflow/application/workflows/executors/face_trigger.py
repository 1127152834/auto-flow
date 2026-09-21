"""Camera face trigger migrated from WebRPA@5ccb900e.

Source: backend/app/executors/trigger.py#FaceTriggerExecutor.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float, to_int

_monotonic = time.monotonic


class FaceTriggerExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "face_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        image_path = context.resolve_value(config.get("targetFaceImage", ""))
        tolerance = to_float(config.get("tolerance", 0.6), 0.6, context)
        check_interval = to_float(config.get("checkInterval", 0.5), 0.5, context)
        timeout = to_int(config.get("timeout", 0), 0, context)
        camera_index = to_int(config.get("cameraIndex", 0), 0, context)
        variable_name = str(config.get("saveToVariable", "face_event"))
        if not image_path:
            return ModuleResult(success=False, error="目标人脸图片路径不能为空")
        path = Path(str(image_path))
        if not path.exists():
            return ModuleResult(success=False, error=f"目标人脸图片不存在: {image_path}")

        capture = None
        try:
            target_encoding = await asyncio.to_thread(_load_target_face, path)
            if target_encoding is None:
                return ModuleResult(success=False, error="目标图片中未检测到人脸")
            capture = await asyncio.to_thread(_open_camera, camera_index)
            if not capture.isOpened():
                return ModuleResult(success=False, error=f"无法打开摄像头 {camera_index}")
            await _progress(context, "📹 摄像头已打开，开始监控...")
            started = _monotonic()
            frame_count = 0
            frame_step = max(1, int(check_interval * 30))
            while True:
                if context.cancellation is not None:
                    context.cancellation.raise_if_cancelled()
                if timeout > 0 and _monotonic() - started >= timeout:
                    return ModuleResult(
                        success=False, error=f"人脸触发器超时（{timeout}秒）"
                    )
                read, frame = await asyncio.to_thread(capture.read)
                if not read:
                    await asyncio.sleep(max(0, check_interval))
                    continue
                frame_count += 1
                if frame_count % frame_step:
                    await asyncio.sleep(0.01)
                    continue
                match = await asyncio.to_thread(
                    _find_match, frame, target_encoding, tolerance
                )
                if match is None:
                    await asyncio.sleep(max(0, check_interval))
                    continue
                confidence, location = match
                top, right, bottom, left = location
                data = {
                    "matched": True,
                    "confidence": confidence,
                    "face_location": {
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                        "left": left,
                    },
                }
                if variable_name:
                    context.set_variable(
                        variable_name,
                        {**data, "timestamp": context.clock.now().isoformat()},
                    )
                return ModuleResult(
                    success=True,
                    message=f"人脸触发器已触发，匹配度: {confidence:.2%}",
                    data=data,
                )
        except ImportError:
            return ModuleResult(
                success=False, error="人脸触发器初始化失败，请检查系统配置"
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - device errors become node errors.
            return ModuleResult(success=False, error=f"人脸触发器失败: {error}")
        finally:
            if capture is not None:
                await asyncio.to_thread(capture.release)


def _load_target_face(path: Path) -> Any | None:
    import face_recognition  # type: ignore[import-untyped]

    encodings = face_recognition.face_encodings(
        face_recognition.load_image_file(path)
    )
    return encodings[0] if encodings else None


def _open_camera(index: int) -> Any:
    import cv2  # type: ignore[import-untyped]

    return cv2.VideoCapture(index)


def _find_match(
    frame: Any, target_encoding: Any, tolerance: float
) -> tuple[float, tuple[int, int, int, int]] | None:
    import cv2  # type: ignore[import-untyped]
    import face_recognition  # type: ignore[import-untyped]

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb_frame)
    encodings = face_recognition.face_encodings(rgb_frame, locations)
    for encoding, location in zip(encodings, locations, strict=False):
        distance = float(face_recognition.face_distance([target_encoding], encoding)[0])
        if distance <= tolerance:
            top, right, bottom, left = location
            return 1 - distance, (
                int(top),
                int(right),
                int(bottom),
                int(left),
            )
    return None


async def _progress(context: ExecutionContext, message: str) -> None:
    context.log_records.append(
        {
            "timestamp": context.clock.now().isoformat(),
            "level": "info",
            "message": message,
            "duration": 0,
            "nodeId": context.current_node_id or "",
        }
    )
    await context.send_progress(message)


FACE_TRIGGER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (FaceTriggerExecutor,)
