from typing import Any

from autoflow.domain.android.capacity_rules import can_admit
from autoflow.domain.android.ports import AndroidError


def admit(request: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    total = snapshot.get("memoryMb")
    used = snapshot.get("usedMb")
    if not isinstance(total, int) or not isinstance(used, int):
        raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "容量尚未核实，不能准入批量操作", 409)
    if request.get("cpu", 1) > int(snapshot.get("cpu", 0)) or not can_admit(
        total * 1024**2,
        used * 1024**2,
        0,
        int(request.get("memoryMb", 0)) * 1024**2,
    ):
        raise AndroidError("ANDROID_CAPACITY", "容量不足，请停止空闲实例或降低配置", 422)
    return True
