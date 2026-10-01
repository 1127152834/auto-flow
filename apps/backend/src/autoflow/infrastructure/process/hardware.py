"""Host facts for the execution-capacity setting. Read-only; nothing here changes the machine."""

from __future__ import annotations

import os

import psutil

from autoflow.domain.settings.execution_capacity import HardwareProfile

MEMORY_PRESSURE_PERCENT = 85.0


def system_hardware() -> HardwareProfile:
    return HardwareProfile(os.cpu_count() or 1, int(psutil.virtual_memory().total))


def memory_pressure() -> bool:
    """True when used memory is at or above the dispatch-pause watermark (spec M1 R1-10)."""
    return float(psutil.virtual_memory().percent) >= MEMORY_PRESSURE_PERCENT
