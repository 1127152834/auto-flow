"""Host facts for the execution-capacity setting. Read-only; nothing here changes the machine."""

from __future__ import annotations

import importlib
import os
from typing import Any

from autoflow.domain.settings.execution_capacity import HardwareProfile

MEMORY_PRESSURE_PERCENT = 85.0

# psutil 没有随锁定依赖提供类型桩；按名称导入，避免各平台 mypy 结果不一致。
_psutil: Any = importlib.import_module("psutil")


def system_hardware() -> HardwareProfile:
    return HardwareProfile(os.cpu_count() or 1, int(_psutil.virtual_memory().total))


def memory_pressure() -> bool:
    """True when used memory is at or above the dispatch-pause watermark (spec M1 R1-10)."""
    return float(_psutil.virtual_memory().percent) >= MEMORY_PRESSURE_PERCENT
