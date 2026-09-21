from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from autoflow.domain.android.ports import AndroidError


class AndroidBulkService:
    def __init__(self, resources: Any, devices: Any) -> None:
        self.resources, self.devices = resources, devices

    def _get(self, identifier: str) -> dict[str, Any]:
        getter = getattr(self.devices, "get", None)
        if getter is not None:
            return getter(identifier)
        return self.devices.repository.get(identifier)

    def create(self, workspace: str, request_id: str, action: str, items: list[dict[str, Any]], delete_data: bool) -> dict[str, Any]:
        if not items or len(items) > 20 or len({item["deviceId"] for item in items}) != len(items):
            raise AndroidError("ANDROID_BULK_TARGET_INVALID", "批次必须包含 1–20 个不重复设备", 422)
        existing = next((item for item in self.resources.list("bulk") if item.get("workspaceIdentity") == workspace and item.get("requestId") == request_id), None)
        if existing is not None:
            same = existing.get("action") == action and existing.get("deleteData") is delete_data and [
                (item.get("deviceId"), item.get("expectedRevision")) for item in existing.get("items", [])
            ] == [(item["deviceId"], item["expectedRevision"]) for item in items]
            if not same:
                raise AndroidError("ANDROID_BULK_REQUEST_CONFLICT", "请求编号已用于不同批量操作", 409)
            return existing
        frozen = []
        for item in items:
            device = self._get(item["deviceId"])
            frozen.append({"deviceId": item["deviceId"], "expectedRevision": item["expectedRevision"], "state": "queued", "operationId": None, "error": None, "name": device.get("name")})
        record = {"id": str(uuid4()), "workspaceIdentity": workspace, "requestId": request_id, "action": action, "deleteData": delete_data, "state": "queued", "items": frozen, "createdAt": datetime.now(UTC).isoformat()}
        self.resources.save("bulk", record)
        return record

    def get(self, identifier: str) -> dict[str, Any]:
        return self.resources.get("bulk", identifier)

    def run(self, identifier: str) -> dict[str, Any]:
        batch = self.get(identifier)
        for item in batch["items"]:
            if item["state"] != "queued":
                continue
            try:
                device = self._get(item["deviceId"])
                if int(device.get("generation", 0)) != int(item["expectedRevision"]):
                    raise AndroidError("ANDROID_REVISION_CONFLICT", "设备已发生变化，请重新创建批次", 409)
                result = self.devices.operate(item["deviceId"], {"requestId": f'{batch["requestId"]}:{item["deviceId"]}', "action": batch["action"], "deleteData": batch["deleteData"]})
                item.update(state="accepted", operationId=(result.get("operation") or {}).get("id"))
            except AndroidError as error:
                item.update(state="failed", error=error.message)
        states = {item["state"] for item in batch["items"]}
        batch["state"] = "partially_failed" if "failed" in states and len(states) > 1 else "failed" if "failed" in states else "succeeded"
        self.resources.save("bulk", batch)
        return batch

    def action(self, identifier: str, action: str) -> dict[str, Any]:
        batch = self.get(identifier)
        if action == "cancelPending":
            for item in batch["items"]:
                if item["state"] == "queued":
                    item["state"] = "cancelled"
        elif action == "retryFailed":
            for item in batch["items"]:
                if item["state"] == "failed":
                    item.update(state="queued", error=None)
        else:
            raise AndroidError("ANDROID_BULK_ACTION_INVALID", "批次动作无效", 422)
        self.resources.save("bulk", batch)
        return batch
