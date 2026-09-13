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


async def run(argv: list[str], timeout: float = 15) -> bytes:
    spawn = asyncio.create_task(asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE))
    try:
        process = await asyncio.shield(spawn)
    except asyncio.CancelledError:
        process = await _wait_for_spawn(spawn)
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout)
        if process.returncode:
            raise AndroidError("ANDROID_COMMAND_FAILED", "安卓运行环境命令失败，请检查设备与连接", 502)
        return stdout
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def docker(*args: str, timeout: float = 30) -> bytes:
    return await run(["limactl", "shell", "--workdir=/tmp", VM, "sudo", "docker", *args], timeout)


def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise AndroidError("ANDROID_SCREEN_INVALID", "设备未返回有效 PNG", 502)
    return struct.unpack(">II", data[16:24])


class MacAndroidRuntime:
    def __init__(self, root: Path, workspace: Path) -> None:
        self.root = root
        self.workspace_id = hashlib.sha256(str(workspace.resolve()).encode()).hexdigest()
        self._lock = ExclusiveFileLock(root / (VM + ".lock"))
        self._locked = False
        self.serial: str | None = None
        self.tunnel: subprocess.Popen[bytes] | None = None
        self.viewer: subprocess.Popen[bytes] | None = None
        self.terminal: int | None = None
        self.device: dict[str, Any] | None = None
        self.save: Callable[[], None] = lambda: None

    async def environment(self) -> dict[str, Any]:
        supported = platform.system() == "Darwin" and platform.machine() == "arm64"
        tools = all(shutil.which(tool) for tool in ("adb", "limactl", "ssh"))
        vendor = (self.root / VENDOR / "scrcpy").is_file()
        ready = False
        info: dict[str, Any] = {}
        if supported and tools:
            try:
                info = json.loads(await docker("info", "--format", "{{json .}}", timeout=5))
                filesystems = await run(["limactl", "shell", "--workdir=/tmp", VM, "cat", "/proc/filesystems"], 5)
                ready = info.get("OSType") == "linux" and info.get("Architecture") in {"aarch64", "arm64"} and b"binder" in filesystems
            except (AndroidError, TimeoutError, OSError, ValueError):
                pass
        from autoflow.providers.android.management import images

        cached = await images() if ready else []
        return {"images": cached, "cpuCount": info.get("NCPU", 0), "memoryMb": info.get("MemTotal", 0) // (1024 * 1024), "available": supported and tools and vendor and ready, "platformSupported": supported,
                "runtimeId": VM, "message": "运行环境可用" if supported and tools and vendor and ready else "需要 Apple Silicon Mac、Lima Linux、ADB 和固定版 scrcpy；请运行设备准备命令"}

    def new_device(self, config: dict[str, Any]) -> dict[str, Any]:
        name = "autoflow-android-" + config["deviceId"]
        return {key: config[key] for key in ("deviceId", "name", "imageId", "width", "height", "dpi", "cpu", "memoryMb")} | {"runtimeId": VM, "workspaceId": self.workspace_id, "volumeId": name + "-data", "containerId": name, "androidStatus": "unknown", "ownerRunId": None, "control": "idle", "generation": 0}

    async def manage(self, device: dict[str, Any], request: dict[str, Any], stage: Callable[[str], None], save: Callable[[], None]) -> None:
        from autoflow.providers.android.management import manage

        await manage(self, device, request, stage, save)

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
            resolved = (await self._adb("shell", "cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", package)).decode().strip().splitlines()
            component = resolved[-1] if resolved else ""
            if not re.fullmatch(r"[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+", component):
                raise AndroidError("ANDROID_APP_UNAVAILABLE", "应用不存在或没有启动入口", 422)
            argv = ["am", "start", "-W", "-n", component]
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
        self.device.pop("pendingCommand", None)
        self.save()
        return data

    async def open_window(self, title: str) -> None:
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
            self.viewer = subprocess.Popen([str(executable), "--serial", str(self.serial), "--window-title", title, "--no-audio", "--no-clipboard-autosync", "--max-fps=30", "--max-size=1280", "--window-height=720"], stdout=slave, stderr=slave,  # noqa: ASYNC220 -- persist identity before yielding.
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
