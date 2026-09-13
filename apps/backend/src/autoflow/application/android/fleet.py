"""Persistent batches and device allocation, using the existing manager and run engine."""

import asyncio
import logging
from copy import deepcopy
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.android.management import now
from autoflow.domain.android.ports import AndroidError
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import prepare_run, validate_runtime
from autoflow.domain.workflows.runs import ACTIVE_RUN_STATES


class AndroidFleet:
    def __init__(
        self, devices: AndroidDeviceService, resources: Any, workflows: Any, runs: Any
    ) -> None:
        self.devices, self.resources, self.workflows, self.runs = (
            devices,
            resources,
            workflows,
            runs,
        )
        self.task: asyncio.Task[None] | None = None
        self.closing = False
        self.tick_lock = asyncio.Lock()

    async def start(self) -> None:
        self.closing = False
        self.task = asyncio.create_task(self._loop(), name="android-allocation-queue")

    async def shutdown(self) -> None:
        self.closing = True
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    def busy(self) -> bool:
        return any(
            item["state"] not in {"succeeded", "failed", "cancelled"}
            for kind in ("batch", "allocation")
            for item in self.resources.list(kind)
        )

    async def profiles(self) -> list[dict[str, Any]]:
        profiles = self.resources.list("profile")
        if profiles:
            return profiles
        environment = await self.devices.environment()
        if environment.get("images"):
            item = {
                "id": str(uuid5(NAMESPACE_URL, "autoflow:android:default-profile")),
                "revision": 1,
                "name": "Android 13 标准 · ARM64",
                "imageId": environment["images"][0]["id"],
                "width": 720,
                "height": 1280,
                "dpi": 320,
                "cpu": 1,
                "memoryMb": 1536,
                "locale": "zh-CN",
                "timezone": "Asia/Shanghai",
                "shellRoot": "unknown",
                "applicationRoot": "unknown",
            }
            self.resources.save("profile", item)
            return [item]
        return []

    def save_profile(self, item: dict[str, Any]) -> dict[str, Any]:
        try:
            existing = self.resources.get("profile", item["id"])
        except AndroidError as error:
            if error.status != 404:
                raise
            existing = None
        if (existing and existing["revision"] != item["revision"]) or (
            not existing and item["revision"] != 0
        ):
            raise AndroidError("ANDROID_PROFILE_CONFLICT", "环境配置已更新，请重新加载")
        saved = {
            **item,
            "revision": item["revision"] + 1,
            "shellRoot": "unknown",
            "applicationRoot": "unknown",
        }
        self.resources.save("profile", saved)
        return saved

    def _existing(
        self, kind: str, identifier: str, request: dict[str, Any]
    ) -> dict[str, Any] | None:
        try:
            existing = self.resources.get(kind, identifier)
        except AndroidError as error:
            if error.status == 404:
                return None
            raise
        if existing["request"] != request:
            raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于不同内容")
        return existing

    def batch(self, request: dict[str, Any]) -> dict[str, Any]:
        existing = self._existing("batch", request["batchId"], request)
        if existing:
            return existing
        profile = self.resources.get("profile", request["profileId"])
        if profile["revision"] != request["profileRevision"]:
            raise AndroidError("ANDROID_PROFILE_CONFLICT", "环境配置已更新，请重新加载")
        items = [
            {
                "deviceId": str(uuid4()),
                "name": f"{request['name']} {i + 1:02d}",
                "state": "waiting_create",
                "error": None,
            }
            for i in range(request["quantity"])
        ]
        result = {
            "id": request["batchId"],
            "createdAt": now(),
            "request": request,
            "profile": profile,
            "items": items,
            "state": "queued",
        }
        self.resources.save("batch", result)
        return result

    def batch_action(self, identifier: str, action: str) -> dict[str, Any]:
        batch = self.resources.get("batch", identifier)
        for item in batch["items"]:
            if action == "cancel" and item["state"] in {
                "waiting_create",
                "waiting_start",
                "waiting_capacity",
            }:
                item["state"] = "cancelled"
            elif action == "retry" and item["state"] == "failed":
                item.update(state="waiting_create", error=None)
        self._batch_state(batch)
        self.resources.save("batch", batch)
        return batch

    def allocate(self, request: dict[str, Any]) -> dict[str, Any]:
        existing = self._existing("allocation", request["requestId"], request)
        if existing:
            return existing
        profile = self.resources.get("profile", request["profileId"])
        workflow = self.workflows.get(request["workflowId"])
        if workflow is None:
            raise AndroidError(
                "ANDROID_WORKFLOW_NOT_FOUND", "请选择已保存的安卓工作流", 404
            )
        document = deepcopy(workflow.document)
        names = {item["name"] for item in document.get("variables", [])}
        if set(request.get("values", {})) - names:
            raise AndroidError(
                "ANDROID_VARIABLE_UNKNOWN", "流程输入包含未定义变量", 422
            )
        for variable in document.get("variables", []):
            if variable["name"] in request.get("values", {}):
                variable["value"] = request["values"][variable["name"]]
        validate_runtime(prepare_run(document, workflow.layout).document, True)
        if request["mode"] == "specified":
            device = self.devices.repository.get(request["deviceId"])
            if device.get("deleted") or device["imageId"] != profile["imageId"]:
                raise AndroidError(
                    "ANDROID_PROFILE_MISMATCH", "设备与所需环境不兼容", 422
                )
        allocation = {
            "id": request["requestId"],
            "createdAt": now(),
            "request": request,
            "profile": profile,
            "document": document,
            "layout": deepcopy(workflow.layout),
            "workflowName": document["name"],
            "profileName": profile["name"],
            "state": "waiting_create"
            if request["mode"] == "temporary"
            else "waiting_device",
            "deviceId": request.get("deviceId"),
            "deviceName": None,
            "runId": str(uuid4()),
            "error": None,
        }
        if request["mode"] == "temporary":
            bid = str(
                uuid5(
                    NAMESPACE_URL, "autoflow:android:allocation:" + request["requestId"]
                )
            )
            batch = self.batch(
                {
                    "batchId": bid,
                    "name": document["name"],
                    "profileId": profile["id"],
                    "profileRevision": profile["revision"],
                    "quantity": 1,
                    "instanceType": "temporary",
                    "start": True,
                    "width": profile["width"],
                    "height": profile["height"],
                    "locale": profile["locale"],
                    "timezone": profile["timezone"],
                }
            )
            allocation.update(batchId=bid, deviceId=batch["items"][0]["deviceId"])
        self.resources.save("allocation", allocation)
        return allocation

    def cancel_allocation(self, identifier: str) -> dict[str, Any]:
        allocation = self.resources.get("allocation", identifier)
        if allocation["state"] in {"running", "cleaning"}:
            raise AndroidError(
                "ANDROID_ALLOCATION_RUNNING", "任务已经运行，请从运行详情停止"
            )
        if allocation.get("batchId"):
            self.batch_action(allocation["batchId"], "cancel")
        allocation["state"] = "cancelled"
        self.resources.save("allocation", allocation)
        return allocation

    async def _loop(self) -> None:
        while not self.closing:
            try:
                await self.tick()
            except Exception:
                logging.getLogger(__name__).exception("Android queue tick failed")
            await asyncio.sleep(1)

    async def tick(self) -> None:
        async with self.tick_lock:
            if self.devices.management.busy():
                return
            for batch in self.resources.list("batch"):
                if batch["state"] not in {"succeeded", "failed", "cancelled"}:
                    await self._batch_step(batch)
                    if self.devices.management.busy():
                        return
            for allocation in self.resources.list("allocation"):
                if allocation["state"] not in {"succeeded", "failed", "cancelled"}:
                    await self._allocation_step(allocation)
                    if self.devices.management.busy():
                        return

    @staticmethod
    def _batch_state(batch: dict[str, Any]) -> None:
        states = {item["state"] for item in batch["items"]}
        batch["state"] = (
            "running"
            if states - {"succeeded", "failed", "cancelled"}
            else "failed"
            if "failed" in states
            else "cancelled"
            if "cancelled" in states
            else "succeeded"
        )

    async def _batch_step(self, batch: dict[str, Any]) -> None:
        for item in batch["items"]:
            if item["state"] in {"succeeded", "failed", "cancelled"}:
                continue
            try:
                await self._device_step(batch, item)
            except (AndroidError, WorkflowError) as error:
                item.update(state="failed", error=error.message)
            self._batch_state(batch)
            self.resources.save("batch", batch)
            if self.devices.management.busy():
                return

    async def _device_step(self, batch: dict[str, Any], item: dict[str, Any]) -> None:
        try:
            device = self.devices.repository.get(item["deviceId"])
        except AndroidError as error:
            if error.status != 404:
                raise
            profile, request = batch["profile"], batch["request"]
            config = {
                key: profile[key] for key in ("imageId", "dpi", "cpu", "memoryMb")
            }
            config.update(
                deviceId=item["deviceId"],
                name=item["name"],
                width=request["width"],
                height=request["height"],
                start=False,
                profileId=profile["id"],
                profileName=profile["name"],
                instanceType=request["instanceType"],
                locale=request["locale"],
                timezone=request["timezone"],
            )
            self.devices.management.create(config)
            item["state"] = "creating"
            return
        if device["control"] == "managing":
            return
        if (
            device["control"] == "recovery_required"
            and item["state"] == "waiting_create"
        ):
            self.devices.management.operate(
                device["deviceId"],
                {"requestId": str(uuid4()), "action": "recover", "deleteData": False},
            )
            item["state"] = "recovering"
            return
        if device["control"] == "recovery_required":
            raise AndroidError(
                "ANDROID_BATCH_ITEM_FAILED", device.get("lastError") or "设备需要核实"
            )
        if device.get("deleted"):
            raise AndroidError(
                "ANDROID_BATCH_ITEM_DELETED", "实例已删除，不能重用原编号"
            )
        observation = await self.devices.runtime.inspect(device)
        if not batch["request"]["start"] or observation["androidStatus"] == "ready":
            item.update(state="succeeded", error=None)
            return
        item["state"] = "waiting_start"
        if not await self._capacity(device):
            item["state"] = "waiting_capacity"
            return
        self.devices.management.operate(
            device["deviceId"],
            {"requestId": str(uuid4()), "action": "start", "deleteData": False},
        )
        item["state"] = "starting"

    async def _capacity(self, device: dict[str, Any]) -> bool:
        check = getattr(self.devices.runtime, "capacity", None)
        if check:
            try:
                await check(device)
            except AndroidError as error:
                if error.code in {
                    "ANDROID_CAPACITY",
                    "ANDROID_MEMORY_BUDGET",
                    "ANDROID_CPU_BUDGET",
                }:
                    return False
                raise
        return True

    async def _allocation_step(self, item: dict[str, Any]) -> None:
        try:
            await self._advance_allocation(item)
        except (AndroidError, WorkflowError) as error:
            if error.code in {
                "ANDROID_BUSY",
                "ANDROID_RUNTIME_BUSY",
                "ANDROID_MANAGEMENT_BUSY",
                "WORKFLOW_RUN_BUSY",
            }:
                item["state"] = "waiting_device"
            else:
                item.update(state="failed", error=error.message)
        self.resources.save("allocation", item)

    async def _advance_allocation(self, item: dict[str, Any]) -> None:
        try:
            record = self.runs.get(item["runId"])
        except WorkflowError as error:
            if error.status != 404:
                raise
            record = None
        if record:
            if record["state"] in ACTIVE_RUN_STATES:
                item["state"] = "running"
                return
            completed_device = self.devices.repository.get(item["deviceId"])
            if (
                record["state"] == "succeeded"
                and completed_device.get("instanceType") == "temporary"
            ):
                item["state"] = "cleaning"
                if completed_device.get("deleted"):
                    item["state"] = "succeeded"
                elif completed_device["control"] == "idle":
                    self.devices.management.operate(
                        completed_device["deviceId"],
                        {
                            "requestId": item["id"],
                            "action": "delete",
                            "deleteData": True,
                        },
                    )
                elif completed_device["control"] == "recovery_required":
                    raise AndroidError(
                        "ANDROID_CLEANUP_FAILED", "临时实例回收失败，请核实设备"
                    )
            else:
                item.update(
                    state="succeeded" if record["state"] == "succeeded" else "failed",
                    error=(record.get("error") or {}).get("message"),
                )
            return
        if item.get("batchId"):
            batch = self.resources.get("batch", item["batchId"])
            if batch["state"] == "failed":
                raise AndroidError(
                    "ANDROID_CREATION_FAILED",
                    batch["items"][0].get("error") or "临时实例创建失败",
                )
            if batch["state"] != "succeeded":
                item["state"] = batch["items"][0]["state"]
                return
        devices = await self.devices.devices()
        if not item.get("deviceId"):
            candidate = next(
                (
                    d
                    for d in devices
                    if d["control"] == "idle"
                    and d["androidStatus"] == "ready"
                    and d["imageId"] == item["profile"]["imageId"]
                ),
                None,
            )
            if not candidate:
                item["state"] = "waiting_device"
                return
            item["deviceId"] = candidate["deviceId"]
            self.resources.save("allocation", item)
        device = next((d for d in devices if d["deviceId"] == item["deviceId"]), None)
        if device is None:
            raise AndroidError("ANDROID_NOT_FOUND", "等待中的设备不存在", 404)
        item["deviceName"] = device["name"]
        if device["control"] != "idle":
            item["state"] = "waiting_device"
            return
        if device["androidStatus"] != "ready":
            item["state"] = "waiting_start"
            if device["androidStatus"] == "stopped" and await self._capacity(device):
                self.devices.management.operate(
                    device["deviceId"],
                    {"requestId": str(uuid4()), "action": "start", "deleteData": False},
                )
            return
        await self.runs.start(
            item["runId"],
            item["document"],
            item["layout"],
            None,
            target={"kind": "android", "deviceId": device["deviceId"]},
        )
        item["state"] = "running"
