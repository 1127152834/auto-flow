from __future__ import annotations

from copy import deepcopy
from typing import Any

from autoflow.domain.android.ports import AndroidError

DEVICE_ID = "11111111-1111-4111-8111-111111111111"
PROFILE_ID = "22222222-2222-4222-8222-222222222222"


class MemoryDeviceRepository:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def list(self) -> list[dict[str, Any]]:
        return deepcopy(list(self.records.values()))

    def get(self, device_id: str) -> dict[str, Any]:
        record = self.records.get(device_id)
        if record is None:
            raise AndroidError("ANDROID_NOT_FOUND", "安卓设备未登记", 404)
        return deepcopy(record)

    def save(self, device: dict[str, Any]) -> None:
        self.records[device["deviceId"]] = deepcopy(device)

    def claim(self, device_id: str, run_id: str) -> dict[str, Any]:
        device = self.get(device_id)
        if device.get("control") != "idle":
            raise AndroidError("ANDROID_BUSY", "设备已占用")
        device.update(ownerRunId=run_id, control="workflow")
        self.save(device)
        return device
