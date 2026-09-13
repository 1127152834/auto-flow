"""Local vphone experiment. No third-party Python packages required."""

import argparse
import base64
import json
import math
import os
import platform
import plistlib
import re
import secrets
import shutil
import signal
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "vphone-cli"
ROOT = (
    Path(os.environ.get("VPHONE_DEMO_ROOT", "~/.vphone-autoflow-demo"))
    .expanduser()
    .resolve()
)
LIBRARY = ROOT / "VMs"
DATA = HERE / ".data"
TOKEN = secrets.token_urlsafe(32)
PROCESSES: dict[str, subprocess.Popen] = {}
# ponytail: one action at a time for this single-device experiment; use per-device locks for a pool.
DEVICE_LOCK = threading.Lock()
_doctor_cache: tuple[float, dict] = (0, {})


def executable() -> Path:
    return (
        Path(
            os.environ.get(
                "VPHONE_DEMO_BIN",
                str(SOURCE / ".build/vphone-cli.app/Contents/MacOS/vphone-cli"),
            )
        )
        .expanduser()
        .resolve()
    )


def capture(args: list[str]) -> dict:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL
        )
        return {
            "code": result.returncode,
            "text": (result.stdout + result.stderr).strip()[:4000],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"code": -1, "text": str(exc)}


def doctor() -> dict:
    global _doctor_cache
    if time.monotonic() - _doctor_cache[0] < 10:
        return _doctor_cache[1]
    mac = platform.system() == "Darwin"
    version = platform.mac_ver()[0]
    checks = {
        "platform": {
            "ok": mac
            and platform.machine() == "arm64"
            and int(version.split(".")[0] or 0) >= 15,
            "text": f"{platform.system()} {version} / {platform.machine()}",
        },
        "binary": {
            "ok": executable().is_file() and os.access(executable(), os.X_OK),
            "text": str(executable()),
        },
    }
    if mac:
        research = capture(["/usr/bin/csrutil", "allow-research-guests", "status"])
        xcode = capture(["/usr/bin/xcodebuild", "-version"])
        checks["research"] = {
            "ok": research["code"] == 0
            and "status: enabled" in research["text"].lower(),
            **research,
        }
        checks["sip"] = {"ok": None, **capture(["/usr/bin/csrutil", "status"])}
        checks["xcode"] = {"ok": xcode["code"] == 0, **xcode}
        nested = capture(["/usr/sbin/sysctl", "-n", "kern.hv_vmm_present"])
        checks["host"] = {
            "ok": nested["code"] == 0 and nested["text"] == "0",
            "text": "物理 Mac 宿主"
            if nested["text"] == "0"
            else "嵌套虚拟化状态未通过",
            "code": nested["code"],
        }
    else:
        checks["research"] = {"ok": False, "text": "需要 Apple Silicon macOS 宿主"}
        checks["host"] = {"ok": False, "text": "需要物理 Mac 宿主"}
    result = {
        "checks": checks,
        "root": str(ROOT),
        "freeGiB": round(shutil.disk_usage(HERE).free / 2**30, 1),
        "canAttemptLaunch": all(
            checks[k]["ok"] for k in ("platform", "binary", "research", "host")
        ),
        "note": "前置检查通过不代表 iOS 已就绪；AMFI 与实际启动由上游 preflight 和画面回读验证。",
    }
    _doctor_cache = (time.monotonic(), result)
    return result


def bundle(name: str) -> Path:
    if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", name
    ):
        raise ValueError("设备名仅支持字母、数字、横线和下划线，最长 48 字符")
    target = LIBRARY / name
    if target.is_symlink() or target.resolve().parent != LIBRARY.resolve():
        raise ValueError("设备目录不能指向专用库以外")
    if not (target / "config.plist").is_file():
        raise ValueError("设备不存在；请先从终端创建真实 iOS 环境")
    return target


def dimensions(target: Path) -> tuple[int, int]:
    config = target / "config.plist"
    if config.is_symlink() or config.stat().st_size > 1024 * 1024:
        raise ValueError("设备配置无效")
    with config.open("rb") as stream:
        size = plistlib.load(stream)["screenConfig"]
    w, h = size["width"], size["height"]
    if any(type(v) is not int or not 1 <= v <= 16384 for v in (w, h)):
        raise ValueError("无效屏幕尺寸")
    return w, h


def devices() -> list[dict]:
    result = []
    for path in sorted(LIBRARY.glob("*/config.plist")):
        name = path.parent.name
        try:
            target = bundle(name)
            w, h = dimensions(target)
            proc = PROCESSES.get(name)
            result.append(
                {
                    "name": name,
                    "width": w,
                    "height": h,
                    "socketPresent": (target / "vphone.sock").is_socket(),
                    "managed": proc is not None and proc.poll() is None,
                    "exitCode": proc.poll() if proc else None,
                }
            )
        except (ValueError, OSError, KeyError, plistlib.InvalidFileException) as exc:
            result.append(
                {
                    "name": name,
                    "error": str(exc),
                    "socketPresent": False,
                    "managed": False,
                    "width": 0,
                    "height": 0,
                }
            )
    return result


def number(value, low: float, high: float) -> float:
    if (
        type(value) not in (float, int)
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"数值必须在 {low} 到 {high} 之间")
    return value


def wire_command(action: dict, width: int, height: int) -> dict:
    if not isinstance(action, dict):
        raise ValueError("动作必须是 JSON 对象")
    kind = action.get("t")
    out = {"t": kind, "delay": 500}
    if kind == "screenshot":
        allowed = {"t"}
    elif kind == "tap":
        allowed = {"t", "x", "y"}
        out.update(
            x=number(action.get("x"), 0, 1) * (width - 1),
            y=number(action.get("y"), 0, 1) * (height - 1),
        )
    elif kind == "swipe":
        allowed = {"t", "x1", "y1", "x2", "y2", "ms"}
        for key, size in (("x1", width), ("x2", width), ("y1", height), ("y2", height)):
            out[key] = number(action.get(key), 0, 1) * (size - 1)
        out["ms"] = int(number(action.get("ms", 350), 50, 3000))
    elif kind == "key":
        allowed = {"t", "name"}
        if action.get("name") not in ("home", "power", "volup", "voldown"):
            raise ValueError("不支持的设备按键")
        out["name"] = action["name"]
    elif kind == "clipboard":
        allowed = {"t", "text"}
        value = action.get("text")
        if not isinstance(value, str) or len(value.encode("utf-8")) > 2000:
            raise ValueError("剪贴板文本必须小于 2000 UTF-8 字节")
        out.update(t="type", text=value)
    else:
        raise ValueError("仅支持 screenshot/tap/swipe/key/clipboard；控件树尚未实现")
    if set(action) - allowed:
        raise ValueError("动作包含不支持的字段")
    return out


def exchange(sock_path: Path, command: dict, timeout: float = 12) -> dict:
    encoded = json.dumps(command, ensure_ascii=False).encode() + b"\n"
    if len(encoded) > 4000:
        raise ValueError("命令超过上游 4096 字节限制")
    if len(os.fsencode(sock_path)) >= 104:
        raise ValueError("socket 路径过长；请使用较短的 VPHONE_DEMO_ROOT")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(sock_path))
        client.sendall(encoded)
        # One absolute deadline, including fragmented/trickled responses.
        deadline = time.monotonic() + timeout
        data = bytearray()
        while b"\n" not in data:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("等待 vphone 截图超时")
            client.settimeout(remaining)
            chunk = client.recv(65536)
            if not chunk:
                raise ValueError("vphone 连接提前关闭，未收到完整响应")
            data.extend(chunk)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("vphone 响应过大")
    reply = json.loads(bytes(data).split(b"\n", 1)[0])
    if not isinstance(reply, dict) or reply.get("ok") is not True:
        raise ValueError(
            str(reply.get("error", "vphone 返回失败"))
            if isinstance(reply, dict)
            else "vphone 响应格式错误"
        )
    image = reply.get("image")
    if not isinstance(image, str):
        raise ValueError("指令已发送，但未回读到画面；不能标记为成功")
    raw = base64.b64decode(image, validate=True)
    if not (raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9")):
        raise ValueError("回读图像不是有效的 JPEG 数据")
    return {"ok": True, "image": image}


def perform(name: str, action: dict) -> dict:
    target = bundle(name)
    width, height = dimensions(target)
    command = wire_command(action, width, height)
    if not DEVICE_LOCK.acquire(blocking=False):
        raise ValueError("设备操作忙，请等待当前指令结束")
    try:
        result = exchange(target / "vphone.sock", command)
        return {
            **result,
            "width": width,
            "height": height,
            "message": "剪贴板已设置，仍需在 App 内粘贴"
            if action["t"] == "clipboard"
            else "指令与画面回读完成；业务结果需单独检查",
        }
    finally:
        DEVICE_LOCK.release()


def lifecycle(name: str, operation: str) -> dict:
    bundle(name)
    if not DEVICE_LOCK.acquire(blocking=False):
        raise ValueError("设备操作忙")
    try:
        proc = PROCESSES.get(name)
        if operation == "start":
            if (proc and proc.poll() is None) or (
                bundle(name) / "vphone.sock"
            ).exists():
                raise ValueError("设备已启动或存在 socket；请先核查原运行进程")
            if not doctor()["canAttemptLaunch"]:
                raise ValueError("宿主前置条件未满足，请查看环境检查和 README")
            DATA.mkdir(exist_ok=True)
            env = {
                **os.environ,
                "VPHONE_ROOT": str(ROOT),
                "VPHONE_LIBRARY_ROOT": str(LIBRARY),
            }
            with (DATA / f"{name}.log").open("ab") as log:
                PROCESSES[name] = subprocess.Popen(
                    [
                        str(executable()),
                        "vm",
                        "launch",
                        name,
                        "--library-root",
                        str(LIBRARY),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    env=env,
                    start_new_session=True,
                )
            return {"message": "启动进程已创建，需等待 socket 并回读画面确认就绪"}
        if operation == "stop":
            if not proc or proc.poll() is not None:
                raise ValueError("本服务未持有该设备进程，请在原启动终端停止")
            os.killpg(proc.pid, signal.SIGINT)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired as exc:
                raise ValueError(
                    "设备未在 20 秒内退出；请检查原生窗口，未强制终止"
                ) from exc
            return {"message": "启动进程已退出；磁盘数据保留"}
        raise ValueError("仅支持 start/stop")
    finally:
        DEVICE_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Do not log user-entered text or tokens.

    def trusted(self) -> bool:
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return host in hosts and (origin is None or origin == f"http://{host}")

    def respond(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.trusted():
            self.respond({"error": "Host/Origin 不允许"}, 403)
            return
        path = urlsplit(self.path).path
        if path == "/api/state":
            self.respond(
                {"environment": doctor(), "devices": devices(), "token": TOKEN}
            )
            return
        if path.startswith("/api/"):
            self.respond({"error": "接口不存在"}, 404)
            return
        static = HERE / "frontend/dist"
        file = (static / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
        if not file.is_relative_to(static.resolve()) or not file.is_file():
            self.respond(
                {"error": "请先构建前端：cd frontend && npm ci && npm run build"}, 404
            )
            return
        mime = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}.get(
            file.suffix, "application/octet-stream"
        )
        raw = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if not self.trusted() or not secrets.compare_digest(
            self.headers.get("X-Demo-Token", ""), TOKEN
        ):
            self.respond({"error": "请求来源或 token 不允许"}, 403)
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("仅接受 application/json")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                raise ValueError("请求大小无效")
            self.connection.settimeout(5)
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("请求必须是对象")
            if self.path == "/api/action":
                result = perform(body.get("device"), body.get("action"))
            elif self.path == "/api/lifecycle":
                result = lifecycle(body.get("device"), body.get("operation"))
            else:
                self.respond({"error": "接口不存在"}, 404)
                return
            self.respond(result)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self.respond({"error": str(exc)}, 400)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("serve", "doctor", "smoke"), nargs="?", default="serve"
    )
    parser.add_argument("--port", type=int, default=8083)
    parser.add_argument("--device", default="af-ios-demo")
    args = parser.parse_args()
    if args.command == "doctor":
        result = doctor()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["canAttemptLaunch"] else 2
    if args.command == "smoke":
        output = DATA / "runs" / time.strftime("%Y%m%d-%H%M%S")
        output.mkdir(parents=True, exist_ok=False)
        steps = [{"t": "screenshot"}, {"t": "key", "name": "home"}, {"t": "screenshot"}]
        report = {
            "device": args.device,
            "status": "failed",
            "steps": [],
            "scope": "真实 socket 指令和画面回读；不证明 App 业务流程正确",
        }
        try:
            for i, step in enumerate(steps):
                result = perform(args.device, step)
                (output / f"{i + 1:02}.jpg").write_bytes(
                    base64.b64decode(result["image"])
                )
                report["steps"].append({"action": step, "ok": True})
            report["status"] = "passed"
        except (ValueError, OSError, KeyError) as exc:
            report["error"] = str(exc)
        (output / "result.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        print(
            json.dumps({**report, "output": str(output)}, ensure_ascii=False, indent=2)
        )
        return 0 if report["status"] == "passed" else 1
    DATA.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"iOS Demo: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
