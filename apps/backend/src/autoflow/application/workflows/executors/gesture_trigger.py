"""Camera gesture trigger migrated from WebRPA@5ccb900e.

Source: backend/app/executors/trigger.py#GestureTriggerExecutor.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.infrastructure.gesture import (
    GestureBusyError,
    GestureNotFoundError,
    GestureRecognitionService,
    gesture_model_path,
)

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_bool, to_float, to_int


class GestureTriggerExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "gesture_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        gesture_name = str(context.resolve_value(config.get("gestureName", ""))).strip()
        if not gesture_name:
            return ModuleResult(success=False, error="手势名称不能为空")
        camera_index = to_int(config.get("cameraIndex", 0), 0, context)
        debug_window = to_bool(config.get("debugWindow", False), False, context)
        threshold = to_float(config.get("confidenceThreshold", 0.6), 0.6, context)
        timeout = _timeout_seconds(to_float(config.get("timeout", 60), 60, context))
        variable_name = str(config.get("saveToVariable", "gesture_data"))
        try:
            service = _worker_service()
            await context.send_progress(f"👋 手势触发器已启动，等待手势: {gesture_name}")
            data = await asyncio.to_thread(
                service.wait_for_gesture,
                gesture_name,
                camera_index=camera_index,
                debug_window=debug_window,
                confidence_threshold=threshold,
                timeout=timeout,
                cancelled=lambda: bool(
                    context.cancellation and context.cancellation.cancelled
                ),
            )
            if variable_name:
                context.set_variable(variable_name, data)
            return ModuleResult(
                success=True,
                message=f"手势触发器已触发: {gesture_name}",
                data=data,
            )
        except asyncio.CancelledError:
            raise
        except InterruptedError:
            raise asyncio.CancelledError from None
        except (GestureBusyError, GestureNotFoundError, TimeoutError) as error:
            return ModuleResult(success=False, error=str(error))
        except ImportError:
            return ModuleResult(
                success=False,
                error="手势触发器初始化失败，请安装 mediapipe 和 opencv-python",
            )
        except Exception as error:  # noqa: BLE001 - camera/model errors become node errors.
            return ModuleResult(success=False, error=f"手势触发器失败: {error}")


def _timeout_seconds(value: float) -> float:
    # AutoFlow's migrated panel persists this one legacy field in milliseconds.
    return value / 1000 if value >= 1000 else value


@lru_cache(maxsize=1)
def _worker_service() -> GestureRecognitionService:
    configured = os.environ.get("AUTOFLOW_GESTURE_DATA_FILE")
    if not configured:
        raise RuntimeError("手势数据存储未配置")
    return GestureRecognitionService(Path(configured), gesture_model_path())


GESTURE_TRIGGER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    GestureTriggerExecutor,
)
