import asyncio
import hashlib
import json
import os
import platform
import plistlib
import re
import select
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock
from autoflow.infrastructure.process.browser_processes import process_birth
from autoflow.infrastructure.process.test_browser_worker import _wait_for_spawn

VM = "autoflow-redroid"
VENDOR = "scrcpy-macos-aarch64-v3.3.4"
ARCHIVE_SHA = "8fef43520405dd523c74e1530ac68febcc5a405ea89712c874936675da8513dd"
LABEL = "io.autoflow.android.workspace"


async def run(argv: list[str], timeout: float = 15, input_data: bytes | None = None) -> bytes:
    spawn = asyncio.create_task(asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE if input_data is not None else None, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE))
    try:
        process = await asyncio.shield(spawn)
    except asyncio.CancelledError:
        process = await _wait_for_spawn(spawn)
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(input_data), timeout)
        if process.returncode:
            detail = stderr.decode(errors="replace").strip()
            message = "安卓运行环境命令失败，请检查设备与连接"
            if detail:
                message += ": " + detail[:240]
            raise AndroidError("ANDROID_COMMAND_FAILED", message, 502)
        return stdout
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def docker(*args: str, timeout: float = 30, input_data: bytes | None = None) -> bytes:
    return await run(["limactl", "shell", "--workdir=/tmp", VM, "sudo", "docker", *args], timeout, input_data)


def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise AndroidError("ANDROID_SCREEN_INVALID", "设备未返回有效 PNG", 502)
    return struct.unpack(">II", data[16:24])


def package_inventory(data: bytes) -> dict[str, int | None]:
    packages: dict[str, int | None] = {}
    for line in data.decode(errors="replace").splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"package:([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*)(?: versionCode:(\d+))?", line.strip())
        if match is None:
            raise AndroidError("ANDROID_APP_INFO_UNKNOWN", "无法核实已安装应用，请重新读取", 502)
        packages[match[1]] = int(match[2]) if match[2] else None
    return packages


class MacAndroidRuntime:
    def __init__(self, root: Path, workspace: Path) -> None:
        self.root = root
        self.workspace = workspace
        self.workspace_id = hashlib.sha256(str(workspace.resolve()).encode()).hexdigest()
        self._lock = ExclusiveFileLock(root / (VM + ".lock"))
        self._locked = False
        self.serial: str | None = None
        self.tunnel: subprocess.Popen[bytes] | None = None
        self.viewer: subprocess.Popen[bytes] | None = None
        self.terminal: int | None = None
        self.device: dict[str, Any] | None = None
        self.save: Callable[[], None] = lambda: None
        self.image_catalog: Any | None = None

    def for_device(self, device_id: str) -> "MacAndroidRuntime":
        device_id = str(__import__("uuid").UUID(device_id))
        runtime = MacAndroidRuntime(self.root, self.workspace)
        runtime._lock = ExclusiveFileLock(self.root / (VM + "-" + device_id + ".lock"))
        runtime.image_catalog = self.image_catalog
        return runtime

    async def environment(self) -> dict[str, Any]:
        supported = platform.system() == "Darwin" and platform.machine() == "arm64"
        tool_state = {tool: bool(shutil.which(tool)) for tool in ("adb", "limactl", "ssh")}
        tools = all(tool_state.values())
        vendor = (self.root / VENDOR / "scrcpy").is_file()
        info: dict[str, Any] = {}
        checks: dict[str, dict[str, Any]] = {}
        checks["platform"] = {"status": "pass" if supported else "unsupported", "code": None if supported else "ANDROID_PLATFORM_UNSUPPORTED", "message": "平台支持" if supported else "当前平台不支持安卓运行时"}
        for tool, present in tool_state.items():
            name = "lima" if tool == "limactl" else tool
            checks[name] = {"status": "pass" if present else "fail", "code": None if present else "ANDROID_TOOL_MISSING", "message": "工具可用" if present else f"缺少 {name}"}
        checks["scrcpy"] = {"status": "pass" if vendor else "fail", "code": None if vendor else "ANDROID_SCRCPY_MISSING", "message": "固定版 scrcpy 可用" if vendor else "固定版 scrcpy 不存在"}
        vm_running = False
        if supported and tool_state["limactl"]:
            try:
                listing = await run(["limactl", "list"], 5)
                vm_running = any(line.split()[:2] == [VM, "Running"] for line in listing.decode(errors="replace").splitlines())
                checks["vm"] = {"status": "pass" if vm_running else "fail", "code": None if vm_running else "ANDROID_VM_STOPPED", "message": "Lima 虚拟机运行中" if vm_running else "Lima 虚拟机未运行"}
            except (AndroidError, TimeoutError, OSError):
                checks["vm"] = {"status": "unknown", "code": "ANDROID_VM_UNKNOWN", "message": "无法核实 Lima 虚拟机状态"}
        else:
            checks["vm"] = {"status": "unsupported" if not supported else "unknown", "code": "ANDROID_VM_UNAVAILABLE", "message": "无法检查 Lima 虚拟机"}
        if vm_running:
            try:
                info = json.loads(await docker("info", "--format", "{{json .}}", timeout=5))
                docker_ok = info.get("OSType") == "linux" and info.get("Architecture") in {"aarch64", "arm64"}
                checks["docker"] = {"status": "pass" if docker_ok else "fail", "code": None if docker_ok else "ANDROID_DOCKER_INCOMPATIBLE", "message": "Linux ARM64 Docker 可用" if docker_ok else "Docker 不是兼容的 Linux ARM64"}
            except (AndroidError, TimeoutError, OSError, ValueError):
                checks["docker"] = {"status": "fail", "code": "ANDROID_DOCKER_UNAVAILABLE", "message": "Docker 守护进程不可访问"}
        else:
            checks["docker"] = {"status": "unknown", "code": "ANDROID_DOCKER_UNKNOWN", "message": "虚拟机未运行，无法检查 Docker"}
        binder = False
        if vm_running:
            try:
                filesystems = await run(["limactl", "shell", "--workdir=/tmp", VM, "cat", "/proc/filesystems"], 5)
                binder = b"binder" in filesystems
                checks["binder"] = {"status": "pass" if binder else "fail", "code": None if binder else "ANDROID_BINDER_MISSING", "message": "Android binder 可用" if binder else "未发现 Android binder"}
            except (AndroidError, TimeoutError, OSError):
                checks["binder"] = {"status": "unknown", "code": "ANDROID_BINDER_UNKNOWN", "message": "无法核实 Android binder"}
        else:
            checks["binder"] = {"status": "unknown", "code": "ANDROID_BINDER_UNKNOWN", "message": "虚拟机未运行，无法检查 binder"}
        from autoflow.providers.android.management import images

        cached = await images() if info else []
        checks["images"] = {"status": "pass" if cached else "fail" if info else "unknown", "code": None if cached else "ANDROID_IMAGE_MISSING" if info else "ANDROID_IMAGE_UNKNOWN", "message": "已发现兼容镜像" if cached else "未发现兼容镜像" if info else "尚未检查镜像"}
        capacity_ok = isinstance(info.get("NCPU"), int) and info.get("NCPU", 0) > 0 and isinstance(info.get("MemTotal"), int) and info.get("MemTotal", 0) > 0
        checks["capacity"] = {"status": "pass" if capacity_ok else "unknown", "code": None if capacity_ok else "ANDROID_CAPACITY_UNKNOWN", "message": "CPU 与内存容量可用" if capacity_ok else "容量尚未核实"}
        try:
            free = shutil.disk_usage(self.workspace if self.workspace.exists() else self.root).free
            disk_ok = free > 0
        except OSError:
            disk_ok = False
        checks["disk"] = {"status": "pass" if disk_ok else "unknown", "code": None if disk_ok else "ANDROID_DISK_UNKNOWN", "message": "工作区磁盘可用" if disk_ok else "磁盘空间尚未核实"}
        ready = bool(info.get("OSType") == "linux" and info.get("Architecture") in {"aarch64", "arm64"} and binder)
        return {"images": cached, "cpuCount": info.get("NCPU", 0), "memoryMb": info.get("MemTotal", 0) // (1024 * 1024), "available": supported and tools and vendor and ready, "platformSupported": supported, "checks": checks,
                "runtimeId": VM, "message": "运行环境可用" if supported and tools and vendor and ready else "需要 Apple Silicon Mac、Lima Linux、ADB 和固定版 scrcpy；请运行设备准备命令"}

    def new_device(self, config: dict[str, Any]) -> dict[str, Any]:
        name = "autoflow-android-" + config["deviceId"]
        return {key: config[key] for key in ("deviceId", "name", "imageId", "width", "height", "dpi", "cpu", "memoryMb")} | {"runtimeId": VM, "workspaceId": self.workspace_id, "volumeId": name + "-data", "containerId": name, "profileId": config.get("profileId"), "profileName": config.get("profileName"), "instanceType": config.get("instanceType", "persistent"), "locale": config.get("locale", "zh-CN"), "timezone": config.get("timezone", "Asia/Shanghai"), "androidStatus": "unknown", "ownerRunId": None, "control": "idle", "generation": 0}

    async def capacity(self, device: dict[str, Any]) -> None:
        from autoflow.providers.android.management import capacity
        await capacity(device)

    async def manage(self, device: dict[str, Any], request: dict[str, Any], stage: Callable[[str], None], save: Callable[[], None]) -> None:
        from autoflow.providers.android.management import manage

        await manage(self, device, request, stage, save)

    async def backup_volume(self, device: dict[str, Any]) -> bytes:
        container = (await docker("create", "--label", LABEL + "=" + self.workspace_id,
                                  "--label", "io.autoflow.android.device=" + device["deviceId"],
                                  "-v", f"{device['volumeId']}:/data:ro", device["imageId"], timeout=30)).decode().strip()
        try:
            return await docker("cp", container + ":/data", "-", timeout=600)
        finally:
            await docker("rm", container, timeout=30)

    async def restore_volume(self, device: dict[str, Any], data: bytes) -> None:
        if device.get("workspaceId") != self.workspace_id:
            raise AndroidError("ANDROID_OWNERSHIP", "设备工作区归属校验失败", 403)
        if device.get("androidStatus") is not None and device.get("androidStatus") != "stopped":
            raise AndroidError("ANDROID_BACKUP_REQUIRES_STOPPED", "恢复前必须停止目标实例", 409)
        if device.get("ownerRunId") or device.get("control") not in {None, "idle"}:
            raise AndroidError("ANDROID_BACKUP_REQUIRES_STOPPED", "恢复前必须停止并释放目标实例控制会话", 409)
        volume_id = device.get("volumeId")
        if not isinstance(volume_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}", volume_id):
            raise AndroidError("ANDROID_OWNERSHIP", "设备数据卷标识无效", 403)
        try:
            volume = json.loads(await docker("volume", "inspect", volume_id, timeout=5))[0]
        except (AndroidError, OSError, TimeoutError, ValueError, IndexError, KeyError, TypeError) as error:
            raise AndroidError("ANDROID_OWNERSHIP", "设备数据卷归属无法核实", 403) from error
        labels = volume.get("Labels") or {}
        if labels.get(LABEL) != self.workspace_id or labels.get("io.autoflow.android.device") != device.get("deviceId"):
            raise AndroidError("ANDROID_OWNERSHIP", "设备数据卷归属标签不符", 403)
        container = (await docker("create", "--label", LABEL + "=" + self.workspace_id,
                                  "--label", "io.autoflow.android.device=" + device["deviceId"],
                                  "-v", f"{volume_id}:/data", device["imageId"], timeout=30)).decode().strip()
        try:
            await docker("cp", "-", container + ":/", timeout=600, input_data=data)
        finally:
            await docker("rm", container, timeout=30)

    async def inspect_image(self, reference: str) -> dict[str, Any]:
        try:
            item = json.loads(await docker("image", "inspect", reference, timeout=10))[0]
        except AndroidError as error:
            if error.status == 502 and any(marker in error.message.lower() for marker in ("no such image", "manifest unknown", "not found")):
                raise AndroidError("ANDROID_IMAGE_NOT_FOUND", "镜像不存在", 404) from error
            raise
        repo_digests = item.get("RepoDigests") or []
        source_digest = next((value.split("@", 1)[1] for value in repo_digests if "@" in value), None)
        labels = item.get("Config", {}).get("Labels") or {}
        return {"imageId": item.get("Id"), "sourceDigest": source_digest, "architecture": item.get("Architecture"), "os": item.get("Os"), "androidVersion": labels.get("org.opencontainers.image.version"), "googleComponents": labels.get("autoflow.google-components", "unknown")}

    async def pull_image(self, reference: str) -> None:
        await docker("pull", reference, timeout=900)

    async def delete_image(self, image_id: str) -> None:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise AndroidError("ANDROID_IMAGE_ID_INVALID", "镜像摘要格式无效", 422)
        await docker("image", "rm", image_id, timeout=60)

    def lock(self) -> None:
        if platform.system() != "Darwin":
            raise AndroidError("ANDROID_PLATFORM_UNAVAILABLE", "此安卓运行环境仅在 Mac 提供", 503)
        if self._locked or not self._lock.acquire():
            raise AndroidError("ANDROID_RUNTIME_BUSY", "安卓运行环境已有控制器")
        self._locked = True

    def unlock(self) -> None:
        self._lock.release()
        self._locked = False

    async def inspect(self, device: dict[str, Any]) -> dict[str, Any]:
        if device.get("dataRetained"):
            from autoflow.providers.android.management import verify

            containers, volumes = await verify(device, self.workspace_id)
            if not containers:
                return {"androidStatus": "retained" if volumes else "missing", "dockerStatus": "missing", "imageId": device["imageId"], "ports": {}}
        obj = json.loads(await docker("inspect", device["containerId"], timeout=8))[0]
        labels = obj["Config"].get("Labels") or {}
        if device["workspaceId"] != self.workspace_id or labels.get(LABEL) != self.workspace_id or labels.get("io.autoflow.android.device") != device["deviceId"]:
            raise AndroidError("ANDROID_OWNERSHIP", "设备归属校验失败", 403)
        mounts = obj.get("Mounts", [])
        if not any(m.get("Name") == device["volumeId"] and m.get("Destination") == "/data" for m in mounts):
            raise AndroidError("ANDROID_OWNERSHIP", "设备数据卷归属不符", 403)
        volume = json.loads(await docker("volume", "inspect", device["volumeId"], timeout=5))[0]
        volume_labels = volume.get("Labels") or {}
        if volume_labels.get(LABEL) != self.workspace_id or volume_labels.get("io.autoflow.android.device") != device["deviceId"]:
            raise AndroidError("ANDROID_OWNERSHIP", "设备数据卷标签不符", 403)
        state = obj["State"]["Status"]
        android_status = "stopped"
        if state == "running":
            try:
                boot = await docker("exec", device["containerId"], "getprop", "sys.boot_completed", timeout=3)
                android_status = "ready" if boot.strip() == b"1" else "starting"
            except (AndroidError, TimeoutError):
                android_status = "unknown"
        return {"dockerStatus": state, "androidStatus": android_status, "imageId": obj["Image"], "ports": obj["NetworkSettings"]["Ports"]}

    async def preview(self, device: dict[str, Any]) -> bytes:
        observed = await self.inspect(device)
        if observed["androidStatus"] != "ready":
            raise AndroidError("ANDROID_PREVIEW_UNAVAILABLE", "设备尚未就绪，无法读取画面")
        data = await docker("exec", device["containerId"], "screencap", "-p", timeout=8)
        png_size(data)
        return data

    def _remember(self, name: str, process: subprocess.Popen[bytes]) -> None:
        assert self.device is not None
        self.device.setdefault("processes", {})[name] = {"pid": process.pid, "birth": process_birth(process.pid)}
        self.device.pop("spawnPending", None)
        self.save()

    async def connect(self, device: dict[str, Any], save: Callable[[], None]) -> None:
        self.device, self.save = device, save
        observed = await self.inspect(device)
        if observed["dockerStatus"] == "missing":
            raise AndroidError("ANDROID_DATA_RETAINED", "请先从设备页恢复实例，再打开窗口或运行工作流")
        if observed["dockerStatus"] != "running":
            await docker("start", device["containerId"])
        deadline = time.monotonic() + 180
        while True:
            try:
                boot = await docker("exec", device["containerId"], "getprop", "sys.boot_completed", timeout=3)
                if boot.strip() == b"1":
                    break
            except (AndroidError, TimeoutError):
                pass
            if time.monotonic() >= deadline:
                raise AndroidError("ANDROID_BOOT_TIMEOUT", "Android 启动超时", 504)
            await asyncio.sleep(1)
        observed = await self.inspect(device)
        mapping = observed["ports"].get("5555/tcp") or []
        if len(mapping) != 1 or mapping[0]["HostIp"] != "127.0.0.1":
            raise AndroidError("ANDROID_PORT_INVALID", "设备 ADB 必须仅绑定 Linux 回环地址")
        port = int(mapping[0]["HostPort"])
        if not 1 <= port <= 65535:
            raise AndroidError("ANDROID_PORT_INVALID", "ADB 端口无效")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            local_port = sock.getsockname()[1]
        self.serial = f"127.0.0.1:{local_port}"
        config = Path(os.environ.get("LIMA_HOME", str(Path.home() / ".lima"))) / VM / "ssh.config"
        device["spawnPending"] = True
        self.save()
        self.tunnel = subprocess.Popen(["ssh", "-F", str(config), "-o", "ControlMaster=no", "-o", "ControlPath=none", "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2", "-N", "-L", f"{self.serial}:127.0.0.1:{port}", "lima-" + VM], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: ASYNC220 -- spawn and identity persistence must not yield.
        self._remember("tunnel", self.tunnel)
        for _ in range(30):
            try:
                await run(["adb", "connect", self.serial], 2)
                if (await self._adb("shell", "getprop", "sys.boot_completed", timeout=2)).strip() == b"1":
                    device.update(androidStatus="ready", imageId=observed["imageId"])
                    self.save()
                    return
            except (AndroidError, TimeoutError):
                if self.tunnel.poll() is not None:
                    break
            await asyncio.sleep(.2)
        raise AndroidError("ANDROID_CONNECT_FAILED", "Mac 无法连接 Android", 502)

    async def _adb(self, *args: str, timeout: float = 15) -> bytes:
        if not self.serial:
            raise AndroidError("ANDROID_DISCONNECTED", "安卓设备未连接", 503)
        return await run(["adb", "-s", self.serial, *args], timeout)

    async def command(self, operation: str, args: dict[str, Any], timeout: float) -> bytes:
        if operation == "android_screenshot":
            data = await self._adb("exec-out", "screencap", "-p", timeout=timeout)
            png_size(data)
            return data
        if operation == "android_key":
            argv = ["input", "keyevent", str({"HOME": 3, "BACK": 4, "ENTER": 66, "APP_SWITCH": 187}[args["key"]])]
        elif operation == "android_tap":
            size = png_size(await self._adb("exec-out", "screencap", "-p", timeout=timeout))
            if size != (args["basisWidth"], args["basisHeight"]):
                raise AndroidError("ANDROID_SCREEN_CHANGED", "屏幕尺寸已变化，请更新坐标基准", 422)
            x, y = args["x"], args["y"]
            if type(x) is not int or type(y) is not int or not 0 <= x < size[0] or not 0 <= y < size[1]:
                raise AndroidError("ANDROID_COORDINATES", "坐标超出设备画面", 422)
            argv = ["input", "tap", str(x), str(y)]
        elif operation == "android_launch_app":
            package = args["packageName"]
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package):
                raise AndroidError("ANDROID_PACKAGE_INVALID", "应用包名无效", 422)
            component = ""
            for attempt in range(3):
                resolved = (await self._adb("shell", "cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", package)).decode().strip().splitlines()
                component = next((line.strip() for line in reversed(resolved) if re.fullmatch(r"[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+", line.strip())), "")
                if component:
                    break
                if attempt < 2:
                    await asyncio.sleep(.5)
            if not component:
                raise AndroidError("ANDROID_APP_UNAVAILABLE", "应用不存在或没有启动入口", 422)
            argv = ["am", "start", "-W", "-n", component]
        elif operation in {"android_stop_app", "android_uninstall_app", "android_clear_app_data"}:
            package = args["packageName"]
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package):
                raise AndroidError("ANDROID_PACKAGE_INVALID", "应用包名无效", 422)
            if operation in {"android_uninstall_app", "android_clear_app_data"}:
                system = package_inventory(await self._adb("shell", "pm", "list", "packages", "-s"))
                if package in system or package.startswith(("com.android.", "com.google.android.")):
                    raise AndroidError("ANDROID_PROTECTED_APP", "系统或保护应用不能卸载或清除数据", 409)
                users = package_inventory(await self._adb("shell", "pm", "list", "packages", "-3"))
                if package not in users:
                    raise AndroidError("ANDROID_APP_INFO_UNKNOWN", "无法确认目标为已安装的用户应用", 409)
            argv = {
                "android_stop_app": ["am", "force-stop", package],
                "android_uninstall_app": ["pm", "uninstall", package],
                "android_clear_app_data": ["pm", "clear", package],
            }[operation]
        else:
            raise AndroidError("ANDROID_OPERATION_INVALID", "不支持的设备操作", 422)
        assert self.device is not None
        marker = "/data/local/tmp/autoflow-operation-" + uuid4().hex
        self.device["pendingCommand"] = marker
        self.save()  # A crash or cancellation cannot make the device silently reusable.
        script = shlex.join(argv) + "; rc=$?; echo $rc > " + marker + "; exit $rc"
        data = await self._adb("shell", "sh", "-c", shlex.quote(script), timeout=timeout)
        if operation == "android_launch_app" and (b"Error:" in data or b"Status: ok" not in data):
            raise AndroidError("ANDROID_LAUNCH_FAILED", "Android 未确认应用启动成功", 502)
        if operation in {"android_uninstall_app", "android_clear_app_data"} and b"Success" not in data:
            raise AndroidError("ANDROID_APP_OPERATION_FAILED", "Android 未确认应用操作成功", 502)
        self.device.pop("pendingCommand", None)
        self.save()
        return data

    async def app_info(self) -> dict[str, Any]:
        packages = package_inventory(await self._adb("shell", "pm", "list", "packages", "--show-versioncode"))
        system = package_inventory(await self._adb("shell", "pm", "list", "packages", "-s"))
        applications = [{"packageName": name, "versionCode": version, "versionName": None, "system": name in system,
                         "protected": name in system or name.startswith(("com.android.", "com.google.android."))} for name, version in packages.items()]
        activity = (await self._adb("shell", "dumpsys", "activity", "activities")).decode()
        match = re.search(r"(?:mResumedActivity|topResumedActivity)[=:].*? ([A-Za-z][A-Za-z0-9_.]+)/", activity)
        uid = (await self._adb("shell", "id", "-u")).strip()
        return {"packages": list(packages), "applications": applications, "currentPackage": match.group(1) if match else None, "shellRoot": "available" if uid == b"0" else "unavailable", "applicationRoot": "unknown"}

    async def install_apk(self, data: bytes) -> None:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="autoflow-apk-") as directory:
            path = Path(directory) / "application.apk"
            await asyncio.to_thread(path.write_bytes, data)
            assert self.device is not None
            remote = "/data/local/tmp/autoflow-apk-" + uuid4().hex + ".apk"
            await self._adb("push", str(path), remote, timeout=60)
            marker = "/data/local/tmp/autoflow-operation-" + uuid4().hex
            self.device["pendingCommand"] = marker
            self.save()
            script = f"pm install -r {remote}; rc=$?; rm -f {remote}; echo $rc > {marker}; exit $rc"
            result = await self._adb("shell", "sh", "-c", shlex.quote(script), timeout=120)
            self.device.pop("pendingCommand", None)
            self.save()
            if b"Success" not in result:
                raise AndroidError("ANDROID_INSTALL_FAILED", "Android 未确认 APK 安装成功", 422)

    async def open_window(self, title: str, readonly: bool = False) -> None:
        self.window_readonly = readonly
        if self.window_open():
            return
        assert self.device is not None
        binary = self.root / VENDOR / "scrcpy"
        contents = self.root / "AutoFlow Android.app" / "Contents"
        executable = contents / "MacOS" / "scrcpy"
        executable.parent.mkdir(parents=True, exist_ok=True)
        if not executable.exists():
            executable.symlink_to(binary)
        with (contents / "Info.plist").open("wb") as f:
            plistlib.dump({"CFBundleIdentifier": "local.autoflow.android", "CFBundleName": "AutoFlow Android", "CFBundleExecutable": "scrcpy", "CFBundlePackageType": "APPL", "NSHighResolutionCapable": True}, f)
        import pty

        self.terminal, slave = pty.openpty()
        self.device["spawnPending"] = True
        self.save()
        try:
            self.viewer = subprocess.Popen([str(executable), "--serial", str(self.serial), "--window-title", title, "--no-audio", "--no-clipboard-autosync", "--max-fps=30", "--max-size=1280", "--window-height=720", *(["--no-control"] if readonly else [])], stdout=slave, stderr=slave,  # noqa: ASYNC220 -- persist identity before yielding.
                                           env={**os.environ, "ADB": shutil.which("adb") or "adb", "SCRCPY_SERVER_PATH": str(binary.with_name("scrcpy-server")), "SCRCPY_ICON_PATH": str(binary.with_name("icon.png"))})
            self._remember("viewer", self.viewer)
        finally:
            os.close(slave)
        deadline = time.monotonic() + 25
        output = b""
        while self.viewer.poll() is None and time.monotonic() < deadline:
            if select.select([self.terminal], [], [], 0)[0]:
                try:
                    output = (output + os.read(self.terminal, 65536))[-65536:]
                except OSError:
                    break
                if b"Texture:" in output:
                    return
            await asyncio.sleep(.1)
        await self.close_window()
        raise AndroidError("ANDROID_WINDOW_FAILED", "原生窗口未在限时内出画面", 502)

    def window_open(self) -> bool:
        # Drain diagnostic output so a verbose native process cannot block on PTY.
        if self.terminal is not None and select.select([self.terminal], [], [], 0)[0]:
            try:
                os.read(self.terminal, 65536)
            except OSError:
                pass
        return self.viewer is not None and self.viewer.poll() is None

    async def _stop(self, process: subprocess.Popen[bytes] | None, name: str) -> None:
        if process is not None and process.poll() is None:
            process.terminate()
            deadline = time.monotonic() + 5
            while process.poll() is None and time.monotonic() < deadline:
                await asyncio.sleep(.05)
            if process.poll() is None:
                process.kill()
                await asyncio.to_thread(process.wait, timeout=5)
        if self.device is not None:
            self.device.setdefault("processes", {}).pop(name, None)
            self.save()

    async def close_window(self) -> None:
        await self._stop(self.viewer, "viewer")
        self.viewer = None
        if self.terminal is not None:
            os.close(self.terminal)
            self.terminal = None

    async def disconnect(self) -> None:
        await self.close_window()
        await self._stop(self.tunnel, "tunnel")
        self.tunnel = None
        if self.serial:
            await run(["adb", "disconnect", self.serial])
            self.serial = None

    async def recover(self, device: dict[str, Any]) -> None:
        # Only signals identities persisted by this device controller; never a name-wide kill.
        for identity in device.get("processes", {}).values():
            pid, birth = identity["pid"], identity["birth"]
            if birth is None:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                raise AndroidError("ANDROID_RECOVERY_REQUIRED", "旧进程身份无法核实，设备保持隔离", 503)
            if birth is not None and process_birth(pid) == birth:
                os.kill(pid, signal.SIGTERM)
                for _ in range(100):
                    if process_birth(pid) != birth:
                        break
                    await asyncio.sleep(.05)
                else:
                    raise AndroidError("ANDROID_RECOVERY_REQUIRED", "旧窗口连接仍未退出", 503)
        if device.get("spawnPending"):
            raise AndroidError("ANDROID_RECOVERY_REQUIRED", "存在未确认的进程启动，请检查运行环境", 503)
        marker = device.get("pendingCommand")
        if marker:
            if not re.fullmatch(r"/data/local/tmp/autoflow-operation-[0-9a-f]{32}", marker):
                raise AndroidError("ANDROID_RECOVERY_REQUIRED", "设备操作标记无效", 503)
            await self.inspect(device)
            result = await docker("exec", device["containerId"], "cat", marker, timeout=5)
            if not re.fullmatch(rb"[0-9]+\s*", result):
                raise AndroidError("ANDROID_RECOVERY_REQUIRED", "Android 操作结束状态未知", 503)
        device.pop("pendingCommand", None)
        device["processes"] = {}
