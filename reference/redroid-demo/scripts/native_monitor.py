#!/usr/bin/env python3
"""Mac-only reference monitor: React -> local launcher -> scrcpy -> Lima redroid.

Uses the existing demo API for ownership/start/readiness. No Android input is
sent by this web page. This is not a workflow lease or a production IPC bridge.
"""
import json
import os
from pathlib import Path
import platform
import plistlib
import pty
import re
import shutil
import socket
import select
import subprocess
import threading
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from flask import Flask, jsonify, redirect, request, send_from_directory
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "http://127.0.0.1:8081"
VM = "autoflow-redroid"
INSTANCE = re.compile(r"afd-[0-9a-f]{16}")
SCRCPY = ROOT / ".data/native-monitor/vendor/scrcpy-macos-aarch64-v3.3.4/scrcpy"


class NativeError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def api(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(UPSTREAM + "/api" + path, data=data,
                  headers={"Content-Type": "application/json"})
    try:
        with build_opener(ProxyHandler({})).open(req, timeout=35) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = json.load(exc).get("error", {}).get("message", str(exc))
        raise NativeError(detail, exc.code) from exc


def command(argv, timeout=15):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise NativeError((result.stderr or result.stdout).strip()[-2000:] or "本机命令失败", 502)
    return result.stdout.strip()


def guest_port(address):
    match = re.fullmatch(r"127\.0\.0\.1:([0-9]{1,5})", address or "")
    if not match or not 1 <= int(match[1]) <= 65535:
        raise NativeError("实例没有有效的 Linux 宿主回环 ADB 端口")
    return int(match[1])


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def viewer_binary():
    """A local app identity lets macOS expose the native window in its app UI."""
    contents = ROOT / ".data" / "native-monitor" / "AutoFlow Android.app" / "Contents"
    executable = contents / "MacOS" / "scrcpy"
    executable.parent.mkdir(parents=True, exist_ok=True)
    if not SCRCPY.is_file():
        raise NativeError("缺少固定版 scrcpy，请运行 scripts/start-native-mac.sh")
    if executable.is_symlink() and executable.resolve() != SCRCPY.resolve():
        executable.unlink()
    if not executable.exists():
        executable.symlink_to(SCRCPY.resolve())
    with (contents / "Info.plist").open("wb") as target:
        plistlib.dump({"CFBundleIdentifier": "local.autoflow.redroid-native-demo",
                      "CFBundleName": "AutoFlow Android", "CFBundleExecutable": "scrcpy",
                      "CFBundlePackageType": "APPL", "NSHighResolutionCapable": True}, target)
    return str(executable)


class Launcher:
    def __init__(self):
        self.lock = threading.RLock()
        self.worker = None
        self.stopping = threading.Event()
        self.state = {"phase": "idle", "instance_id": None, "message": "尚未打开原生窗口"}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def update(self, phase, message, **extra):
        with self.lock:
            self.state.update(phase=phase, message=message, **extra)

    def open(self, instance_id):
        if not isinstance(instance_id, str) or not INSTANCE.fullmatch(instance_id):
            raise NativeError("实例 ID 无效")
        with self.lock:
            # ponytail: one native window for this validation; add per-device
            # sessions only with the formal workflow/manual ownership contract.
            if self.worker and self.worker.is_alive():
                raise NativeError("已有窗口或启动任务，请先关闭原生窗口", 409)
            if self.stopping.is_set():
                raise NativeError("启动器正在退出", 503)
            self.state = {"phase": "starting", "instance_id": instance_id, "message": "正在检查真实实例"}
            self.worker = threading.Thread(target=self.launch, args=(instance_id,), daemon=True)
            self.worker.start()
            return dict(self.state)

    def wait(self, seconds):
        if self.stopping.wait(seconds):
            raise NativeError("启动器已关闭", 503)

    def launch(self, instance_id):
        tunnel = viewer = None
        terminal = None
        serial = None
        errors = []
        log_path = ROOT / ".data" / "native-monitor" / f"{instance_id}-{time.time_ns()}.log"
        try:
            for tool in ("adb", "limactl", "ssh"):
                if not shutil.which(tool):
                    raise NativeError(f"Mac 缺少 {tool}，请先安装")
            # The API must belong to this VM, not an unrelated forwarded service.
            guest = command(["limactl", "shell", "--workdir=/tmp", VM, "python3", "-c",
                             'import json,urllib.request; print(json.load(urllib.request.build_opener(urllib.request.ProxyHandler({})).open("http://127.0.0.1:8080/api/jobs",timeout=5))["session_id"])'])
            if guest != api("/jobs")["session_id"]:
                raise NativeError("8081 与目标 Lima VM 的 API 会话不一致", 409)
            device = api(f"/instances/{instance_id}")  # upstream validates Docker labels
            if device["busy"]:
                raise NativeError("设备正在执行 Demo 操作", 409)
            if device["docker_status"] != "running":
                self.update("starting", "正在启动 Android；数据保留")
                job_id = api(f"/instances/{instance_id}/actions", {"action": "start"})["job_id"]
                deadline = time.monotonic() + 200
                while True:
                    job = api(f"/jobs/{job_id}")
                    if job["status"] in ("done", "failed"):
                        if job["status"] == "failed" or any(r["status"] != "success" for r in job["results"]):
                            raise NativeError("Android 启动失败：" + str(job["results"]), 502)
                        break
                    if time.monotonic() > deadline:
                        raise NativeError("启动等待超时，请在 Demo 核实实际状态", 504)
                    self.wait(1)
                device = api(f"/instances/{instance_id}")
            if device["android_status"] != "ready" or device["busy"]:
                raise NativeError("Android 尚未就绪或设备正在执行操作", 409)
            port = guest_port(device["adb_address"])
            self.update("connecting", "Android 已就绪，正在连接原生窗口", name=device["name"])
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                local_port = listener.getsockname()[1]
            serial = f"127.0.0.1:{local_port}"
            config = Path(os.getenv("LIMA_HOME", str(Path.home() / ".lima"))) / VM / "ssh.config"
            if not config.is_file():
                raise NativeError("Lima SSH 配置不存在，请先启动 VM")
            with log_path.open("wb") as log:
                tunnel = subprocess.Popen(["ssh", "-F", str(config), "-o", "ControlMaster=no",
                                           "-o", "ControlPath=none", "-o", "ExitOnForwardFailure=yes",
                                           "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
                                           "-N", "-L", f"{serial}:127.0.0.1:{port}", "lima-" + VM],
                                          stdout=log, stderr=log)
                for _ in range(40):
                    if tunnel.poll() is not None:
                        raise NativeError("ADB 隧道启动失败", 502)
                    try:
                        with socket.create_connection(("127.0.0.1", local_port), timeout=.2):
                            break
                    except OSError:
                        self.wait(.1)
                else:
                    raise NativeError("ADB 隧道连接超时", 504)
                command(["adb", "connect", serial])
                if command(["adb", "-s", serial, "shell", "getprop", "sys.boot_completed"]) != "1":
                    raise NativeError("Mac ADB 未确认 Android 就绪", 502)
                terminal, slave = pty.openpty()
                try:
                    viewer = subprocess.Popen([viewer_binary(), "--serial", serial,
                                           "--window-title", f"AutoFlow · {device['name']} · {instance_id}",
                                           "--no-audio", "--no-clipboard-autosync", "--max-fps=30",
                                           "--max-size=1280", "--window-height=720"], stdout=slave, stderr=slave,
                                          env={**os.environ, "SCRCPY_SERVER_PATH": str(SCRCPY.with_name("scrcpy-server")),
                                               "SCRCPY_ICON_PATH": str(SCRCPY.with_name("icon.png")),
                                               "ADB": shutil.which("adb")})
                finally:
                    os.close(slave)
                output = bytearray()

                def drain_output():
                    if select.select([terminal], [], [], .1)[0]:
                        try:
                            chunk = os.read(terminal, 65536)
                        except OSError:
                            return
                        output.extend(chunk)
                        del output[:-65536]
                        log.write(chunk)
                        log.flush()

                deadline = time.monotonic() + 25
                while viewer.poll() is None:
                    drain_output()
                    if tunnel.poll() is not None:
                        raise NativeError("ADB 隧道已断开", 502)
                    if b"Texture:" in output:
                        self.update("open", "原生窗口已出画面；请在 Mac 窗口中点击和输入", serial=serial)
                        break
                    if time.monotonic() > deadline:
                        raise NativeError("scrcpy 未在限时内输出画面", 504)
                    self.wait(.2)
                if self.snapshot()["phase"] != "open":
                    raise NativeError("scrcpy 出画面前已退出", 502)
                while viewer.poll() is None:
                    drain_output()
                    if tunnel.poll() is not None:
                        raise NativeError("ADB 隧道已断开", 502)
                    self.wait(.3)
                if viewer.returncode:
                    raise NativeError(f"scrcpy 异常退出（{viewer.returncode}）", 502)
        except Exception as exc:
            errors.append(str(exc))
        finally:
            self.update("closing", "正在清理窗口连接；Android 实例保留")
            for process in (viewer, tunnel):
                try:
                    stop_process(process)
                except Exception as exc:
                    errors.append(f"连接进程清理失败：{exc}")
            if terminal is not None:
                os.close(terminal)
            if serial:
                try:
                    command(["adb", "disconnect", serial])
                except Exception as exc:
                    errors.append(f"ADB 连接清理失败：{exc}")
            if errors:
                self.update("failed", "; ".join(errors), log=str(log_path.relative_to(ROOT)))
            else:
                self.update("closed", "原生窗口已关闭；本次仅清理连接，设备数据保留")

    def shutdown(self):
        self.stopping.set()
        if self.worker:
            self.worker.join(timeout=55)


def create_app(launcher=None):
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 1024
    launcher = launcher or Launcher()
    app.extensions["native_launcher"] = launcher

    @app.before_request
    def local_only():
        if request.host not in ("127.0.0.1:8082", "localhost:8082"):
            raise NativeError("仅接受本机 8082 访问")
        if request.method == "POST":
            if request.headers.get("Origin") != request.host_url.rstrip("/") or request.headers.get("Sec-Fetch-Site") == "cross-site":
                raise NativeError("拒绝跨来源启动原生进程", 403)
            if not request.is_json:
                raise NativeError("请使用 JSON 请求", 415)

    @app.errorhandler(NativeError)
    def native_error(exc):
        return jsonify(error={"message": str(exc)}), exc.status

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error={"message": exc.description}), exc.code
        return jsonify(error={"message": str(exc)}), 502

    @app.get("/api/native")
    def status():
        return jsonify(instances=api("/instances")["instances"], session=launcher.snapshot())

    @app.post("/api/native/open")
    def open_window():
        body = request.get_json()
        if not isinstance(body, dict) or set(body) != {"instance_id"}:
            raise NativeError("只接受 instance_id")
        return jsonify(launcher.open(body["instance_id"])), 202

    @app.get("/")
    def home():
        return redirect("/native")

    @app.get("/native")
    def index():
        return send_from_directory(ROOT / "frontend" / "dist", "index.html")

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(ROOT / "frontend" / "dist" / "assets", filename)

    return app


if __name__ == "__main__":
    if platform.system() != "Darwin":
        raise SystemExit("此验证启动器只支持 Mac")
    from waitress import serve
    app = create_app()
    print("Mac native monitor: http://127.0.0.1:8082/native", flush=True)
    try:
        serve(app, host="127.0.0.1", port=8082, threads=4)
    finally:
        app.extensions["native_launcher"].shutdown()
