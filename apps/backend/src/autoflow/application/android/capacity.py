from typing import Any

from autoflow.domain.android.capacity_rules import can_admit
from autoflow.domain.android.ports import AndroidError


def admit(request: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    total = snapshot.get("memoryMb")
    used = snapshot.get("usedMb")
    cpu = snapshot.get("cpu")
    if (
        not isinstance(cpu, int)
        or isinstance(cpu, bool)
        or cpu <= 0
        or not isinstance(total, int)
        or isinstance(total, bool)
        or total <= 0
        or not isinstance(used, int)
        or isinstance(used, bool)
        or used < 0
        or used > total
    ):
        raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "容量尚未核实，不能准入批量操作", 409)
    requested_cpu = request.get("cpu", 1)
    requested_memory = request.get("memoryMb")
    if (
        not isinstance(requested_cpu, int)
        or isinstance(requested_cpu, bool)
        or requested_cpu <= 0
        or not isinstance(requested_memory, int)
        or isinstance(requested_memory, bool)
        or requested_memory <= 0
    ):
        raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "请求容量尚未核实，不能准入批量操作", 409)
    if requested_cpu > cpu or not can_admit(
        total * 1024**2,
        used * 1024**2,
        0,
        requested_memory * 1024**2,
    ):
        raise AndroidError("ANDROID_CAPACITY", "容量不足，请停止空闲实例或降低配置", 422)
    return True
