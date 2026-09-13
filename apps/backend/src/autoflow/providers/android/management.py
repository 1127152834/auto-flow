"""Fixed Docker lifecycle commands with durable completion markers and ownership checks."""
import asyncio
import json
import re
import shlex
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android.mac_runtime import LABEL, VM, docker, run

if TYPE_CHECKING:
    from autoflow.providers.android.mac_runtime import MacAndroidRuntime

IMAGE = "redroid/redroid:13.0.0_64only-latest"


async def images() -> list[dict[str, Any]]:
    try:
        item = json.loads(await docker("image", "inspect", IMAGE, timeout=5))[0]
    except (AndroidError, OSError, TimeoutError, ValueError):
        return []
    if item.get("Architecture") != "arm64" or item.get("Os") != "linux":
        return []
    return [{"id": item["Id"], "name": "Android 13 标准 · ARM64", "reference": IMAGE}]


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


async def mutation(device: dict[str, Any], save: Callable[[], None], *args: str, timeout: float = 40) -> bytes:
    marker = "/tmp/autoflow-lifecycle-" + uuid4().hex
    device["pendingLifecycle"] = marker
    save()
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


async def capacity(device: dict[str, Any]) -> None:
    info = json.loads(await docker("info", "--format", "{{json .}}"))
    ids = (await docker("ps", "-q")).decode().split()
    allocated = 0
    if ids:
        for obj in json.loads(await docker("inspect", *ids)):
            if obj["Id"] != device["containerId"]:
                allocated += obj["HostConfig"].get("Memory", 0)
    # CPU is a quota, shared by scheduling; do not promise dedicated CPU cores.
    if device.get("cpu", 1) > info["NCPU"] or allocated + device.get("memoryMb", 1536) * 1024 * 1024 > info["MemTotal"] - 512 * 1024 * 1024:
        raise AndroidError("ANDROID_CAPACITY", "运行环境内存预算不足或 CPU 配额过大，请停止空闲设备或降低新实例配置", 422)


async def manage(runtime: "MacAndroidRuntime", device: dict[str, Any], request: dict[str, Any], stage: Callable[[str], None], save: Callable[[], None]) -> None:
    action = request["action"]
    await confirm_pending(device)
    containers, volumes = await verify(device, runtime.workspace_id)
    if action == "recover":
        stage("核实遗留操作")
        await runtime.recover(device)
        device["androidStatus"] = (await runtime.inspect(device))["androidStatus"] if containers else "retained" if volumes else "missing"
        device["dataRetained"] = not containers and bool(volumes)
        return
    if action == "delete":
        stage("移除实例运行环境")
        if containers:
            await mutation(device, save, "rm", "-f", device["containerId"])
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
            await mutation(device, save, "stop", "--time", "10", device["containerId"])
        device["androidStatus"] = (await runtime.inspect(device))["androidStatus"] if containers else "retained" if volumes else "missing"
        if containers and device["androidStatus"] != "stopped":
            raise AndroidError("ANDROID_STOP_FAILED", "Android 尚未停止")
        return
    if action == "create" or not containers:
        stage("检查镜像与配置")
        if not any(item["id"] == device["imageId"] for item in await images()):
            raise AndroidError("ANDROID_IMAGE_UNAVAILABLE", "请选择已缓存的 Android 13 ARM64 标准镜像", 422)
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
    await capacity(device)
    await runtime.inspect(device)
    stage("启动 Android" if action != "restart" else "重启 Android")
    device["androidStatus"] = "starting"
    await mutation(device, save, "restart" if action == "restart" else "start", device["containerId"])
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        observation = await runtime.inspect(device)
        if observation["androidStatus"] == "ready":
            device["androidStatus"] = "ready"
            return
        await asyncio.sleep(1)
    raise AndroidError("ANDROID_BOOT_TIMEOUT", "Android 未在180秒内就绪，请检查实例状态", 504)
