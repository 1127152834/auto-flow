"""Screen image trigger migrated from WebRPA@5ccb900e.

Source: backend/app/executors/trigger.py#ImageTriggerExecutor.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import parse_search_region, to_float, to_int

_monotonic = time.monotonic


class ImageTriggerExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "image_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        image_path = context.resolve_value(config.get("imagePath", ""))
        confidence = to_float(config.get("confidence", 0.8), 0.8, context)
        check_interval = to_float(config.get("checkInterval", 0.5), 0.5, context)
        timeout = to_int(config.get("timeout", 0), 0, context)
        region = parse_search_region(config.get("searchRegion") or {})
        variable_name = str(config.get("saveToVariable", "image_event"))
        if not image_path:
            return ModuleResult(success=False, error="图像路径不能为空")
        path = Path(str(image_path))
        if not path.exists():
            return ModuleResult(success=False, error=f"图像文件不存在: {image_path}")
        try:
            template, width, height = await asyncio.to_thread(_load_template, path)
            if template is None:
                return ModuleResult(success=False, error="无法读取图像文件")
            use_region = region[2] > 0 and region[3] > 0
            _log(context, "🖼️ 图像触发器已启动")
            _log(
                context,
                (
                    f"📍 搜索区域: ({region[0]}, {region[1]}) - "
                    f"({region[0] + region[2]}, {region[1] + region[3]})"
                    if use_region
                    else "📍 搜索区域: 整个屏幕"
                ),
            )
            _log(context, f"🎯 匹配置信度: {confidence:.0%}")
            started = _monotonic()
            best = 0.0
            while True:
                if context.cancellation is not None:
                    context.cancellation.raise_if_cancelled()
                if timeout > 0 and _monotonic() - started >= timeout:
                    return ModuleResult(
                        success=False,
                        error=(
                            f"图像触发器超时（{timeout}秒），最高匹配度: {best:.2%}"
                        ),
                    )
                screen, offset_x, offset_y = await asyncio.to_thread(
                    _capture_screen, region if use_region else None
                )
                match, location = await asyncio.to_thread(_best_match, screen, template)
                best = max(best, match)
                if match >= confidence:
                    x = offset_x + location[0] + width // 2
                    y = offset_y + location[1] + height // 2
                    data = {"x": x, "y": y, "confidence": match}
                    if variable_name:
                        context.set_variable(variable_name, data)
                    return ModuleResult(
                        success=True,
                        message=(
                            f"图像触发器已触发，位置: ({x}, {y})，匹配度: {match:.2%}"
                        ),
                        data=data,
                    )
                await asyncio.sleep(max(0, check_interval))
        except ImportError as error:
            missing = (
                str(error).split("'")[1]
                if "'" in str(error)
                else "opencv-python/Pillow"
            )
            return ModuleResult(success=False, error=f"图像触发器初始化失败: {missing}")
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - capture errors become node errors.
            return ModuleResult(success=False, error=f"图像触发器失败: {error}")


def _load_template(path: Path) -> tuple[Any, int, int]:
    import cv2  # type: ignore[import-untyped]
    import numpy as np

    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None, 0, 0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    return gray, int(width), int(height)


def _capture_screen(
    region: tuple[int, int, int, int] | None,
) -> tuple[Any, int, int]:
    import cv2  # type: ignore[import-untyped]
    import numpy as np
    from PIL import ImageGrab

    if region is not None:
        x, y, width, height = region
        image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        offset_x, offset_y = x, y
    else:
        image = ImageGrab.grab(all_screens=True)
        offset_x = offset_y = 0
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY), offset_x, offset_y


def _best_match(screen: Any, template: Any) -> tuple[float, tuple[int, int]]:
    import cv2  # type: ignore[import-untyped]

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _minimum, maximum, _minimum_location, maximum_location = cv2.minMaxLoc(result)
    return float(maximum), (int(maximum_location[0]), int(maximum_location[1]))


def _log(context: ExecutionContext, message: str) -> None:
    context.log_records.append(
        {
            "timestamp": context.clock.now().isoformat(),
            "level": "info",
            "message": message,
            "duration": 0,
            "nodeId": context.current_node_id or "",
        }
    )


IMAGE_TRIGGER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (ImageTriggerExecutor,)
