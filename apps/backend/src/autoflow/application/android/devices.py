import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from uuid import uuid4

from autoflow.application.android.management import AndroidManagement
from autoflow.domain.android.ports import AndroidError, AndroidRuntime, DeviceRepository

Emit = Callable[[dict[str, Any], dict[str, Any]], Awaitable[None]]


class AndroidDeviceService:
    def __init__(self, repository: DeviceRepository, runtime: AndroidRuntime) -> None:
        self.repository, self.runtime = repository, runtime
        self.management = AndroidManagement(repository, runtime)
        self.device: dict[str, Any] | None = None
        self.handoff: dict[str, Any] | None = None
        self.continued = asyncio.Event()
        self.control_lock = asyncio.Lock()
        self.request_lock = asyncio.Lock()
        self.resuming = False
        self.open_task: asyncio.Task[None] | None = None
        self.continue_task: asyncio.Task[None] | None = None
        self.stopping = False
        self.emit: Emit | None = None
        self.close_console: Callable[[], Awaitable[None]] | None = None
        self.takeover_requested = False
        self.preview_slots = asyncio.Semaphore(2)
        self.preview_locks: dict[str, asyncio.Lock] = {}
        self.previews: dict[str, tuple[float, bytes]] = {}

    def context(self, device_id: str) -> "AndroidDeviceService":
        factory = getattr(self.runtime, "for_device", None)
        return AndroidDeviceService(self.repository, factory(device_id)) if factory else self

    def get(self, device_id: str) -> dict[str, Any]:
        """Expose the device facade used by bulk and cleanup services."""
        return self.repository.get(device_id)

    def operate(self, device_id: str, request: dict[str, Any]) -> dict[str, Any]:
        """Route lifecycle writes through the durable management owner."""
        return self.management.operate(device_id, request)

    async def environment(self) -> dict[str, Any]:
        return await self.runtime.environment()

    async def devices(self) -> list[dict[str, Any]]:
        result = []
        for device in self.repository.list():
            if device.get("deleted"):
                continue
            try:
                observed = await self.runtime.inspect(device)
                # Container running alone is not Android readiness.
                status = observed["androidStatus"]
                error = device.get("lastError")
            except (AndroidError, OSError, TimeoutError):
                status, error = "unknown", "无法核实设备或运行环境"
            result.append(device_view(device) | {"androidStatus": status, "lastError": error})
        return result

    async def preview(self, device_id: str) -> bytes:
        self.repository.get(device_id)
        async with self.preview_locks.setdefault(device_id, asyncio.Lock()), self.preview_slots:
            device = self.repository.get(device_id)
            if device.get("deleted") or device.get("control") in {"managing", "recovery_required"}:
                raise AndroidError("ANDROID_PREVIEW_UNAVAILABLE", "当前设备状态无法核实")
            cached = self.previews.get(device_id)
            if cached and monotonic() - cached[0] < 1:
                return cached[1]
            data = await self.runtime.preview(device)
            if len(self.previews) >= 20:
                self.previews.pop(next(iter(self.previews)))
            self.previews[device_id] = (monotonic(), data)
            return data

    def claim(self, device_id: str, run_id: str) -> dict[str, Any]:
        self.runtime.lock()
        try:
            self.device = self.repository.claim(device_id, run_id)
            self.stopping = False
            self.handoff = None
            self.continued = asyncio.Event()
            return self.device
        except BaseException:
            self.runtime.unlock()
            raise

    def rollback_claim(self) -> None:
        if self.device is not None:
            self.device.update(ownerRunId=None, control="idle")
            self._save()
            self.device = None
        self.runtime.unlock()

    def _save(self) -> None:
        assert self.device is not None
        self.repository.save(self.device)

    async def connect(self) -> None:
        assert self.device is not None
        await self.runtime.connect(self.device, self._save)

    async def command(self, operation: str, args: dict[str, Any], timeout: float) -> bytes:
        async with self.control_lock:
            if self.stopping or self.device is None or self.device["control"] != "workflow" or (self.runtime.window_open() and not getattr(self.runtime, "window_readonly", False)) or (self.handoff is not None and not self.continued.is_set()):
                raise AndroidError("ANDROID_CONTROL_CONFLICT", "设备当前不允许自动操作")
            async with asyncio.timeout(timeout):
                return await self.runtime.command(operation, args, timeout)

    async def _publish(self, event: str, message: str, state: str | None = None) -> None:
        assert self.emit is not None and self.handoff is not None
        changes: dict[str, Any] = {"handoff": dict(self.handoff)}
        if state:
            changes["state"] = state
        await self.emit({"type": event, "nodeId": self.handoff["nodeId"], "message": message}, changes)

    async def manual(self, node_id: str, config: dict[str, Any], emit: Emit) -> None:
        assert self.device is not None
        self.emit = emit
        self.continued.clear()
        self.resuming = False
        self.open_task = self.continue_task = None
        deadline = datetime.now(UTC) + timedelta(seconds=config["timeoutSeconds"])
        self.handoff = {"handoffId": str(uuid4()), "nodeId": node_id, "state": "waiting", "prompt": config["prompt"], "deadlineAt": deadline.isoformat(), "nativeSessionId": None, "error": None, "receipts": {}}
        self.device["generation"] += 1
        self._save()
        await self._publish("manual_requested", "等待人工处理", "waiting_manual")
        while not self.continued.is_set():
            if self.stopping:
                raise asyncio.CancelledError
            if datetime.now(UTC) >= deadline:
                raise AndroidError("ANDROID_MANUAL_TIMEOUT", "人工处理等待超时", 504)
            if self.handoff["state"] == "open" and not self.runtime.window_open():
                async with self.control_lock:
                    if self.handoff["state"] == "open":
                        await self.runtime.close_window()
                        self.device["control"] = "workflow"
                        self._save()
                        self.handoff["state"] = "closed"
                        await self._publish("native_closed", "窗口已关闭，工作流仍在等待")
            await asyncio.sleep(.1)

    async def control(self, handoff_id: str, request_id: str, action: str) -> None:
        async with self.request_lock:
            await self._control(handoff_id, request_id, action)

    async def _control(self, handoff_id: str, request_id: str, action: str) -> None:
        if self.handoff is None or self.handoff["handoffId"] != handoff_id:
            raise AndroidError("ANDROID_HANDOFF_STALE", "人工处理会话已过期")
        receipts = self.handoff["receipts"]
        if request_id in receipts:
            if receipts[request_id] != action:
                raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于不同操作")
            return
        if self.stopping or self.continued.is_set() or self.resuming:
            raise AndroidError("ANDROID_HANDOFF_STALE", "当前会话已结束或正在继续")
        if datetime.now(UTC) >= datetime.fromisoformat(self.handoff["deadlineAt"]):
            raise AndroidError("ANDROID_MANUAL_TIMEOUT", "人工处理等待超时", 504)
        if len(receipts) >= 100:
            raise AndroidError("ANDROID_REQUEST_LIMIT", "本次人工处理请求次数达到上限")
        if action == "open" and (self.open_task and not self.open_task.done() or self.runtime.window_open()):
            raise AndroidError("ANDROID_WINDOW_BUSY", "原生窗口正在启动或已打开")
        receipts[request_id] = action
        try:
            await self._publish("native_opening" if action == "open" else "resume_requested", "正在打开操作窗口" if action == "open" else "正在收回控制权", None if action == "open" else "resuming")
        except BaseException:
            receipts.pop(request_id)
            raise
        if action == "open":
            self.open_task = asyncio.create_task(self._open())
        else:
            self.resuming = True
            self.handoff["state"] = "resuming"
            self.continue_task = asyncio.create_task(self._continue())

    async def _open(self) -> None:
        assert self.device is not None and self.handoff is not None
        async with self.control_lock:
            try:
                if self.stopping:
                    return
                self.device["control"] = "opening_manual"
                self._save()
                self.handoff.update(state="starting", nativeSessionId=str(uuid4()), error=None)
                await self._publish("native_opening", "正在启动原生窗口")
                await self.runtime.open_window("AutoFlow · " + self.device["name"])
                if self.stopping:
                    return
                self.device["control"] = "manual"
                self._save()
                self.handoff["state"] = "open"
                await self._publish("native_opened", "请在 Mac 原生窗口操作")
            except Exception as exc:  # noqa: BLE001 -- window errors must retain control and surface a safe failure.
                try:
                    await self.runtime.close_window()
                    self.device["control"] = "workflow"
                except Exception:  # noqa: BLE001 -- uncertain connection must stay quarantined.
                    self.device["control"] = "recovery_required"
                    self.resuming = True
                self._save()
                self.handoff.update(state="failed", error=str(exc) if isinstance(exc, AndroidError) else "原生窗口启动失败")
                await self._publish("native_failed", "原生连接清理未确认，请停止并重试清理" if self.resuming else "原生窗口启动失败，可重试或继续", "resuming" if self.resuming else None)

    async def _continue(self) -> None:
        assert self.device is not None and self.handoff is not None
        try:
            async with self.control_lock:
                if self.stopping:
                    return
                self.device["control"] = "closing_manual"
                self._save()
                if self.close_console:
                    await self.close_console()
                await self.runtime.close_window()
                if self.stopping:
                    return
                if datetime.now(UTC) >= datetime.fromisoformat(self.handoff["deadlineAt"]):
                    raise AndroidError("ANDROID_MANUAL_TIMEOUT", "人工处理等待超时", 504)
                self.device["control"] = "workflow"
                self._save()
                self.handoff["state"] = "completed"
                await self._publish("resumed", "人工处理完成，继续自动执行", "running")
                self.continued.set()
        except Exception:  # noqa: BLE001 -- failed cleanup never releases ownership.
            self.device.update(control="recovery_required", lastError="原生连接交接失败，请停止并重试清理")
            self._save()
            self.handoff.update(state="failed", error=self.device["lastError"])
            await self._publish("native_failed", self.device["lastError"], "resuming")

    def request_stop(self) -> None:
        self.stopping = True
        for task in (self.open_task, self.continue_task):
            if task is not None and not task.done():
                task.cancel()

    async def cleanup(self) -> None:
        self.request_stop()
        await asyncio.gather(*(t for t in (self.open_task, self.continue_task) if t), return_exceptions=True)
        if self.device is None:
            return
        try:
            if self.close_console:
                await self.close_console()
            await self.runtime.disconnect()
            await self.runtime.recover(self.device)
            self.device.update(control="idle", ownerRunId=None, lastError=None)
            self._save()
            self.device = None
            self.runtime.unlock()
        except BaseException:
            assert self.device is not None
            self.device.update(control="recovery_required", lastError="清理尚未确认，请重试停止")
            self._save()
            raise

    async def recover(self) -> None:
        if self.management.operations is not None:
            recover_running = getattr(self.management.operations, "recover_running", None)
            if callable(recover_running):
                recover_running(self.management.workspace_identity)
        records = [
            d
            for d in self.repository.list()
            if not d.get("deleted")
            and (
                d.get("ownerRunId")
                or d.get("control") != "idle"
                or d.get("operation", {}).get("state") == "needs_verification"
            )
        ]
        if not records:
            return
        try:
            self.runtime.lock()
        except AndroidError:
            return  # Another controller or unsupported platform cannot block app startup.
        try:
            for device in records:
                device["control"] = "recovery_required"
                self.repository.save(device)
                try:
                    operation_state = device.get("operation", {}).get("state")
                    if operation_state == "needs_verification":
                        device["lastError"] = "管理操作结果待核实，请先核实设备状态"
                        self.repository.save(device)
                        continue
                    if operation_state in {"running", "interrupted", "failed"}:
                        device["operation"].update(state="interrupted", stage="等待核实", error="服务已重启，请核实设备状态")
                        device["lastError"] = "管理操作中断，请点击核实状态"
                        self.repository.save(device)
                        continue
                    await self.runtime.recover(device)
                    device.update(ownerRunId=None, control="idle", lastError=None)
                except (AndroidError, OSError, TimeoutError):
                    device["lastError"] = "遗留操作未确认结束，设备保持隔离"
                self.repository.save(device)
        finally:
            self.runtime.unlock()

    def list(self) -> list[dict[str, Any]]:
        return self.repository.list()


def device_view(device: dict[str, Any]) -> dict[str, Any]:
    fields = ("deviceId", "name", "runtimeId", "ownerRunId", "control", "generation", "width", "height", "imageId")
    return {key: device.get(key) for key in fields} | {"androidStatus": device.get("androidStatus", "unknown"), "lastError": device.get("lastError"), "cpu": device.get("cpu", 1), "memoryMb": device.get("memoryMb", 1536), "dpi": device.get("dpi", 320), "androidVersion": device.get("androidVersion"), "architecture": device.get("architecture"), "dataRetained": device.get("dataRetained", False), "deleted": device.get("deleted", False), "operation": device.get("operation"), "profileId": device.get("profileId"), "profileName": device.get("profileName"), "instanceType": device.get("instanceType", "persistent"), "locale": device.get("locale", "zh-CN"), "timezone": device.get("timezone", "Asia/Shanghai")}
