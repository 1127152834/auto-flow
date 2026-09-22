import asyncio
import hashlib
import inspect
import json
import logging
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

from autoflow.application.android.verification import verify_lifecycle_operation
from autoflow.domain.android.ports import AndroidError


class AndroidBulkService:
    _terminal_items: ClassVar[set[str]] = {"succeeded", "failed", "cancelled", "needs_verification"}

    def __init__(self, resources: Any, devices: Any) -> None:
        self.resources, self.devices = resources, devices
        self.task: asyncio.Task[None] | None = None
        self.closing = False
        self.tick_lock = asyncio.Lock()

    async def start(self) -> None:
        self.closing = False
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop(), name="android-bulk-queue")

    async def shutdown(self) -> None:
        self.closing = True
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def _loop(self) -> None:
        while not self.closing:
            try:
                await self.tick()
            except Exception:
                logging.getLogger(__name__).exception("Android bulk queue tick failed")
            await asyncio.sleep(0.2)

    def _workspace_identity(self) -> str | None:
        return getattr(getattr(self.devices, "management", None), "workspace_identity", None)

    def _runtime_workspace_identity(self) -> str | None:
        value = getattr(getattr(self.devices, "runtime", None), "workspace_id", None)
        return str(value) if value is not None else None

    def _get(self, identifier: str, workspace: str | None = None) -> dict[str, Any]:
        getter = getattr(self.devices, "get", None)
        if getter is not None:
            try:
                device = getter(identifier)
            except TypeError as error:
                if workspace is None or "workspace" not in str(error) or "required" not in str(error):
                    raise
                device = getter(identifier, workspace=workspace)
        else:
            device = self.devices.repository.get(identifier)
        expected_workspace = self._runtime_workspace_identity() or workspace
        management_workspace = self._workspace_identity()
        if workspace is not None and management_workspace is not None and workspace != management_workspace:
            raise AndroidError("ANDROID_NOT_FOUND", "安卓设备未登记", 404)
        if workspace is not None and device.get("workspaceId") not in (None, expected_workspace):
            raise AndroidError("ANDROID_NOT_FOUND", "安卓设备未登记", 404)
        return device

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
            device = self._get(item["deviceId"], workspace)
            frozen_item = {"deviceId": item["deviceId"], "expectedRevision": item["expectedRevision"], "state": "queued", "operationId": None, "retryOf": None, "error": None, "name": device.get("name")}
            frozen.append(frozen_item)
        record = {"id": str(uuid4()), "workspaceIdentity": workspace, "requestId": request_id, "action": action, "deleteData": delete_data, "state": "queued", "items": frozen, "createdAt": datetime.now(UTC).isoformat()}
        for item in frozen:
            self._ensure_operation(record, item)
        self.resources.save("bulk", record)
        return record

    def _operations(self) -> Any | None:
        return getattr(getattr(self.devices, "management", None), "operations", None)

    @staticmethod
    def _operation_record(operations: Any, operation_id: str, workspace: str | None) -> Any:
        try:
            return operations.get(operation_id, workspace)
        except TypeError:
            return operations.get(operation_id)

    def _ensure_operation(self, batch: dict[str, Any], item: dict[str, Any], *, attempt: int = 1, retry_of: str | None = None) -> Any | None:
        operations = self._operations()
        if operations is None or not hasattr(operations, "accept"):
            return None
        request = {"requestId": self._request_id(batch, item, attempt), "action": batch["action"], "deleteData": batch["deleteData"]}
        if retry_of is not None:
            request["retryOf"] = retry_of
        digest = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        try:
            record = operations.accept(batch["workspaceIdentity"], request["requestId"], item["deviceId"], batch["action"], digest, request, retry_of=retry_of)
        except TypeError:
            if retry_of is not None:
                raise
            record = operations.accept(batch["workspaceIdentity"], request["requestId"], item["deviceId"], batch["action"], digest, request)
        item["operationId"] = record.operation_id
        return record

    def _mark_failed(self, batch: dict[str, Any], item: dict[str, Any], message: str) -> None:
        operation_id = item.get("operationId")
        operations = self._operations()
        if not operation_id or operations is None:
            return
        try:
            record = self._operation_record(operations, operation_id, batch.get("workspaceIdentity"))
            if record.state in {"queued", "waiting_capacity"}:
                operations.transition(operation_id, record.state, "failed", {"stage_code": "failed", "result_code": "ANDROID_BULK_ITEM_FAILED", "message": message})
        except (AndroidError, KeyError, LookupError, TypeError):
            return

    def get(self, identifier: str, workspace: str | None = None) -> dict[str, Any]:
        batch = self.resources.get("bulk", identifier)
        if workspace is not None and batch.get("workspaceIdentity") != workspace:
            raise AndroidError("ANDROID_BULK_NOT_FOUND", "批次不存在", 404)
        return batch

    def run(self, identifier: str, workspace: str | None = None) -> dict[str, Any]:
        batch = self.get(identifier, workspace)
        if batch["state"] in {"queued", "running"}:
            batch["state"] = "running"
        # HTTP requests run with the persistent queue started at bootstrap. Keep
        # this synchronous fallback for focused/unit callers that do not start it.
        if self.task is None:
            self._run_inline(batch)
        else:
            self.resources.save("bulk", batch)
        return batch

    def _run_inline(self, batch: dict[str, Any]) -> None:
        for item in batch["items"]:
            if item["state"] != "queued":
                continue
            try:
                device = self._get(item["deviceId"], batch.get("workspaceIdentity"))
                if int(device.get("generation", 0)) != int(item["expectedRevision"]):
                    raise AndroidError("ANDROID_REVISION_CONFLICT", "设备已发生变化，请重新创建批次", 409)
                attempt = int(item.get("attempt", 0)) + 1
                item["attempt"] = attempt
                request = {"requestId": self._request_id(batch, item, attempt), "action": batch["action"], "deleteData": batch["deleteData"]}
                if item.get("retryOf"):
                    request["retryOf"] = item["retryOf"]
                result = self.devices.operate(item["deviceId"], request)
                item.update(state="accepted", operationId=(result.get("operation") or {}).get("id"))
            except asyncio.CancelledError:
                item.update(state="needs_verification", error="操作被中断，结果未知，请核实设备状态")
                self._batch_state(batch)
                self.resources.save("bulk", batch)
                raise
            except (TimeoutError, OSError):
                item.update(state="needs_verification", error="操作结果未知，请核实设备状态")
            except AndroidError as error:
                item.update(state="failed", error=error.message)
                self._mark_failed(batch, item, error.message)
        self._batch_state(batch)
        self.resources.save("bulk", batch)

    async def tick(self) -> None:
        async with self.tick_lock:
            workspace = self._workspace_identity()
            for batch in sorted(self.resources.list("bulk"), key=lambda item: item.get("createdAt", "")):
                if workspace is not None and batch.get("workspaceIdentity") != workspace:
                    continue
                if batch.get("state") in {"succeeded", "failed", "cancelled", "partially_failed", "needs_verification"} and not any(item.get("state") in {"queued", "waiting_capacity", "waiting_device", "accepted"} for item in batch.get("items", [])):
                    continue
                await self._advance(batch)
                if any(item.get("state") == "accepted" for item in batch.get("items", [])):
                    break

    async def _advance(self, batch: dict[str, Any]) -> None:
        changed = self._reconcile(batch)
        if any(item.get("state") == "accepted" for item in batch["items"]):
            self._batch_state(batch)
            if changed:
                self.resources.save("bulk", batch)
            return
        for item in batch["items"]:
            if item.get("state") not in {"queued", "waiting_capacity", "waiting_device"}:
                continue
            try:
                device = self._get(item["deviceId"], batch.get("workspaceIdentity"))
                if int(device.get("generation", 0)) != int(item["expectedRevision"]):
                    raise AndroidError("ANDROID_REVISION_CONFLICT", "设备已发生变化，请重新创建批次", 409)
                if device.get("control") != "idle":
                    item.update(state="waiting_device", error="设备当前被占用或待核实")
                    break
                if batch["action"] in {"start", "restart"}:
                    admitted, reason = await self._capacity(device)
                    if not admitted:
                        item.update(state="waiting_capacity", error=reason)
                        break
                attempt = int(item.get("attempt", 0)) + 1
                request = {"requestId": self._request_id(batch, item, attempt), "action": batch["action"], "deleteData": batch["deleteData"]}
                if item.get("retryOf"):
                    request["retryOf"] = item["retryOf"]
                item["attempt"] = attempt
                result = self.devices.operate(item["deviceId"], request)
                item.update(state="accepted", operationId=(result.get("operation") or {}).get("id"), error=None)
                changed = True
                break
            except asyncio.CancelledError:
                item.update(state="needs_verification", error="操作被中断，结果未知，请核实设备状态")
                self._batch_state(batch)
                self.resources.save("bulk", batch)
                raise
            except (TimeoutError, OSError):
                item.update(state="needs_verification", error="操作结果未知，请核实设备状态")
                changed = True
                break
            except AndroidError as error:
                if error.code in {"ANDROID_CAPACITY", "ANDROID_MEMORY_BUDGET", "ANDROID_CPU_BUDGET", "ANDROID_CAPACITY_UNKNOWN"}:
                    item.update(state="waiting_capacity", error=error.message)
                elif error.code in {"ANDROID_BUSY", "ANDROID_RUNTIME_BUSY", "ANDROID_MANAGEMENT_BUSY", "ANDROID_RECOVERY_REQUIRED"}:
                    item.update(state="waiting_device", error=error.message)
                else:
                    item.update(state="failed", error=error.message)
                    self._mark_failed(batch, item, error.message)
                changed = True
                break
        self._batch_state(batch)
        if changed or batch.get("state") != "queued":
            self.resources.save("bulk", batch)

    async def _capacity(self, device: dict[str, Any]) -> tuple[bool, str | None]:
        checker = getattr(getattr(self.devices, "runtime", None), "capacity", None)
        if checker is None:
            return False, "容量尚未核实，不能启动批量操作"
        try:
            result = checker(device)
            if inspect.isawaitable(result):
                await result
        except AndroidError as error:
            if error.code in {"ANDROID_CAPACITY", "ANDROID_MEMORY_BUDGET", "ANDROID_CPU_BUDGET", "ANDROID_CAPACITY_UNKNOWN"}:
                return False, error.message
            raise
        except (OSError, TimeoutError, ValueError):
            return False, "容量尚未核实，不能启动批量操作"
        return True, None

    def _reconcile(self, batch: dict[str, Any]) -> bool:
        changed = False
        for item in batch["items"]:
            if item.get("state") != "accepted":
                continue
            state, message = self._operation_state(item, batch.get("workspaceIdentity"))
            if state in self._terminal_items:
                item.update(state=state, error=message)
                changed = True
        self._batch_state(batch)
        return changed

    async def verify(self, identifier: str, workspace: str | None = None) -> dict[str, Any]:
        batch = self.get(identifier, workspace)
        self._reconcile(batch)
        operations = self._operations()
        for item in batch["items"]:
            if item.get("state") not in {"accepted", "needs_verification"} or not item.get("operationId") or operations is None:
                continue
            try:
                record = self._operation_record(operations, item["operationId"], batch.get("workspaceIdentity"))
                if record.state != "needs_verification":
                    continue
                await verify_lifecycle_operation(
                    operations,
                    self.devices,
                    record,
                    workspace_identity=batch.get("workspaceIdentity") or "default",
                )
            except AndroidError as error:
                item.update(state="needs_verification", error=error.message)
            else:
                item.update(state="succeeded", error=None)
        self._batch_state(batch)
        self.resources.save("bulk", batch)
        return batch

    def _operation_state(self, item: dict[str, Any], workspace: str | None = None) -> tuple[str | None, str | None]:
        operation_id = item.get("operationId")
        operations = getattr(getattr(self.devices, "management", None), "operations", None)
        if operation_id and operations is not None:
            try:
                record = self._operation_record(operations, operation_id, workspace)
                if workspace is not None and getattr(record, "workspace_identity", workspace) != workspace:
                    return "needs_verification", "操作归属无法核实，请重新检查"
                return record.state, getattr(record, "message", None)
            except (AndroidError, AttributeError, KeyError, LookupError, TypeError):
                return "needs_verification", "操作结果未知，请核实设备状态"
        try:
            device = self._get(item["deviceId"], workspace)
        except AndroidError:
            return None, None
        operation = device.get("operation") or {}
        if operation.get("id") != operation_id:
            return None, None
        return operation.get("state"), operation.get("error") or device.get("lastError")

    @staticmethod
    def _request_id(batch: dict[str, Any], item: dict[str, Any], attempt: int) -> str:
        return f'{batch["requestId"]}:{item["deviceId"]}:{attempt}'

    @classmethod
    def _batch_state(cls, batch: dict[str, Any]) -> None:
        states = {item["state"] for item in batch["items"]}
        if states & {"queued", "waiting_capacity", "waiting_device", "accepted"}:
            batch["state"] = "running"
        elif "needs_verification" in states:
            batch["state"] = "needs_verification" if states == {"needs_verification"} else "partially_failed"
        elif "failed" in states or "cancelled" in states:
            batch["state"] = "partially_failed" if len(states) > 1 else "failed" if "failed" in states else "cancelled"
        else:
            batch["state"] = "succeeded"

    def action(self, identifier: str, action: str, request_id: str | None = None, workspace: str | None = None) -> dict[str, Any]:
        batch = self.get(identifier, workspace)
        self._reconcile(batch)
        receipts = batch.setdefault("actionReceipts", {})
        if request_id:
            previous = receipts.get(request_id)
            if previous is not None:
                if previous != action:
                    raise AndroidError("ANDROID_BULK_REQUEST_CONFLICT", "请求编号已用于不同批次动作", 409)
                return batch
        if action == "cancelPending":
            for item in batch["items"]:
                if item["state"] in {"queued", "waiting_capacity", "waiting_device"}:
                    operation_id = item.get("operationId")
                    operations = self._operations()
                    if operation_id and operations is not None:
                        try:
                            operation = self._operation_record(operations, operation_id, batch.get("workspaceIdentity"))
                            if operation.state in {"queued", "waiting_capacity"}:
                                operations.transition(operation_id, operation.state, "cancelled", {"stage_code": "cancelled", "result_code": "BULK_CANCELLED"})
                            elif operation.state not in self._terminal_items:
                                item.update(state="needs_verification", error="取消结果未知，请核实操作状态")
                                continue
                        except (AndroidError, KeyError, LookupError, TypeError) as error:
                            item.update(state="needs_verification", error=str(error)[:240] or "取消结果未知，请核实操作状态")
                            continue
                    item["state"] = "cancelled"
        elif action == "retryFailed":
            for item in batch["items"]:
                if item["state"] == "failed":
                    retry_of = item.get("operationId")
                    item.update(state="queued", operationId=None, retryOf=retry_of, error=None)
                    operations = self._operations()
                    if retry_of and operations is not None:
                        try:
                            parent = self._operation_record(operations, retry_of, batch.get("workspaceIdentity"))
                            retry = self._ensure_operation(batch, item, attempt=int(parent.attempt) + 1, retry_of=retry_of)
                            if retry is not None:
                                item["attempt"] = int(retry.attempt) - 1
                        except (AndroidError, KeyError, LookupError, TypeError) as error:
                            item.update(state="needs_verification", error=str(error)[:240] or "重试操作无法核实")
        elif action == "verify":
            self._reconcile(batch)
        else:
            raise AndroidError("ANDROID_BULK_ACTION_INVALID", "批次动作无效", 422)
        self._batch_state(batch)
        if request_id:
            receipts[request_id] = action
        self.resources.save("bulk", batch)
        return batch
