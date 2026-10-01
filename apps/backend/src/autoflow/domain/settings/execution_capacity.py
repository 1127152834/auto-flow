"""How many browsers one machine runs at the same time (remediation M1, R1-07 / spec §5.3).

The 3/4-core and 1.5 GiB-per-task figures are only a starting heuristic that the user can
override. They are not a proof that any workflow stays stable at that concurrency.
"""

from __future__ import annotations

from dataclasses import dataclass

GIB = 1024**3
MAX_RUNNING_BROWSERS = 64
MEMORY_PER_BROWSER_BYTES = 3 * GIB // 2  # 1.5 GiB


@dataclass(frozen=True)
class HardwareProfile:
    logical_cpus: int
    total_memory_bytes: int


@dataclass(frozen=True)
class ExecutionCapacity:
    configured: int | None
    recommended: int
    effective: int
    live: int


def recommended_capacity(hardware: HardwareProfile) -> int:
    by_cpu = hardware.logical_cpus * 3 // 4
    by_memory = hardware.total_memory_bytes // MEMORY_PER_BROWSER_BYTES
    return max(1, min(by_cpu, by_memory, MAX_RUNNING_BROWSERS))


def validate_configured(value: object) -> int | None:
    """None restores the recommendation; anything else must be a real integer in range."""
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= MAX_RUNNING_BROWSERS:
        raise ValueError(f"maxRunningBrowsers must be an integer from 1 to {MAX_RUNNING_BROWSERS} or null")
    return value


def resolve_capacity(configured: object, hardware: HardwareProfile) -> ExecutionCapacity:
    value = validate_configured(configured)
    recommended = recommended_capacity(hardware)
    effective = recommended if value is None else value
    return ExecutionCapacity(value, recommended, effective, 2 * effective)
