"""Windows system-audio trigger migrated from WebRPA@5ccb900e.

Source: backend/app/executors/trigger.py#SoundTriggerExecutor.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float, to_int

_monotonic = time.monotonic


class SoundTriggerExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "sound_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        threshold = to_int(config.get("volumeThreshold", 50), 50, context)
        interval = to_float(config.get("checkInterval", 0.1), 0.1, context)
        timeout = to_int(config.get("timeout", 0), 0, context)
        variable_name = str(config.get("saveToVariable", "sound_event"))
        try:
            meter = _audio_meter()
            _log(context, "🔊 声音触发器已启动")
            _log(context, f"📊 音量阈值: {threshold}%")
            started = _monotonic()
            while True:
                if context.cancellation is not None:
                    context.cancellation.raise_if_cancelled()
                if timeout > 0 and _monotonic() - started >= timeout:
                    return ModuleResult(
                        success=False, error=f"声音触发器超时（{timeout}秒）"
                    )
                volume = int(float(meter.GetPeakValue()) * 100)
                if volume >= threshold:
                    if variable_name:
                        context.set_variable(variable_name, volume)
                    return ModuleResult(
                        success=True,
                        message=f"声音触发器已触发，当前音量: {volume}%",
                        data={"volume": volume},
                    )
                await asyncio.sleep(max(0, interval))
        except ImportError:
            return ModuleResult(
                success=False, error="声音触发器初始化失败，请检查系统配置"
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - native audio errors become node errors.
            return ModuleResult(success=False, error=f"声音触发器失败: {error}")


def _audio_meter() -> Any:
    from comtypes import CLSCTX_ALL  # type: ignore[import-not-found,import-untyped]
    from pycaw.pycaw import (  # type: ignore[import-not-found,import-untyped]
        AudioUtilities,
        IAudioMeterInformation,
    )

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioMeterInformation)


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


SOUND_TRIGGER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (SoundTriggerExecutor,)
