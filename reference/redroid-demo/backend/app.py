#!/usr/bin/env python3
"""Redroid Manager demo — Flask + Docker SDK.

Adapted from JinHisAndy/RedroidManager app.py, MIT License,
commit 853b786b29430886ae8db58eb2d9e3432e0c8684 (2026-09-13).
Copied/adapted: labelled container discovery, redroid command/volume setup,
lifecycle calls, tar APK upload, screencap/input and package-list commands.
Changed: ownership, ports, job bounds, validation, deadlines, single-frame API.
See ../THIRD_PARTY.md and ../licenses/RedroidManager-LICENSE.txt.
"""

import copy
import io
import json
import math
import os
import re
import socket
import struct
import tarfile
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import docker
from flask import Flask, Response, jsonify, request, send_from_directory
from requests.exceptions import RequestException
from werkzeug.exceptions import HTTPException


BASE_DIR = Path(__file__).resolve().parent.parent
LABEL_MANAGER = "autoflow.redroid-demo"
LABEL_INSTANCE = LABEL_MANAGER + ".instance"
DEFAULT_IMAGE = "redroid/redroid:13.0.0-latest"
ROOT_IMAGE = "autoflow/redroid:13-magisk"
MAX_INSTANCES = 3
CONCURRENCY = 2
MAX_APK = 256 * 1024 * 1024
PACKAGE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")
KEYS = {3, 4, 187, 66, 67, 19, 20, 21, 22, 62}
DOCKER_ERRORS = (docker.errors.DockerException, RequestException, OSError)


class DemoError(Exception):
    def __init__(self, message, status=400, code="invalid_request"):
        super().__init__(message)
        self.status = status
        self.code = code


def integer(data, key, default, lower, upper):
    value = data.get(key, default)
    if type(value) is not int or not lower <= value <= upper:
        raise DemoError(f"{key} 必须是 {lower}–{upper} 的整数")
    return value


class Runtime:
    def __init__(self, app, client=None):
        self.app = app
        self._client = client
        self.lock = threading.RLock()
        # ponytail: one process, 3 devices and 50 jobs; use durable coordination
        # only when this demo becomes a multi-process service.
        self.executor = ThreadPoolExecutor(max_workers=CONCURRENCY, thread_name_prefix="redroid")
        self.jobs = {}
        self.busy = set()
        self.quarantine = set()
        self.creating = set()
        self.states = {}
        self.versions = {}
        self.sizes = {}
        self.last_screen = {}
        self.last_probe = {}
        self.session_id = uuid.uuid4().hex
        self.upload_dir = Path(app.config["UPLOAD_DIR"])
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = docker.from_env(timeout=30)
            except DOCKER_ERRORS as exc:
                raise DemoError(f"Docker 不可用：{exc}", 503, "docker_unavailable") from exc
        return self._client

    def containers(self):
        # Adapted directly from upstream get_redroid_containers.
        return self.client.containers.list(all=True, filters={"label": f"{LABEL_MANAGER}=1"})

    def owned(self, instance_id):
        try:
            ct = self.client.containers.get(instance_id)
        except docker.errors.NotFound as exc:
            raise DemoError("实例不存在", 404, "not_found") from exc
        if ct.labels.get(LABEL_MANAGER) != "1" or ct.labels.get(LABEL_INSTANCE) != ct.name:
            raise DemoError("实例不属于此 Demo", 404, "not_owned")
        return ct

    def environment(self):
        checks = []
        info = None
        images = []
        available = False
        try:
            info = self.client.info()
            available = True
            daemon = {key: info.get(key) for key in
                      ("ID", "Name", "OperatingSystem", "OSType", "Architecture", "KernelVersion", "ServerVersion")}
            architecture = str(info.get("Architecture", ""))
            supported = info.get("OSType") == "linux" and architecture in ("x86_64", "amd64")
            desktop = "docker desktop" in str(info.get("OperatingSystem", "")).lower() or "docker-desktop" in str(info.get("Name", "")).lower()
            checks.append({"name": "docker_host", "status": "pass" if supported and not desktop else "fail",
                           "message": "Linux amd64 Docker Engine" if supported and not desktop else
                           "此 Demo 基线需要 Linux amd64 原生 Engine；Docker Desktop/ARM 宿主不受支持"})
            for ref in self.app.config["IMAGES"]:
                try:
                    img = self.client.images.get(ref)
                    images.append({"ref": ref, "cached": True, "id": img.id,
                                   "digests": img.attrs.get("RepoDigests", [])})
                except docker.errors.ImageNotFound:
                    images.append({"ref": ref, "cached": False, "id": None, "digests": []})
        except (DemoError, *DOCKER_ERRORS) as exc:
            available = False
            daemon = None
            checks.append({"name": "docker", "status": "fail", "message": str(exc)})
        proc = Path(self.app.config["HOST_PROC"])
        dev = Path(self.app.config["HOST_DEV"])
        try:
            filesystems = (proc / "filesystems").read_text()
            modules = (proc / "modules").read_text() if (proc / "modules").exists() else ""
            binder = ("binder" in filesystems or "binder_linux" in modules or
                      (dev / "binderfs" / "binder-control").exists() or (dev / "binder").exists())
            checks.append({"name": "binder", "status": "pass" if binder else "fail",
                           "message": "实际 Engine 宿主挂载中发现 binder 能力" if binder else
                           "宿主未发现 binder/binderfs；先配置 WSL/Linux 内核"})
        except OSError:
            checks.append({"name": "binder", "status": "unknown",
                           "message": "未读取到 Engine 宿主 /proc；请用 Compose 挂载 /host/proc、/host/dev"})
        if not images:
            images = [{"ref": ref, "cached": False, "id": None, "digests": []} for ref in self.app.config["IMAGES"]]
        cached = any(item["cached"] for item in images)
        checks.append({"name": "images", "status": "pass" if cached else "fail",
                       "message": "已有可选缓存镜像；创建时再检查所选镜像" if cached else "请先在同一 Engine 拉取基础镜像"})
        return {"docker_available": available, "ready": available and all(c["status"] == "pass" for c in checks),
                "checks": checks, "daemon": daemon, "images": images,
                "limits": {"max_instances": MAX_INSTANCES, "concurrency": CONCURRENCY}}

    def preflight(self, image):
        environment = self.environment()
        if not environment["ready"]:
            errors = "; ".join(c["message"] for c in environment["checks"] if c["status"] != "pass")
            raise DemoError(errors, 503, "host_unsupported")
        img = next((item for item in environment["images"] if item["ref"] == image), None)
        if not img or not img["cached"]:
            raise DemoError(f"镜像 {image} 未缓存，请先在同一 Engine 构建/拉取", 400, "image_missing")
        actual = self.client.images.get(img["id"])
        if actual.attrs.get("Architecture") not in ("amd64", "x86_64"):
            raise DemoError("所选镜像必须为 amd64", 400, "image_architecture")
        return img["id"]

    def config(self, data):
        name = data.get("name", "Android demo")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64 or any(ord(c) < 32 for c in name):
            raise DemoError("name 必须是 1–64 字符的名称")
        image = data.get("image", DEFAULT_IMAGE)
        if not isinstance(image, str) or image not in self.app.config["IMAGES"]:
            raise DemoError("image 不在 Demo 允许的镜像列表")
        cpu = data.get("cpu", 2)
        if type(cpu) not in (int, float) or not math.isfinite(cpu) or not 0.5 <= cpu <= 8:
            raise DemoError("cpu 必须在 0.5–8 之间")
        return {"name": name.strip(), "image": image,
                "width": integer(data, "width", 720, 128, 2160),
                "height": integer(data, "height", 1280, 128, 2160),
                "dpi": integer(data, "dpi", 320, 120, 640), "cpu": cpu,
                "memory_mb": integer(data, "memory_mb", 2048, 512, 8192)}

    def _set_state(self, ct, status, error=None):
        with self.lock:
            self.states[ct.name] = (ct.attrs.get("State", {}).get("StartedAt"), status, error)

    def _stop_uncertain(self, ct, reason):
        """Do not release ownership while a timed-out exec may still run."""
        try:
            ct.stop(timeout=3)
            ct.reload()
            if ct.status in ("running", "restarting", "paused"):
                raise RuntimeError("Docker 仍报告实例活动中")
            self._set_state(ct, "failed", f"{reason}；实例已停止以终止命令")
            return "实例已停止以终止命令"
        except Exception as exc:
            with self.lock:
                self.quarantine.add(ct.name)
                self.busy.add(ct.name)
            self._set_state(ct, "failed", f"{reason}；停止未确认：{exc}，保留 busy，请从 Engine 停止实例")
            return f"停止未确认：{exc}；保留 busy，请从 Engine 停止实例"

    def exec(self, ct, argv, timeout=None, check=True, readonly=False):
        """Docker multiplexed socket, bounded read; no runaway future/thread."""
        if readonly and argv != ["getprop", "sys.boot_completed"]:
            raise ValueError("Only the boot property probe may use readonly timeout handling")
        deadline = time.monotonic() + (timeout or self.app.config["EXEC_TIMEOUT"])
        connection = None
        started = False
        try:
            result = self.client.api.exec_create(ct.id, argv, stdout=True, stderr=True, stdin=False, tty=False)
            started = True  # A failed start response can still mean Docker accepted it.
            connection = self.client.api.exec_start(result["Id"], socket=True, tty=False)
            sock = getattr(connection, "_sock", connection)
            pending = bytearray()
            stdout, stderr = bytearray(), bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Android 命令超时")
                sock.settimeout(min(1, remaining))
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                pending.extend(chunk)
                while len(pending) >= 8:
                    kind, length = pending[0], struct.unpack(">I", pending[4:8])[0]
                    if kind not in (1, 2) or length > 32 * 1024 * 1024:
                        raise DemoError("Docker 返回了无效 exec 数据帧", 503, "exec_protocol")
                    if len(pending) < 8 + length:
                        break
                    (stdout if kind == 1 else stderr).extend(pending[8:8 + length])
                    del pending[:8 + length]
                    if len(stdout) + len(stderr) > 32 * 1024 * 1024:
                        raise DemoError("Android 命令输出超过 32 MiB", 503, "exec_output_limit")
            if pending:
                raise DemoError("Docker exec 输出不完整", 503, "exec_protocol")
            while True:
                inspection = self.client.api.exec_inspect(result["Id"])
                if not inspection["Running"]:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("Android 命令超时")
                time.sleep(0.05)
            code = inspection.get("ExitCode")
            if code is None:
                raise DemoError("Android 命令退出状态未知", 503, "exec_unknown")
            if check and code != 0:
                message = bytes(stderr or stdout).decode(errors="replace").strip()[-1500:]
                raise DemoError(f"Android 命令失败（{code}）：{message}", 400, "exec_failed")
            return code, bytes(stdout), bytes(stderr)
        except TimeoutError as exc:
            if readonly:
                raise DemoError("只读就绪检查超时；未停止设备，稍后重试", 504, "probe_timeout") from exc
            outcome = self._stop_uncertain(ct, str(exc))
            raise DemoError(f"{exc}；{outcome}", 504, "exec_timeout") from exc
        except (DemoError, *DOCKER_ERRORS) as exc:
            if started and not readonly and (not isinstance(exc, DemoError) or exc.code not in ("exec_failed",)):
                outcome = self._stop_uncertain(ct, str(exc))
                raise DemoError(f"命令结果未知：{exc}；{outcome}", 503, "exec_uncertain") from exc
            raise
        finally:
            if connection is not None:
                connection.close()

    def wait_ready(self, ct):
        deadline = time.monotonic() + self.app.config["BOOT_TIMEOUT"]
        self._set_state(ct, "starting")
        while time.monotonic() < deadline:
            ct.reload()
            if ct.status != "running":
                raise DemoError(f"Android 启动失败，容器状态 {ct.status}", 400, "boot_failed")
            _, output, _ = self.exec(ct, ["getprop", "sys.boot_completed"],
                                     timeout=min(self.app.config["EXEC_TIMEOUT"], max(0.05, deadline - time.monotonic())))
            if output.strip() == b"1":
                started = ct.attrs.get("State", {}).get("StartedAt")
                if self.versions.get(ct.name, (None,))[0] != started:
                    _, version, _ = self.exec(ct, ["getprop", "ro.build.version.release"])
                    self.versions[ct.name] = (started, version.decode(errors="replace").strip() or None)
                self._set_state(ct, "ready")
                return
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        self._set_state(ct, "failed", "Android 启动超时；未执行后续操作")
        raise DemoError("Android 启动超时；未执行后续操作", 504, "boot_timeout")

    def info(self, ct, probe=False):
        ct.reload()
        with self.lock:
            if ct.name in self.quarantine and ct.status not in ("running", "restarting", "paused"):
                self.quarantine.discard(ct.name)
                self.busy.discard(ct.name)
            state = self.states.get(ct.name)
            busy = ct.name in self.busy
        started = ct.attrs.get("State", {}).get("StartedAt")
        status, error = (state[1], state[2]) if state and state[0] == started else ("unknown", None)
        if ct.status != "running":
            status = "failed" if error else "stopped"
        elif probe and not busy and status in ("unknown", "starting") and time.monotonic() - self.last_probe.get(ct.name, 0) >= 10:
            try:
                with self.reserve([ct.name]):
                    self.last_probe[ct.name] = time.monotonic()
                    _, output, _ = self.exec(ct, ["getprop", "sys.boot_completed"], timeout=3, readonly=True)
                    status = "ready" if output.strip() == b"1" else "starting"
                    error = None
                    self._set_state(ct, status)
            except DemoError as exc:
                if exc.code != "busy":
                    status, error = "unknown", str(exc)
        bindings = ct.attrs.get("NetworkSettings", {}).get("Ports", {}).get("5555/tcp") or []
        binding = bindings[0] if bindings else None
        config = json.loads(ct.labels.get(LABEL_MANAGER + ".config", "{}"))
        version = self.versions.get(ct.name)
        return {"id": ct.name, "name": config.get("name", ct.name), "image": config.get("image", ct.attrs.get("Config", {}).get("Image", "")),
                "image_id": ct.attrs.get("Image", ""), "docker_status": ct.status, "android_status": status,
                "android_version": version[1] if version and version[0] == started else None,
                "width": config.get("width", 720), "height": config.get("height", 1280), "dpi": config.get("dpi", 320),
                "cpu": config.get("cpu", 2), "memory_mb": config.get("memory_mb", 2048),
                "adb_address": f"{binding['HostIp']}:{binding['HostPort']}" if binding else None,
                "busy": ct.name in self.busy, "error": error}

    @contextmanager
    def reserve(self, ids):
        with self.lock:
            if any(key in self.busy for key in ids):
                raise DemoError("设备正忙，请等待当前操作完成", 409, "busy")
            self.busy.update(ids)
        try:
            yield
        finally:
            with self.lock:
                self.busy.difference_update(set(ids) - self.quarantine)

    def schedule(self, action, targets, function, creates=False):
        """Reserve every target atomically before enqueueing individual workers."""
        with self.lock:
            active = sum(job["status"] in ("queued", "running") for job in self.jobs.values())
            if active >= 10:
                raise DemoError("任务队列已满（最多 10 个活动任务）", 409, "queue_full")
            ids = [target[0] for target in targets]
            if self.busy.intersection(ids):
                raise DemoError("目标中有设备正忙，未提交任何操作", 409, "busy")
            if creates:
                existing = {ct.name for ct in self.containers()} | self.creating
                if len(existing) + len(targets) > MAX_INSTANCES:
                    raise DemoError("Demo 最多保留 3 台实例，请先删除不用的实例", 409, "capacity")
                self.creating.update(ids)
            while len(self.jobs) >= 50:
                old = next(key for key, value in self.jobs.items() if value["status"] in ("done", "failed"))
                del self.jobs[old]
            job_id = uuid.uuid4().hex
            job = {"id": job_id, "action": action, "status": "queued", "total": len(targets), "done": 0, "results": []}
            self.jobs[job_id] = job
            self.busy.update(ids)
            for target in targets:
                self.executor.submit(self._run, job, target, function)
            return job_id

    def _run(self, job, target, function):
        key, name, payload = target
        with self.lock:
            job["status"] = "running"
        try:
            data = function(key, payload)
            result = {"instance_id": data.get("id", key) if isinstance(data, dict) else key,
                      "name": name, "status": "success", "message": "操作完成", "data": data or {}}
        except Exception as exc:
            result = {"instance_id": key, "name": name, "status": "error", "message": str(exc)}
            try:
                ct = self.owned(key)
                self._set_state(ct, "failed", str(exc))
            except Exception:
                pass
        finally:
            with self.lock:
                self.creating.discard(key)
                if key not in self.quarantine:
                    self.busy.discard(key)
        with self.lock:
            job["results"].append(result)
            job["done"] += 1
            if job["done"] == job["total"]:
                job["status"] = "done" if all(item["status"] == "success" for item in job["results"]) else "failed"

    def create(self, key, config):
        volume_name = key + "-data"
        ct = None
        volume = None
        try:
            volume = self.client.volumes.create(name=volume_name, labels={LABEL_MANAGER: "1", LABEL_INSTANCE: key})
            # RedroidManager create_instance command and volume setup, corrected.
            ct = self.client.containers.create(
                image=config["image_id"], name=key, privileged=True,
                ports={"5555/tcp": ("127.0.0.1", None)},
                volumes={volume_name: {"bind": "/data", "mode": "rw"}},
                command=["androidboot.use_memfd=true", f"androidboot.redroid_width={config['width']}",
                         f"androidboot.redroid_height={config['height']}", f"androidboot.redroid_dpi={config['dpi']}",
                         "androidboot.redroid_fps=15", "androidboot.redroid_gpu_mode=guest"],
                nano_cpus=int(config["cpu"] * 1_000_000_000), mem_limit=f"{config['memory_mb']}m",
                labels={LABEL_MANAGER: "1", LABEL_INSTANCE: key,
                        LABEL_MANAGER + ".config": json.dumps(config, ensure_ascii=False)})
            ct.start()
            ct.reload()
            self.wait_ready(ct)
            return self.info(ct)
        except Exception as exc:
            errors = []
            if ct is None:
                try:
                    ct = self.owned(key)  # create request might have succeeded before transport failed.
                except DemoError as lookup:
                    if lookup.code not in ("not_found", "not_owned"):
                        errors.append(f"容器创建结果未知：{lookup}")
                except Exception as lookup:
                    errors.append(f"容器创建结果未知：{lookup}")
            if ct is not None:
                try:
                    self.delete(key)
                    volume = None
                except Exception as cleanup:
                    errors.append(str(cleanup))
            if ct is None:
                try:
                    self.remove_volume(volume_name, key)
                except Exception as cleanup:
                    errors.append(str(cleanup))
            detail = f"；清理失败：{'; '.join(errors)}" if errors else "；本次资源已回收"
            raise DemoError(f"创建失败：{exc}{detail}", 400, "create_failed") from exc

    def remove_volume(self, name, instance_id):
        try:
            volume = self.client.volumes.get(name)
        except docker.errors.NotFound:
            return
        labels = volume.attrs.get("Labels") or {}
        if labels.get(LABEL_MANAGER) != "1" or labels.get(LABEL_INSTANCE) != instance_id:
            raise DemoError(f"拒绝删除归属不匹配的数据卷 {name}", 409, "volume_not_owned")
        volume.remove()

    def delete(self, key):
        ct = self.owned(key)
        volume_name = key + "-data"
        # Verify the expected volume BEFORE destroying the container.
        try:
            volume = self.client.volumes.get(volume_name)
            if (volume.attrs.get("Labels") or {}).get(LABEL_INSTANCE) != key or (volume.attrs.get("Labels") or {}).get(LABEL_MANAGER) != "1":
                raise DemoError("数据卷归属不匹配，未删除容器", 409, "volume_not_owned")
        except docker.errors.NotFound:
            pass
        ct.stop(timeout=3)
        ct.remove()
        try:
            self.remove_volume(volume_name, key)
        except Exception as exc:
            raise DemoError(f"容器已删除，但数据卷 {volume_name} 清理失败：{exc}", 400, "cleanup_failed") from exc
        with self.lock:
            self.states.pop(key, None)
            self.versions.pop(key, None)
            self.sizes.pop(key, None)
            self.last_screen.pop(key, None)
            self.last_probe.pop(key, None)
            self.quarantine.discard(key)
        return {"id": key, "removed": True, "volume": volume_name}

    def action(self, key, data):
        action = data["action"]
        if action == "delete":
            return self.delete(key)
        ct = self.owned(key)
        if action == "stop":
            ct.stop(timeout=3)
            self._set_state(ct, "stopped")
        elif action in ("start", "restart"):
            self.preflight(self.info(ct)["image"])
            if action == "restart":
                ct.restart(timeout=3)
            else:
                ct.start()
            ct.reload()
            self.wait_ready(ct)
        else:
            self.wait_ready(ct)
            if action == "open_settings":
                _, output, stderr = self.exec(ct, ["am", "start", "-a", "android.settings.SETTINGS"])
                self.check_activity(output + stderr)
            elif action == "launch":
                _, output, _ = self.exec(ct, ["cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", data["package"]])
                component = next((line for line in output.decode(errors="replace").splitlines() if re.fullmatch(r"[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+", line)), None)
                if not component:
                    raise DemoError("未找到该应用的 launcher activity", 400, "no_launcher")
                _, output, stderr = self.exec(ct, ["am", "start", "-n", component])
                self.check_activity(output + stderr)
            elif action == "install":
                return self.install(ct, data["apk_id"])
            elif action == "root_check":
                checks = {}
                # Fixed shell literals only: missing optional tools must return
                # 127, not an OCI exec-start error that looks like lost control.
                for name, argv in (("container_exec_uid", ["id"]),
                                   ("magisk_version", ["/system/bin/sh", "-c", "magisk -v"]),
                                   ("shell_su", ["/system/bin/sh", "-c", "su -c id"])):
                    code, output, error = self.exec(ct, argv, check=False)
                    checks[name] = {"argv": argv, "exit_code": code, "stdout": output.decode(errors="replace").strip(),
                                    "stderr": error.decode(errors="replace").strip()}
                return {"id": key, "checks": checks, "host_adb_root": "unverified", "app_root": "unverified",
                        "note": "容器 exec UID / shell su 不能证明应用级 root；宿主 ADB 与独立 APK 需另行验证"}
        return self.info(ct)

    @staticmethod
    def check_activity(output):
        if re.search(rb"(?:Error:|Exception|does not exist|unable to resolve)", output, re.I):
            raise DemoError(output.decode(errors="replace").strip(), 400, "launch_failed")

    def capture(self, ct):
        _, png, _ = self.exec(ct, ["screencap", "-p"])
        if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n" or png[12:16] != b"IHDR":
            raise DemoError("设备未返回有效 PNG", 503, "invalid_screen")
        size = struct.unpack(">II", png[16:24])
        if not all(1 <= value <= 8192 for value in size):
            raise DemoError("截图尺寸无效", 503, "invalid_screen")
        self.sizes[ct.name] = size
        return png

    def require_ready(self, ct):
        info = self.info(ct)
        if info["docker_status"] != "running" or info["android_status"] != "ready":
            raise DemoError("Android 尚未就绪，请先启动并等待设备 ready", 409, "not_ready")

    def input(self, ct, data):
        action = data.get("action")
        if action in ("tap", "swipe"):
            self.capture(ct)  # Re-read dimensions: orientation may have changed since the browser's last frame.
            width, height = self.sizes[ct.name]
            keys = ("x", "y") if action == "tap" else ("x1", "y1", "x2", "y2")
            values = [integer(data, field, None, 0, (width if field.startswith("x") else height) - 1) for field in keys]
            argv = ["input", action, *map(str, values)]
            if action == "swipe":
                argv.append("300")
        elif action == "key":
            code = data.get("code")
            if type(code) is not int or code not in KEYS:
                raise DemoError("不支持的系统按键")
            argv = ["input", "keyevent", str(code)]
        elif action == "text":
            value = data.get("text")
            if not isinstance(value, str) or not 1 <= len(value) <= 200 or any(ord(c) < 32 or ord(c) > 126 for c in value):
                raise DemoError("仅支持 1–200 个可打印 ASCII 字符；暂不支持中文输入")
            # Android input text replaces the literal sequence %s with spaces.
            # Send % separately so user text like '100%s' remains literal.
            pieces = re.split(r"(%)", value)
            deadline = time.monotonic() + self.app.config["EXEC_TIMEOUT"]
            for piece in pieces:
                if piece:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise DemoError("文字输入达到时间上限；前面部分可能已输入", 504, "input_timeout")
                    self.exec(ct, ["input", "text", piece.replace(" ", "%s")], timeout=remaining)
            return
        else:
            raise DemoError("未知输入操作")
        self.exec(ct, argv)

    def apks(self):
        result = []
        for path in self.upload_dir.glob("*.json"):
            try:
                item = json.loads(path.read_text())
                if (self.upload_dir / (item["id"] + ".apk")).is_file():
                    result.append(item)
            except (OSError, ValueError, KeyError):
                continue
        return result

    def apk_path(self, apk_id):
        if not isinstance(apk_id, str) or not re.fullmatch(r"[0-9a-f]{32}", apk_id):
            raise DemoError("APK 不存在", 404, "apk_missing")
        path = self.upload_dir / (apk_id + ".apk")
        if not path.is_file():
            raise DemoError("APK 不存在", 404, "apk_missing")
        return path

    def install(self, ct, apk_id):
        path = self.apk_path(apk_id)
        name = apk_id + ".apk"
        remote_path = "/data/local/tmp/" + name
        # Adapted from upstream _do_install_one: tar.add + put_archive + pm.
        error = None
        try:
            with tempfile.TemporaryFile() as stream:
                with tarfile.open(fileobj=stream, mode="w") as archive:
                    archive.add(path, arcname=name)
                stream.seek(0)
                if not ct.put_archive("/data/local/tmp", stream):
                    raise DemoError("APK 传输失败", 400, "install_failed")
            code, output, stderr = self.exec(ct, ["pm", "install", "-r", remote_path], timeout=120, check=False)
            if code != 0 or not re.search(rb"^Success\s*$", output, re.M):
                raise DemoError(f"APK 安装失败（{code}）：{(output + stderr).decode(errors='replace').strip()}", 400, "install_failed")
            return {"id": ct.name, "apk_id": apk_id, "output": output.decode().strip()}
        except Exception as exc:
            error = exc
            raise
        finally:
            try:
                ct.reload()
                if ct.status != "running":
                    raise DemoError(f"实例已停止，临时 APK 可能残留于 {remote_path}")
                self.exec(ct, ["rm", "-f", remote_path])
            except Exception as cleanup:
                raise DemoError(f"{str(error) + '；' if error else ''}临时 APK 清理失败：{cleanup}", 400, "apk_cleanup_failed") from cleanup


def create_app(client=None, config=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(
        MAX_CONTENT_LENGTH=MAX_APK + 1024 * 1024,
        UPLOAD_DIR=os.getenv("REDROID_UPLOAD_DIR", str(BASE_DIR / ".data" / "apks")),
        STATIC_DIR=os.getenv("REDROID_STATIC_DIR", str(BASE_DIR / "frontend" / "dist")),
        HOST_PROC=os.getenv("REDROID_HOST_PROC", "/host/proc"), HOST_DEV=os.getenv("REDROID_HOST_DEV", "/host/dev"),
        IMAGES=[part.strip() for part in os.getenv("REDROID_IMAGES", f"{DEFAULT_IMAGE},{ROOT_IMAGE}").split(",") if part.strip()],
        BOOT_TIMEOUT=float(os.getenv("REDROID_BOOT_TIMEOUT", "180")),
        EXEC_TIMEOUT=float(os.getenv("REDROID_EXEC_TIMEOUT", "15")),
    )
    if config:
        app.config.update(config)
    runtime = Runtime(app, client)
    app.extensions["redroid"] = runtime

    @app.before_request
    def same_origin():
        if urlsplit(request.host_url).hostname not in ("localhost", "127.0.0.1", "::1"):
            raise DemoError("Demo 仅接受 localhost / 127.0.0.1 本机访问", 400, "invalid_host")
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                raise DemoError("拒绝跨来源操作", 400, "cross_origin")
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                raise DemoError("拒绝跨站操作", 400, "cross_origin")
            if request.path != "/api/apks" and not request.is_json:
                raise DemoError("请使用 application/json", 415, "content_type")

    @app.errorhandler(DemoError)
    def demo_error(exc):
        return jsonify(error={"code": exc.code, "message": str(exc)}), exc.status

    @app.errorhandler(docker.errors.DockerException)
    @app.errorhandler(RequestException)
    @app.errorhandler(OSError)
    def docker_error(exc):
        return jsonify(error={"code": "docker_unavailable", "message": f"Docker 操作失败：{exc}"}), 503

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error={"code": "http_error", "message": exc.description}), exc.code

    def body():
        data = request.get_json()
        if not isinstance(data, dict):
            raise DemoError("请求体必须是 JSON object")
        return data

    def accepted(job_id):
        return jsonify(job_id=job_id), 202

    @app.get("/api/environment")
    def environment():
        return jsonify(runtime.environment())

    @app.get("/api/instances")
    def list_instances():
        return jsonify(instances=[runtime.info(ct, probe=True) for ct in runtime.containers()
                                  if ct.labels.get(LABEL_INSTANCE) == ct.name])

    @app.get("/api/instances/<instance_id>")
    def get_instance(instance_id):
        return jsonify(runtime.info(runtime.owned(instance_id), probe=True))

    @app.post("/api/instances")
    def create_instances():
        data = body()
        config = runtime.config(data)
        count = integer(data, "count", 1, 1, MAX_INSTANCES)
        config["image_id"] = runtime.preflight(config["image"])
        targets = []
        for index in range(count):
            target_config = {**config, "name": config["name"] + (f" {index + 1}" if count > 1 else "")}
            targets.append(("afd-" + uuid.uuid4().hex[:16], target_config["name"], target_config))
        return accepted(runtime.schedule("create", targets, runtime.create, creates=True))

    @app.post("/api/instances/<instance_id>/actions")
    def actions(instance_id):
        data = body()
        action = data.get("action")
        if action not in ("start", "stop", "restart", "clone", "delete", "open_settings", "launch", "root_check"):
            raise DemoError("未知实例操作")
        ct = runtime.owned(instance_id)
        if action == "launch" and (not isinstance(data.get("package"), str) or not PACKAGE_RE.fullmatch(data["package"])):
            raise DemoError("package 格式无效")
        info = runtime.info(ct)
        if action == "clone":
            with runtime.reserve([instance_id]):
                config = runtime.config({key: info[key] for key in ("name", "image", "width", "height", "dpi", "cpu", "memory_mb")})
                config["name"] = config["name"][:59] + " 副本"
                runtime.preflight(config["image"])
                # Keep the source's actual immutable image even if its tag moved.
                config["image_id"] = runtime.client.images.get(info["image_id"]).id
                key = "afd-" + uuid.uuid4().hex[:16]
                return accepted(runtime.schedule("clone", [(key, config["name"], config)], runtime.create, creates=True))
        return accepted(runtime.schedule(action, [(instance_id, info["name"], data)], runtime.action))

    @app.post("/api/batches")
    def batches():
        data = body()
        if data.get("action") not in ("start", "stop", "restart", "delete", "install", "open_settings"):
            raise DemoError("未知批量操作")
        ids = data.get("instance_ids")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 3 or any(not isinstance(key, str) for key in ids) or len(set(ids)) != len(ids):
            raise DemoError("请选择 1–3 台不重复实例")
        if data["action"] == "install":
            runtime.apk_path(data.get("apk_id"))
        targets = [(key, runtime.info(runtime.owned(key))["name"], data) for key in ids]
        return accepted(runtime.schedule(data["action"], targets, runtime.action))

    @app.get("/api/jobs")
    def jobs():
        with runtime.lock:
            return jsonify(jobs=copy.deepcopy(list(runtime.jobs.values())), session_id=runtime.session_id)

    @app.get("/api/jobs/<job_id>")
    def job(job_id):
        with runtime.lock:
            if job_id not in runtime.jobs:
                raise DemoError("任务不存在；服务重启会清空任务记录", 404, "job_missing")
            return jsonify(copy.deepcopy(runtime.jobs[job_id]))

    @app.get("/api/instances/<instance_id>/screen")
    def screen(instance_id):
        ct = runtime.owned(instance_id)
        with runtime.reserve([instance_id]):
            runtime.require_ready(ct)
            previous = runtime.last_screen.get(instance_id, 0)
            if time.monotonic() - previous < 1:
                raise DemoError("截图最多每秒一次", 409, "screen_throttled")
            runtime.last_screen[instance_id] = time.monotonic()
            return Response(runtime.capture(ct), mimetype="image/png", headers={"Cache-Control": "no-store"})

    @app.post("/api/instances/<instance_id>/input")
    def input_event(instance_id):
        data = body()
        ct = runtime.owned(instance_id)
        with runtime.reserve([instance_id]):
            runtime.require_ready(ct)
            runtime.input(ct, data)
        return jsonify(ok=True)

    @app.get("/api/instances/<instance_id>/packages")
    def packages(instance_id):
        ct = runtime.owned(instance_id)
        with runtime.reserve([instance_id]):
            runtime.require_ready(ct)
            _, output, _ = runtime.exec(ct, ["pm", "list", "packages", "-3"])
        return jsonify(packages=sorted(set(re.findall(r"^package:(\S+)$", output.decode(), re.M))))

    @app.get("/api/apks")
    def apks():
        return jsonify(apks=runtime.apks())

    @app.post("/api/apks")
    def upload_apk():
        file = request.files.get("file")
        if not file or not file.filename or not file.filename.lower().endswith(".apk"):
            raise DemoError("请上传单个 .apk 文件")
        key = uuid.uuid4().hex
        path = runtime.upload_dir / (key + ".apk")
        try:
            size = 0
            with path.open("xb") as target:
                while chunk := file.stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_APK:
                        raise DemoError("APK 不得超过 256 MiB", 413, "apk_too_large")
                    target.write(chunk)
            with zipfile.ZipFile(path) as archive:
                manifests = [item for item in archive.infolist() if item.filename == "AndroidManifest.xml"]
                if len(manifests) != 1 or manifests[0].file_size == 0 or manifests[0].file_size > 8 * 1024 * 1024 or manifests[0].flag_bits & 1:
                    raise DemoError("APK 缺少有效 AndroidManifest.xml")
                archive.read(manifests[0])  # CRC/integrity of manifest; Android validates the actual APK at install time.
            item = {"id": key, "name": file.filename.replace("\\", "/").split("/")[-1][:200], "size_bytes": size}
            (runtime.upload_dir / (key + ".json")).write_text(json.dumps(item, ensure_ascii=False))
            return jsonify(item), 201
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
            path.unlink(missing_ok=True)
            raise DemoError(f"不是有效 APK ZIP：{exc}") from exc
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @app.get("/")
    def index():
        if not (Path(app.config["STATIC_DIR"]) / "index.html").exists():
            return Response("React 尚未构建。请在 frontend 执行 npm ci && npm run build，或用 Vite 开发入口。", status=503)
        return send_from_directory(app.config["STATIC_DIR"], "index.html")

    @app.get("/<path:path>")
    def static_file(path):
        if path.startswith("api/"):
            raise DemoError("API 不存在", 404, "not_found")
        return send_from_directory(app.config["STATIC_DIR"], path)

    return app


if __name__ == "__main__":
    from waitress import serve
    serve(create_app(), host=os.getenv("REDROID_BIND_HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8080")),
          threads=8, max_request_body_size=MAX_APK + 1024 * 1024)
