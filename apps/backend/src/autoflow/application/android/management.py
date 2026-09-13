"""Durable, serial device lifecycle operations using the existing runtime owner."""
import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from autoflow.domain.android.ports import AndroidError, AndroidRuntime, DeviceRepository


def now() -> str:
    return datetime.now(UTC).isoformat()


class AndroidManagement:
    def __init__(self, repository: DeviceRepository, runtime: AndroidRuntime) -> None:
        self.repository, self.runtime = repository, runtime
        self.task: asyncio.Task[None] | None = None
        self.closing = False

    def busy(self) -> bool:
        return self.task is not None and not self.task.done()

    def _admit(self) -> None:
        if self.closing or self.busy():
            raise AndroidError("ANDROID_MANAGEMENT_BUSY", "设备管理操作尚未结束，请稍后再试")
        self.runtime.lock()

    def create(self, config: dict[str, Any]) -> dict[str, Any]:
        try:
            existing = self.repository.get(config["deviceId"])
        except AndroidError as error:
            if error.status != 404:
                raise
        else:
            if existing.get("creationConfig") != config:
                raise AndroidError("ANDROID_REQUEST_CONFLICT", "设备编号已用于其他创建配置")
            return existing
        self._admit()
        try:
            device = self.runtime.new_device(config)
            device["creationConfig"] = deepcopy(config)
            return self._start(device, {"requestId": config["deviceId"], "action": "create", "deleteData": False})
        except BaseException:
            self.runtime.unlock()
            raise

    def operate(self, device_id: str, request: dict[str, Any]) -> dict[str, Any]:
        device = self.repository.get(device_id)
        receipts = device.get("operationReceipts", {})
        prior = receipts.get(request["requestId"])
        if prior is not None:
            if prior != request:
                raise AndroidError("ANDROID_REQUEST_CONFLICT", "操作编号已用于不同请求")
            return device
        if device.get("deleted"):
            raise AndroidError("ANDROID_NOT_FOUND", "设备已删除", 404)
        if len(receipts) >= 1000:
            raise AndroidError("ANDROID_OPERATION_LIMIT", "设备操作记录达到本版本上限，请联系维护者")
        if device.get("ownerRunId") or device.get("control") not in {"idle", "recovery_required"}:
            raise AndroidError("ANDROID_BUSY", "请先结束设备的手动会话或工作流")
        if device.get("control") == "recovery_required" and request["action"] != "recover":
            raise AndroidError("ANDROID_RECOVERY_REQUIRED", "请先核实上一次设备操作")
        self._admit()
        try:
            return self._start(device, request)
        except BaseException:
            self.runtime.unlock()
            raise

    def _start(self, device: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        device.setdefault("operationReceipts", {})[request["requestId"]] = deepcopy(request)
        device.update(control="managing", lastError=None, operation={"id": request["requestId"], "action": request["action"], "state": "running", "stage": "准备中", "error": None, "startedAt": now(), "finishedAt": None})
        self.repository.save(device)
        self.task = asyncio.create_task(self._execute(device, request), name="android-management")
        return deepcopy(device)

    async def _execute(self, device: dict[str, Any], request: dict[str, Any]) -> None:
        def save() -> None:
            self.repository.save(device)

        def stage(text: str) -> None:
            device["operation"]["stage"] = text
            save()

        try:
            await self.runtime.manage(device, request, stage, save)
            device.update(control="idle", lastError=None)
            device["operation"].update(state="succeeded", stage="已完成", finishedAt=now())
        except asyncio.CancelledError:
            device.update(control="recovery_required", lastError="操作中断，请核实实际设备状态")
            device["operation"].update(state="interrupted", stage="等待核实", error=device["lastError"], finishedAt=now())
        except Exception as error:  # noqa: BLE001 -- persist a reviewable failed operation, never raw shell diagnostics.
            device.update(control="recovery_required", lastError=error.message if isinstance(error, AndroidError) else "设备操作未完成，请核实实际状态")
            device["operation"].update(state="failed", stage="需要处理", error=device["lastError"], finishedAt=now())
        finally:
            try:
                save()
            finally:
                self.runtime.unlock()

    def rename(self, device_id: str, name: str) -> dict[str, Any]:
        device = self.repository.get(device_id)
        if device.get("deleted") or device.get("control") != "idle":
            raise AndroidError("ANDROID_BUSY", "请在设备空闲时修改名称")
        self._admit()
        try:
            device["name"] = name
            self.repository.save(device)
            return device
        finally:
            self.runtime.unlock()

    async def shutdown(self) -> None:
        self.closing = True
        if self.task and not self.task.done():
            await asyncio.sleep(0)  # Enter the durable completion/failure owner before cancellation.
            self.task.cancel()
            await asyncio.shield(asyncio.gather(self.task, return_exceptions=True))
