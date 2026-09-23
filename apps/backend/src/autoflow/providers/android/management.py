"""Fixed Docker lifecycle commands with durable completion markers and ownership checks."""
import asyncio
import json
import re
import shlex
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from autoflow.domain.android.capacity_rules import can_admit
from autoflow.domain.android.management_rules import require_restored, restore_pending
from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android import capacity_reservations as reservations
from autoflow.providers.android.mac_runtime import LABEL, VM, docker, run

if TYPE_CHECKING:
    from autoflow.providers.android.mac_runtime import MacAndroidRuntime

IMAGE = "redroid/redroid:13.0.0_64only-latest"


async def images(reference: str | None = None) -> list[dict[str, Any]]:
    """Return cached compatible images, optionally for one immutable local ID."""
    target = reference or IMAGE
    try:
        item = json.loads(await docker("image", "inspect", target, timeout=5))[0]
    except (AndroidError, OSError, TimeoutError, ValueError):
        return []
    image_id = str(item.get("Id") or "")
    if (
        not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)
        or item.get("Architecture") not in {"arm64", "aarch64"}
        or item.get("Os") != "linux"
    ):
        return []
    if reference and image_id != reference:
        return []
    return [{
        "id": image_id,
        "name": "Android 13 标准 · ARM64" if not reference else "Android ARM64 镜像",
        "reference": target,
    }]


async def _admit_image(runtime: "MacAndroidRuntime", image_id: str) -> None:
    catalog = getattr(runtime, "image_catalog", None)
    if catalog is not None:
        records = [item for item in catalog.list() if item.get("imageId") == image_id]
        if not records or records[0].get("state") in {"deleted", "unregistered"}:
            raise AndroidError("ANDROID_IMAGE_UNAVAILABLE", "镜像未在当前工作区登记，或已取消登记", 422)
    if not any(item.get("id") == image_id for item in await images(image_id)):
        raise AndroidError("ANDROID_IMAGE_UNAVAILABLE", "请选择已缓存且通过 Linux ARM64 检查的镜像", 422)


async def objects(kind: str, name: str) -> list[dict[str, Any]]:
    # Enumerate before inspect: a failed daemon query is never mistaken for missing data.
    argv = ("volume", "ls", "--format", "{{.Name}}") if kind == "volume" else ("ps", "-a", "--no-trunc", "--format", "{{.ID}} {{.Names}}")
    lines = (await docker(*argv)).decode().splitlines()
    exists = name in lines if kind == "volume" else any(name in line.split() for line in lines)
    if not exists:
        return []
    return json.loads(await docker(*(("volume", "inspect", name) if kind == "volume" else ("inspect", name))))


def owned(obj: dict[str, Any], device: dict[str, Any], workspace_id: str, kind: str) -> None:
    labels = obj.get("Labels") if kind == "volume" else obj.get("Config", {}).get("Labels")
    if device["workspaceId"] != workspace_id or not labels or labels.get(LABEL) != workspace_id or labels.get("io.autoflow.android.device") != device["deviceId"]:
        raise AndroidError("ANDROID_OWNERSHIP", "设备或数据卷归属校验失败", 403)
    if kind != "volume" and not any(m.get("Name") == device["volumeId"] and m.get("Destination") == "/data" for m in obj.get("Mounts", [])):
        raise AndroidError("ANDROID_OWNERSHIP", "设备数据卷挂载不符", 403)


async def verify(device: dict[str, Any], workspace_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    containers = await objects("container", device["containerId"])
    volumes = await objects("volume", device["volumeId"])
    for kind, entries in (("container", containers), ("volume", volumes)):
        for item in entries:
            owned(item, device, workspace_id, kind)
    return containers, volumes


async def mutation(device: dict[str, Any], save: Callable[[], None], *args: str, timeout: float = 40, reservation_root: Path | None = None, memory: int | None = None) -> bytes:
    marker = "/tmp/autoflow-lifecycle-" + uuid4().hex
    device["pendingLifecycle"] = marker
    save()
    if reservation_root is not None:
        try:
            reservations.reserve(reservation_root, device, marker, memory)
        except BaseException:
            # No command was dispatched. Remove only this attempt's reservation.
            reservations.release(reservation_root, device, marker)
            device.pop('pendingLifecycle', None)
            save()
            raise
    command = shlex.join(["docker", *args]) + "; rc=$?; echo $rc > " + marker + "; exit $rc"
    result = await run(["limactl", "shell", "--workdir=/tmp", VM, "sudo", "sh", "-c", command], timeout)
    device.pop("pendingLifecycle", None)
    save()
    return result


async def confirm_pending(device: dict[str, Any]) -> None:
    marker = device.get("pendingLifecycle")
    if not marker:
        return
    if not re.fullmatch(r"/tmp/autoflow-lifecycle-[0-9a-f]{32}", marker):
        raise AndroidError("ANDROID_RECOVERY_REQUIRED", "设备操作记录无效")
    try:
        result = await run(["limactl", "shell", "--workdir=/tmp", VM, "sudo", "cat", marker], 5)
    except (AndroidError, OSError, TimeoutError):
        raise AndroidError("ANDROID_RECOVERY_REQUIRED", "上次设备命令尚未确认结束，请稍后重新核实") from None
    if not re.fullmatch(rb"[0-9]+\s*", result):
        raise AndroidError("ANDROID_RECOVERY_REQUIRED", "上次设备命令的完成状态未知")
    device.pop("pendingLifecycle", None)


async def capacity(device: dict[str, Any], root: Path | None = None, *, minimum_memory: int = 0) -> None:
    pending = reservations.load(root) if root is not None else {}
    try:
        info = json.loads(await docker("info", "--format", "{{json .}}"))
        total_cpu = info.get("NCPU")
        total_memory = info.get("MemTotal")
    except (AndroidError, OSError, TimeoutError, ValueError, TypeError, AttributeError) as error:
        raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "运行环境容量尚未核实，不能启动实例", 409) from error
    if (
        isinstance(total_cpu, bool)
        or not isinstance(total_cpu, int)
        or total_cpu <= 0
        or isinstance(total_memory, bool)
        or not isinstance(total_memory, int)
        or total_memory <= 0
    ):
        raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "运行环境容量尚未核实，不能启动实例", 409)
    allocated = 0
    running = {}
    try:
        ids = (await docker("ps", "-q", "--no-trunc")).decode().split()
        if ids:
            records = json.loads(await docker("inspect", *ids))
            if not isinstance(records, list) or len(records) != len(ids) or {obj["Id"] for obj in records} != set(ids):
                raise ValueError("incomplete running container inventory")
            for obj in records:
                running[obj['Id']] = obj
                memory = obj.get("HostConfig", {}).get("Memory")
                # Docker's zero limit means unlimited, not zero consumption.
                if type(memory) is not int or memory <= 0:
                    raise ValueError("unknown memory allocation")
                if obj["Id"] != device["containerId"]:
                    allocated += memory
                else:
                    minimum_memory = max(minimum_memory, memory)
        for item in pending.values():
            memory = item['memoryBytes']
            if memory is None:
                raise ValueError('unknown pending memory allocation')
            obj = running.get(item['containerId'])
            if obj is not None:
                labels = obj.get('Config', {}).get('Labels', {})
                if labels.get(LABEL) != item['workspaceId'] or labels.get('io.autoflow.android.device') != item['deviceId']:
                    raise ValueError('pending container ownership changed')
                actual = obj.get('HostConfig', {}).get('Memory')
                if type(actual) is not int or actual <= 0:
                    raise ValueError('unknown pending container allocation')
                memory = max(0, memory - actual)
            allocated += memory
    except (AndroidError, OSError, TimeoutError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "运行环境容量尚未核实，不能启动实例", 409) from error
    # CPU is a quota, shared by scheduling; do not promise dedicated CPU cores.
    requested_cpu = device.get("cpu", 1)
    requested_memory = device.get("memoryMb", 1536)
    if (
        isinstance(requested_cpu, bool)
        or not isinstance(requested_cpu, int)
        or requested_cpu <= 0
        or isinstance(requested_memory, bool)
        or not isinstance(requested_memory, int)
        or requested_memory <= 0
    ):
        raise AndroidError("ANDROID_CAPACITY_UNKNOWN", "实例容量配置尚未核实，不能启动实例", 409)
    if requested_cpu > total_cpu or not can_admit(total_memory, allocated, 0, max(requested_memory * 1024 * 1024, minimum_memory)):
        raise AndroidError("ANDROID_CAPACITY", "运行环境内存预算不足或 CPU 配额过大，请停止空闲设备或降低新实例配置", 422)


async def manage(runtime: "MacAndroidRuntime", device: dict[str, Any], request: dict[str, Any], stage: Callable[[str], None], save: Callable[[], None]) -> None:
    await _manage(runtime, device, request, stage, save)
    pending = reservations.pending(runtime.root, device)
    if pending:
        reservations.release(runtime.root, device, pending['marker'])


async def _manage(runtime: "MacAndroidRuntime", device: dict[str, Any], request: dict[str, Any], stage: Callable[[str], None], save: Callable[[], None]) -> None:
    action = request["action"]
    if restore_pending(device) and (action not in {"create", "recover", "delete"} or (action == "delete" and not request.get("deleteData")) or (action == "create" and device.get("creationConfig", {}).get("start", True))):
        require_restored(device)
    await confirm_pending(device)
    containers, volumes = await verify(device, runtime.workspace_id)
    pending = reservations.pending(runtime.root, device)
    if pending:
        await confirm_pending({'pendingLifecycle': pending['marker']})
        reservations.release(runtime.root, device, pending['marker'])
    if containers and device['containerId'] != containers[0].get('Id'):
        identifier = containers[0].get('Id')
        if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{64}', identifier):
            raise AndroidError('ANDROID_CAPACITY_UNKNOWN', '实例容器身份尚未核实', 409)
        device['containerId'] = identifier
        save()
    memory = containers[0].get('HostConfig', {}).get('Memory') if containers else None
    if type(memory) is not int or memory <= 0:
        memory = None
    if action == "recover":
        stage("核实遗留操作")
        await _admit_image(runtime, device["imageId"])
        await runtime.recover(device)
        device["androidStatus"] = (await runtime.inspect(device))["androidStatus"] if containers else "retained" if volumes else "missing"
        device["dataRetained"] = not containers and bool(volumes)
        return
    if action == "delete":
        stage("移除实例运行环境")
        if containers:
            await mutation(device, save, "rm", "-f", device["containerId"], reservation_root=runtime.root, memory=memory)
        if await objects("container", device["containerId"]):
            raise AndroidError("ANDROID_DELETE_FAILED", "实例运行环境尚未移除")
        # Recheck volume ownership immediately before deletion, including retries.
        _, volumes = await verify(device, runtime.workspace_id)
        if request["deleteData"] and volumes:
            stage("清理独立数据")
            await mutation(device, save, "volume", "rm", device["volumeId"])
        if request["deleteData"] and await objects("volume", device["volumeId"]):
            raise AndroidError("ANDROID_DELETE_FAILED", "独立数据尚未清理")
        device.update(deleted=request["deleteData"] or not volumes, dataRetained=not request["deleteData"] and bool(volumes), androidStatus="retained" if volumes and not request["deleteData"] else "missing")
        return
    if action == "stop":
        stage("停止 Android，保留数据")
        if containers:
            await mutation(device, save, "stop", "--time", "10", device["containerId"], reservation_root=runtime.root, memory=memory)
        device["androidStatus"] = (await runtime.inspect(device))["androidStatus"] if containers else "retained" if volumes else "missing"
        if containers and device["androidStatus"] != "stopped":
            raise AndroidError("ANDROID_STOP_FAILED", "Android 尚未停止")
        return
    if action == "create" or not containers:
        stage("检查镜像与配置")
        await _admit_image(runtime, device["imageId"])
        if action != "create" and not volumes:
            raise AndroidError("ANDROID_DATA_MISSING", "原数据卷不存在，不能以空白数据冒充恢复；请新建实例", 409)
        if not volumes:
            stage("创建独立数据")
            await mutation(device, save, "volume", "create", "--label", LABEL + "=" + runtime.workspace_id, "--label", "io.autoflow.android.device=" + device["deviceId"], device["volumeId"])
        stage("创建实例")
        device["containerId"] = "autoflow-android-" + device["deviceId"]
        save()  # A lost create response must remain discoverable by its intended name.
        output = await mutation(device, save, "create", "--name", "autoflow-android-" + device["deviceId"], "--privileged", "--cpus", str(device.get("cpu", 1)), "--memory", str(device.get("memoryMb", 1536)) + "m", "--label", LABEL + "=" + runtime.workspace_id, "--label", "io.autoflow.android.device=" + device["deviceId"], "-v", device["volumeId"] + ":/data", "-p", "127.0.0.1::5555", device["imageId"], "androidboot.redroid_gpu_mode=guest", "androidboot.redroid_width=" + str(device["width"]), "androidboot.redroid_height=" + str(device["height"]), "androidboot.redroid_dpi=" + str(device.get("dpi", 320)))
        device.update(containerId=output.decode().strip(), dataRetained=False)
        save()
    if action == "create" and not device["creationConfig"]["start"]:
        device["androidStatus"] = "stopped"
        return
    containers, _ = await verify(device, runtime.workspace_id)
    memory = containers[0].get('HostConfig', {}).get('Memory') if containers else None
    if type(memory) is not int or memory <= 0:
        raise AndroidError('ANDROID_CAPACITY_UNKNOWN', '实例实际内存限额尚未核实，不能启动', 409)
    await capacity(device, runtime.root, minimum_memory=memory)
    await runtime.inspect(device)
    stage("启动 Android" if action != "restart" else "重启 Android")
    device["androidStatus"] = "starting"
    memory = max(memory or 0, device.get('memoryMb', 1536) * 1024**2)
    await mutation(device, save, "restart" if action == "restart" else "start", device["containerId"], reservation_root=runtime.root, memory=memory)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        observation = await runtime.inspect(device)
        if observation["androidStatus"] == "ready":
            if device.get("profileId") and not device.get("configurationApplied"):
                stage("应用语言与时区")
                script = shlex.join(["setprop", "persist.sys.locale", device["locale"]]) + "; " + shlex.join(["setprop", "persist.sys.timezone", device["timezone"]]) + "; setprop sys.boot_completed 0; stop; start"
                await mutation(device, save, "exec", device["containerId"], "sh", "-c", script)
                device["configurationApplied"] = True
                save()
                await asyncio.sleep(2)
                continue
            device["androidStatus"] = "ready"
            return
        await asyncio.sleep(1)
    raise AndroidError("ANDROID_BOOT_TIMEOUT", "Android 未在180秒内就绪，请检查实例状态", 504)
