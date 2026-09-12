"""Contract and failure tests; fake Engine, no Android compatibility claims."""

import io
import json
import socket
import struct
import tempfile
import threading
import time
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

import docker
from requests import Response

from backend.app import DEFAULT_IMAGE, LABEL_INSTANCE, LABEL_MANAGER, DemoError, create_app


def png(width=720, height=1280):
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"rest-of-test-frame"


class FakeSocket:
    def __init__(self, output, error=b"", hang=False):
        self.data = b"".join(struct.pack(">BxxxI", kind, len(value)) + value
                             for kind, value in ((1, output), (2, error)) if value)
        self.hang = hang
        self.closed = False
        self.sent_chunks = []
        self.shutdown_how = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, size):
        if self.hang:
            time.sleep(min(self.timeout, 0.005))
            raise socket.timeout()
        chunk, self.data = self.data[:7], self.data[7:]  # fragmented Docker headers and payloads
        return chunk

    def close(self):
        self.closed = True

    def sendall(self, chunk):
        self.sent_chunks.append(chunk)

    def shutdown(self, how):
        self.shutdown_how = how


class FakeExec:
    def __init__(self):
        self.calls = []
        self.created = {}
        self.outputs = {}
        self.stdin_enabled = {}
        self.sockets = {}
        self.boot = b"1\n"
        self.boot_outputs = []
        self.gate = None
        self.entered = threading.Event()

    def exec_create(self, container, argv, **kwargs):
        self.calls.append((container, argv))
        exec_id = uuid.uuid4().hex
        self.stdin_enabled[exec_id] = kwargs["stdin"]
        if argv == ["getprop", "sys.boot_completed"]:
            default = self.boot_outputs.pop(0) if self.boot_outputs else (0, self.boot, b"", False)
        elif argv == ["getprop", "ro.build.version.release"]:
            default = (0, b"13\n", b"", False)
        elif argv == ["screencap", "-p"]:
            default = (0, png(), b"", False)
        elif argv[:2] == ["pm", "install"]:
            default = (0, b"Success\n", b"", False)
        elif argv == ["id"]:
            default = (0, b"uid=0(root) gid=0(root)\n", b"", False)
        elif argv == ["/system/bin/sh", "-c", "/sbin/magisk -v"]:
            default = (127, b"", b"magisk: not found", False)
        elif argv == ["/system/bin/sh", "-c", "/sbin/su -c id"]:
            default = (127, b"", b"su: not found", False)
        else:
            default = (0, b"", b"", False)
        self.created[exec_id] = self.outputs.get(tuple(argv), default)
        return {"Id": exec_id}

    def exec_start(self, exec_id, **kwargs):
        self.entered.set()
        if self.gate is not None:
            self.gate.wait(5)
        code, output, error, hang = self.created[exec_id]
        self.sockets[exec_id] = FakeSocket(output, error, hang)
        return self.sockets[exec_id]

    def exec_inspect(self, exec_id):
        code, output, error, hang = self.created[exec_id]
        return {"Running": hang, "ExitCode": None if hang else code}


class FakeVolume:
    def __init__(self, manager, name, labels):
        self.manager = manager
        self.name = name
        self.attrs = {"Labels": labels}
        self.remove_error = None

    def remove(self):
        if self.remove_error:
            raise self.remove_error
        del self.manager.items[self.name]


class FakeVolumes:
    def __init__(self):
        self.items = {}

    def create(self, name, labels):
        volume = FakeVolume(self, name, labels)
        self.items[name] = volume
        return volume

    def get(self, name):
        if name not in self.items:
            raise docker.errors.NotFound("no volume")
        return self.items[name]


class FakeContainer:
    def __init__(self, manager, kwargs):
        self.manager = manager
        self.name = kwargs["name"]
        self.id = self.name
        self.labels = kwargs["labels"]
        self.status = "created"
        self.start_error = None
        self.stop_error = None
        self.stop_count = 0
        self.uploads = []
        self.attrs = {"State": {"StartedAt": "2026-09-13T00:00:00Z"}, "Image": kwargs["image"],
                      "Config": {"Image": kwargs["image"]},
                      "NetworkSettings": {"Ports": {"5555/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(40000 + len(manager.items))}]}}}

    def start(self):
        if self.start_error:
            raise self.start_error
        self.status = "running"

    def restart(self, **kwargs):
        self.start()

    def stop(self, **kwargs):
        self.stop_count += 1
        if self.stop_error:
            raise self.stop_error
        self.status = "exited"

    def remove(self):
        del self.manager.items[self.name]

    def reload(self):
        pass

    def put_archive(self, destination, stream):
        self.uploads.append((destination, stream.read()))
        return True


class FakeContainers:
    def __init__(self):
        self.items = {}
        self.created = []
        self.next_start_error = None

    def list(self, all, filters):
        return [item for item in list(self.items.values()) if item.labels.get(LABEL_MANAGER) == "1"]

    def get(self, name):
        if name not in self.items:
            raise docker.errors.NotFound("no container")
        return self.items[name]

    def create(self, **kwargs):
        self.created.append(kwargs)
        ct = FakeContainer(self, kwargs)
        ct.start_error = self.next_start_error
        self.items[ct.name] = ct
        return ct


class FakeImage:
    id = "sha256:verified-image"
    attrs = {"Architecture": "amd64", "Os": "linux", "RepoDigests": ["redroid/redroid@sha256:verified"]}


class FakeImages:
    def get(self, ref):
        if ref not in (DEFAULT_IMAGE, FakeImage.id):
            raise docker.errors.ImageNotFound("not cached")
        return FakeImage()


class FakeDocker:
    def __init__(self):
        self.api = FakeExec()
        self.containers = FakeContainers()
        self.volumes = FakeVolumes()
        self.images = FakeImages()
        self.host = {"Name": "wsl-engine", "OperatingSystem": "Ubuntu 24.04", "OSType": "linux", "Architecture": "x86_64"}

    def info(self):
        return self.host


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "proc").mkdir()
        (root / "proc" / "filesystems").write_text("nodev binder\n")
        self.engine = FakeDocker()
        self.app = create_app(self.engine, {"TESTING": True, "UPLOAD_DIR": str(root / "apks"),
                                           "HOST_PROC": str(root / "proc"), "HOST_DEV": str(root / "dev"),
                                           "EXEC_TIMEOUT": 0.02, "BOOT_TIMEOUT": 0.02})
        self.http = self.app.test_client()
        self.runtime = self.app.extensions["redroid"]

    def tearDown(self):
        if self.engine.api.gate:
            self.engine.api.gate.set()
        self.runtime.executor.shutdown(wait=True)
        self.temp.cleanup()

    def wait_job(self, response):
        self.assertEqual(response.status_code, 202, response.get_json())
        key = response.get_json()["job_id"]
        for attempt in range(200):
            job = self.http.get("/api/jobs/" + key).get_json()
            if job["status"] in ("done", "failed"):
                return job
            time.sleep(0.005)
        self.fail("job did not finish")

    def create(self, count=1):
        job = self.wait_job(self.http.post("/api/instances", json={"name": "test", "count": count}))
        self.assertEqual(job["status"], "done", job)
        return [item["instance_id"] for item in job["results"]]

    def action(self, key, action, **data):
        return self.wait_job(self.http.post(f"/api/instances/{key}/actions", json={"action": action, **data}))

    def upload(self, content=None):
        if content is None:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"test manifest")
            content = stream.getvalue()
        return self.http.post("/api/apks", data={"file": (io.BytesIO(content), "../../Demo.apk")})

    def test_environment_reports_supported_cache_and_optional_root_absent(self):
        result = self.http.get("/api/environment").get_json()
        self.assertTrue(result["ready"])
        self.assertEqual(result["images"][0]["id"], FakeImage.id)
        self.assertFalse(result["images"][1]["cached"])

    def test_desktop_arm_is_explicitly_unsupported_and_create_has_no_side_effect(self):
        self.engine.host.update(OperatingSystem="Docker Desktop", Architecture="aarch64")
        environment = self.http.get("/api/environment").get_json()
        self.assertFalse(environment["ready"])
        self.assertTrue(environment["docker_available"])
        self.assertEqual(self.http.post("/api/instances", json={}).status_code, 503)
        self.assertFalse(self.engine.containers.created)

    def test_linux_architecture_aliases_must_match_the_selected_image(self):
        for daemon_arch, image_arch in (("aarch64", "arm64"), ("arm64", "aarch64"),
                                        ("x86_64", "amd64"), ("amd64", "x86_64")):
            with self.subTest(daemon=daemon_arch, image=image_arch), \
                    patch.object(FakeImage, "attrs", {"Architecture": image_arch, "Os": "linux"}):
                self.engine.host["Architecture"] = daemon_arch
                environment = self.http.get("/api/environment").get_json()
                self.assertTrue(environment["ready"])
                self.assertTrue(environment["images"][0]["compatible"])
                self.assertEqual(environment["images"][0]["architecture"], image_arch)
                self.assertEqual(self.runtime.preflight(DEFAULT_IMAGE), FakeImage.id)

    def test_incompatible_images_and_unsupported_hosts_never_create(self):
        for host_os, daemon_arch, image_os, image_arch, error in (
                ("linux", "aarch64", "linux", "amd64", "image_architecture"),
                ("linux", "amd64", "linux", "arm64", "image_architecture"),
                ("linux", "amd64", "windows", "amd64", "image_architecture"),
                ("linux", "riscv64", "linux", "riscv64", "host_unsupported"),
                ("windows", "amd64", "linux", "amd64", "host_unsupported")):
            with self.subTest(daemon=daemon_arch, image=image_arch, os=host_os), \
                    patch.object(FakeImage, "attrs", {"Architecture": image_arch, "Os": image_os}):
                self.engine.host.update(OSType=host_os, Architecture=daemon_arch)
                self.assertFalse(self.http.get("/api/environment").get_json()["ready"])
                response = self.http.post("/api/instances", json={})
                self.assertEqual(response.get_json()["error"]["code"], error)
                self.assertFalse(self.engine.containers.created)

    def test_custom_arm_image_is_the_default_when_request_omits_image(self):
        image_ref = "redroid/redroid:13.0.0_64only-latest"
        self.app.config["IMAGES"] = [image_ref]
        self.engine.host["Architecture"] = "aarch64"
        with patch.object(FakeImage, "attrs", {"Architecture": "arm64", "Os": "linux"}), \
                patch.object(self.engine.images, "get", return_value=FakeImage()) as get_image:
            key = self.create()[0]
            self.assertEqual(self.runtime.config({})["image"], image_ref)
            self.assertEqual(self.runtime.info(self.engine.containers.items[key])["image"], image_ref)
            get_image.assert_any_call(image_ref)

    def test_missing_host_mount_is_unknown_and_does_not_allow_create(self):
        self.app.config["HOST_PROC"] = "/nonexistent-redroid-test"
        env = self.http.get("/api/environment").get_json()
        self.assertEqual(next(c for c in env["checks"] if c["name"] == "binder")["status"], "unknown")
        self.assertFalse(env["ready"])

    def test_docker_failure_has_diagnostics_without_fake_instances(self):
        with patch.object(self.engine, "info", side_effect=docker.errors.DockerException("offline")):
            response = self.http.get("/api/environment")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.get_json()["docker_available"])
        with patch.object(self.engine.containers, "list", side_effect=docker.errors.DockerException("offline")):
            response = self.http.get("/api/instances")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("instances", response.get_json())

    def test_three_instances_use_private_dynamic_5555_and_distinct_owned_volumes(self):
        keys = self.create(3)
        self.assertEqual(len(set(keys)), 3)
        volumes = []
        for kwargs in self.engine.containers.created:
            self.assertEqual(kwargs["ports"], {"5555/tcp": ("127.0.0.1", None)})
            self.assertEqual(kwargs["image"], FakeImage.id)
            self.assertIn("androidboot.redroid_gpu_mode=guest", kwargs["command"])
            self.assertEqual(kwargs["nano_cpus"], 2_000_000_000)
            self.assertEqual(kwargs["mem_limit"], "2048m")
            volumes.extend(kwargs["volumes"])
        self.assertEqual(len(set(volumes)), 3)
        self.assertEqual(self.http.post("/api/instances", json={}).status_code, 409)
        result = self.http.get("/api/instances").get_json()["instances"]
        self.assertEqual(len({item["adb_address"] for item in result}), 3)
        self.assertEqual({item["android_version"] for item in result}, {"13"})

    def test_capacity_includes_queued_creates_and_maximum_two_workers(self):
        self.engine.api.gate = threading.Event()
        response = self.http.post("/api/instances", json={"count": 3})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(self.engine.api.entered.wait(1))
        self.assertEqual(len(self.runtime.creating), 3)
        self.assertLessEqual(len(self.engine.containers.items), 2)
        self.assertEqual(self.http.post("/api/instances", json={}).status_code, 409)
        self.engine.api.gate.set()

    def test_invalid_types_values_and_uncached_images_rejected(self):
        for data in ({"width": True}, {"height": 0}, {"count": 4}, {"cpu": float("nan")}, {"cpu": True},
                     {"memory_mb": 512.0}, {"image": "untrusted/image"}, {"image": "autoflow/redroid:13-magisk"}):
            with self.subTest(data=data):
                self.assertEqual(self.http.post("/api/instances", json=data).status_code, 400)
        self.assertFalse(self.engine.containers.created)

    def test_create_start_failure_rolls_back_only_its_resources(self):
        existing = self.create()[0]
        self.engine.containers.next_start_error = docker.errors.APIError("start failed")
        job = self.wait_job(self.http.post("/api/instances", json={"name": "bad"}))
        self.assertEqual(job["status"], "failed")
        self.assertIn("本次资源已回收", job["results"][0]["message"])
        self.assertEqual(set(self.engine.containers.items), {existing})
        self.assertEqual(set(self.engine.volumes.items), {existing + "-data"})

    def test_clone_copies_settings_but_creates_empty_new_volume(self):
        key = self.create()[0]
        original_get = self.engine.images.get
        moved = type("MovedImage", (), {"id": "sha256:moved-tag", "attrs": FakeImage.attrs})()
        with patch.object(self.engine.images, "get", side_effect=lambda ref: moved if ref in (DEFAULT_IMAGE, moved.id) else original_get(ref)):
            job = self.action(key, "clone")
        self.assertEqual(job["status"], "done")
        clone = job["results"][0]["instance_id"]
        self.assertNotEqual(key, clone)
        self.assertEqual(len(self.engine.volumes.items), 2)
        self.assertEqual(self.engine.containers.items[clone].uploads, [])
        self.assertEqual(self.engine.containers.created[-1]["image"], FakeImage.id)

    def test_ownership_rejected_for_all_mutation_entrypoints(self):
        key = self.create()[0]
        self.engine.containers.items[key].labels[LABEL_MANAGER] = "somebody-else"
        for suffix, data in (("actions", {"action": "delete"}), ("input", {"action": "key", "code": 3})):
            self.assertEqual(self.http.post(f"/api/instances/{key}/{suffix}", json=data).status_code, 404)
        self.assertEqual(self.http.post("/api/batches", json={"action": "stop", "instance_ids": [key]}).status_code, 404)
        self.assertEqual(self.engine.containers.items[key].stop_count, 0)

    def test_delete_refuses_foreign_volume_and_reports_real_cleanup_failure(self):
        key = self.create()[0]
        volume = self.engine.volumes.items[key + "-data"]
        volume.attrs["Labels"][LABEL_INSTANCE] = "foreign"
        job = self.action(key, "delete")
        self.assertEqual(job["status"], "failed")
        self.assertIn(key, self.engine.containers.items)
        volume.attrs["Labels"][LABEL_INSTANCE] = key
        volume.remove_error = docker.errors.APIError("volume busy")
        job = self.action(key, "delete")
        self.assertEqual(job["status"], "failed")
        self.assertIn("数据卷", job["results"][0]["message"])
        self.assertNotIn(key, self.engine.containers.items)
        self.assertIn(key + "-data", self.engine.volumes.items)

    def test_batch_busy_rejects_every_target_without_partial_scheduling(self):
        one, two = self.create(2)
        before = len(self.runtime.jobs)
        with self.runtime.reserve([two]):
            response = self.http.post("/api/batches", json={"action": "stop", "instance_ids": [one, two]})
            self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.runtime.jobs), before)
        self.assertEqual(self.engine.containers.items[one].stop_count, 0)

    def test_batch_reports_partial_failure_and_releases_nonquarantined_busy(self):
        one, two = self.create(2)
        self.engine.containers.items[one].stop_error = docker.errors.APIError("cannot stop")
        job = self.wait_job(self.http.post("/api/batches", json={"action": "stop", "instance_ids": [one, two]}))
        self.assertEqual(job["status"], "failed")
        self.assertEqual({item["status"] for item in job["results"]}, {"success", "error"})
        self.assertFalse(self.runtime.busy)

    def test_boot_timeout_never_runs_install(self):
        key = self.create()[0]
        apk = self.upload().get_json()["id"]
        self.engine.api.boot = b"0"
        job = self.wait_job(self.http.post("/api/batches", json={"action": "install", "instance_ids": [key], "apk_id": apk}))
        self.assertEqual(job["status"], "failed")
        self.assertFalse(self.engine.containers.items[key].uploads)
        self.assertFalse(any(argv[:2] == ["pm", "install"] for _, argv in self.engine.api.calls))

    def test_boot_retries_missing_getprop_and_readonly_timeout_without_stopping(self):
        self.app.config["BOOT_TIMEOUT"] = 0.3
        for first_probe in ((255, b"", b"exec /bin/getprop: no such file or directory", False),
                            (None, b"", b"", True)):
            with self.subTest(first_probe=first_probe), patch("backend.app.time.sleep"):
                self.engine.api.boot_outputs = [first_probe]
                key = "afd-" + uuid.uuid4().hex[:16]
                self.runtime.create(key, {**self.runtime.config({}), "image_id": FakeImage.id})
                ct = self.engine.containers.items[key]
                self.assertEqual(ct.stop_count, 0)
                self.assertEqual(self.runtime.info(ct)["android_status"], "ready")
                self.assertEqual(self.engine.containers.created[-1]["environment"]["PATH"],
                                 "/sbin:/system/bin:/system/xbin:/vendor/bin")
                self.assertNotIn(key, self.runtime.quarantine)

    def test_persistent_getprop_failure_times_out_and_cleans_created_resources(self):
        self.engine.api.outputs[("getprop", "sys.boot_completed")] = (
            255, b"", b"exec /bin/getprop: no such file or directory", False)
        job = self.wait_job(self.http.post("/api/instances", json={}))
        self.assertEqual(job["status"], "failed")
        self.assertIn("Android 启动超时", job["results"][0]["message"])
        self.assertIn("getprop exit=255", job["results"][0]["message"])
        self.assertIn("no such file", job["results"][0]["message"])
        self.assertIn("本次资源已回收", job["results"][0]["message"])
        self.assertFalse(self.engine.containers.items)
        self.assertFalse(self.engine.volumes.items)
        self.assertFalse(self.runtime.busy)

    def test_exec_timeout_stops_container_before_releasing_busy(self):
        key = self.create()[0]
        ct = self.engine.containers.items[key]
        self.engine.api.outputs[("input", "keyevent", "3")] = (None, b"", b"", True)
        response = self.http.post(f"/api/instances/{key}/input", json={"action": "key", "code": 3})
        self.assertEqual(response.status_code, 504)
        self.assertEqual(ct.status, "exited")
        self.assertNotIn(key, self.runtime.busy)

    def test_exec_timeout_failed_stop_keeps_quarantine_until_stop_confirmed(self):
        key = self.create()[0]
        ct = self.engine.containers.items[key]
        ct.stop_error = docker.errors.APIError("offline")
        self.engine.api.outputs[("input", "keyevent", "3")] = (None, b"", b"", True)
        response = self.http.post(f"/api/instances/{key}/input", json={"action": "key", "code": 3})
        self.assertEqual(response.status_code, 504)
        self.assertIn(key, self.runtime.quarantine)
        self.assertIn(key, self.runtime.busy)
        self.assertEqual(self.http.post(f"/api/instances/{key}/actions", json={"action": "restart"}).status_code, 409)
        ct.status = "exited"
        self.http.get(f"/api/instances/{key}")
        self.assertNotIn(key, self.runtime.busy)

    def test_poll_ready_cache_does_not_exec_and_unknown_probe_cannot_stop_device(self):
        key = self.create()[0]
        calls = len(self.engine.api.calls)
        self.http.get("/api/instances")
        self.http.get(f"/api/instances/{key}")
        self.assertEqual(len(self.engine.api.calls), calls)
        self.runtime.states.clear()
        with patch.object(self.runtime, "exec", side_effect=DemoError("slow", 504, "probe_timeout")) as probe:
            info = self.http.get(f"/api/instances/{key}").get_json()
            self.assertEqual(info["android_status"], "unknown")
            self.assertTrue(probe.call_args.kwargs["readonly"])
        self.assertEqual(self.engine.containers.items[key].stop_count, 0)

    def test_png_is_single_no_store_frame_rate_limited_and_real_dimensions_used(self):
        key = self.create()[0]
        self.engine.api.outputs[("screencap", "-p")] = (0, png(1280, 720), b"warning", False)
        response = self.http.get(f"/api/instances/{key}/screen")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "image/png")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.data, png(1280, 720))
        self.assertEqual(self.http.get(f"/api/instances/{key}/screen").status_code, 409)
        self.assertEqual(self.http.post(f"/api/instances/{key}/input", json={"action": "tap", "x": 1000, "y": 600}).status_code, 200)
        self.assertEqual(self.http.post(f"/api/instances/{key}/input", json={"action": "tap", "x": 1000, "y": 800}).status_code, 400)
        self.assertIn((key, ["input", "tap", "1000", "600"]), self.engine.api.calls)

    def test_text_uses_argv_spaces_literal_percent_s_and_rejects_unicode(self):
        key = self.create()[0]
        route = f"/api/instances/{key}/input"
        self.assertEqual(self.http.post(route, json={"action": "text", "text": "x y 100%s;$(id)"}).status_code, 200)
        commands = [argv for _, argv in self.engine.api.calls if argv[:2] == ["input", "text"]]
        self.assertEqual(commands, [["input", "text", "x%sy%s100"], ["input", "text", "%"], ["input", "text", "s;$(id)"]])
        self.assertEqual(self.http.post(route, json={"action": "text", "text": "中文"}).status_code, 400)
        self.assertEqual(self.http.post(route, json={"action": "key", "code": 999}).status_code, 400)

    def test_apk_validation_unique_storage_and_pm_failure_with_zero_exit(self):
        self.assertEqual(self.upload(b"not zip").status_code, 400)
        self.assertFalse(list(self.runtime.upload_dir.glob("*.apk")))
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        item = response.get_json()
        self.assertEqual(item["name"], "Demo.apk")
        self.assertEqual(len(item["id"]), 32)
        key = self.create()[0]
        remote = "/data/local/tmp/" + item["id"] + ".apk"
        self.engine.api.outputs[("pm", "install", "-r", remote)] = (0, b"Failure [INVALID_APK]\n", b"", False)
        job = self.wait_job(self.http.post("/api/batches", json={"action": "install", "instance_ids": [key], "apk_id": item["id"]}))
        self.assertEqual(job["status"], "failed")
        self.assertIn((key, ["rm", "-f", remote]), self.engine.api.calls)

    @staticmethod
    def archive_pivot_error(message="Error setting up pivot dir: mkdir /.pivot_root: read-only file system"):
        response = Response()
        response.status_code = 500
        return docker.errors.APIError("archive failed", response=response, explanation=message)

    def test_magisk_archive_pivot_failure_streams_exact_apk_and_half_closes_stdin(self):
        key = self.create()[0]
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"manifest")
            archive.writestr("assets/binary", b"\x00\xff" * 70000)
        apk = self.upload(content.getvalue()).get_json()["id"]
        remote = "/data/local/tmp/" + apk + ".apk"
        with patch.object(self.engine.containers.items[key], "put_archive", side_effect=self.archive_pivot_error()):
            job = self.wait_job(self.http.post("/api/batches", json={"action": "install", "instance_ids": [key], "apk_id": apk}))
        self.assertEqual(job["status"], "done", job)
        self.assertEqual(job["results"][0]["data"]["transport"], "exec_stdin")
        streams = [self.engine.api.sockets[exec_id] for exec_id, enabled in self.engine.api.stdin_enabled.items() if enabled]
        self.assertEqual(len(streams), 1)
        self.assertEqual(b"".join(streams[0].sent_chunks), content.getvalue())
        self.assertGreater(len(streams[0].sent_chunks), 1)
        self.assertLessEqual(max(map(len, streams[0].sent_chunks)), 65536)
        self.assertEqual(streams[0].shutdown_how, socket.SHUT_WR)
        self.assertTrue(streams[0].closed)
        self.assertIn((key, ["rm", "-f", remote]), self.engine.api.calls)
        self.assertEqual(self.engine.containers.items[key].stop_count, 0)

    def test_other_archive_errors_do_not_enable_fallback(self):
        key = self.create()[0]
        apk = self.upload().get_json()["id"]
        with patch.object(self.engine.containers.items[key], "put_archive", side_effect=self.archive_pivot_error("permission denied")):
            job = self.wait_job(self.http.post("/api/batches", json={"action": "install", "instance_ids": [key], "apk_id": apk}))
        self.assertEqual(job["status"], "failed")
        self.assertIn("permission denied", job["results"][0]["message"])
        self.assertFalse(any(self.engine.api.stdin_enabled.values()))
        self.assertFalse(any(argv[:2] == ["pm", "install"] for _, argv in self.engine.api.calls))
        self.assertIn((key, ["rm", "-f", "/data/local/tmp/" + apk + ".apk"]), self.engine.api.calls)

    def test_apk_stdin_command_failure_cleans_file_and_never_installs(self):
        key = self.create()[0]
        apk = self.upload().get_json()["id"]
        remote = "/data/local/tmp/" + apk + ".apk"
        argv = ["/system/bin/sh", "-c", 'cat > "$1"', "sh", remote]
        self.engine.api.outputs[tuple(argv)] = (2, b"", b"No space left on device", False)
        with patch.object(self.engine.containers.items[key], "put_archive", side_effect=self.archive_pivot_error()):
            job = self.wait_job(self.http.post("/api/batches", json={"action": "install", "instance_ids": [key], "apk_id": apk}))
        self.assertEqual(job["status"], "failed")
        self.assertIn("No space left", job["results"][0]["message"])
        self.assertFalse(any(command[:2] == ["pm", "install"] for _, command in self.engine.api.calls))
        self.assertIn((key, ["rm", "-f", remote]), self.engine.api.calls)
        self.assertEqual(self.engine.containers.items[key].stop_count, 0)

    def test_uncertain_apk_stdin_transfer_stops_device_and_reports_cleanup_unconfirmed(self):
        for failure in (BrokenPipeError("partial send lost"), socket.timeout("send deadline exceeded")):
            with self.subTest(failure=failure):
                key = self.create()[0]
                apk = self.upload().get_json()["id"]
                with patch.object(self.engine.containers.items[key], "put_archive", side_effect=self.archive_pivot_error()), \
                        patch.object(FakeSocket, "sendall", side_effect=failure):
                    job = self.wait_job(self.http.post("/api/batches", json={"action": "install", "instance_ids": [key], "apk_id": apk}))
                self.assertEqual(job["status"], "failed")
                self.assertIn("临时 APK 清理失败", job["results"][0]["message"])
                self.assertIn("可能残留", job["results"][0]["message"])
                self.assertEqual(self.engine.containers.items[key].status, "exited")
                self.assertFalse(any(command[:2] == ["pm", "install"] for device, command in self.engine.api.calls if device == key))

    def test_root_diagnostics_never_infer_app_root_from_uid_zero(self):
        key = self.create()[0]
        job = self.action(key, "root_check")
        self.assertEqual(job["status"], "done")
        data = job["results"][0]["data"]
        self.assertEqual(data["app_root"], "unverified")
        self.assertEqual(data["host_adb_root"], "unverified")
        self.assertIn("uid=0", data["checks"]["container_exec_uid"]["stdout"])
        self.assertEqual(data["checks"]["magisk_version"]["exit_code"], 127)
        self.assertEqual(data["checks"]["shell_su"]["exit_code"], 127)
        self.assertEqual(self.engine.containers.items[key].stop_count, 0)
        self.assertEqual(self.engine.containers.items[key].status, "running")
        self.assertEqual(data["checks"]["magisk_version"]["argv"], ["/system/bin/sh", "-c", "/sbin/magisk -v"])
        self.assertEqual(data["checks"]["shell_su"]["argv"], ["/system/bin/sh", "-c", "/sbin/su -c id"])

    def test_activity_error_on_stderr_is_not_reported_as_success(self):
        key = self.create()[0]
        self.engine.api.outputs[("am", "start", "-a", "android.settings.SETTINGS")] = (0, b"", b"Error: unable to resolve Intent", False)
        job = self.action(key, "open_settings")
        self.assertEqual(job["status"], "failed")
        self.assertIn("unable to resolve", job["results"][0]["message"])

    def test_exec_transport_failure_does_not_release_running_command(self):
        key = self.create()[0]
        with patch.object(self.engine.api, "exec_start", side_effect=docker.errors.APIError("connection lost")):
            response = self.http.post(f"/api/instances/{key}/input", json={"action": "key", "code": 3})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.engine.containers.items[key].status, "exited")
        self.assertFalse(self.runtime.busy)

    def test_jobs_are_bounded_and_session_changes_for_new_process_state(self):
        for index in range(50):
            self.runtime.jobs[str(index)] = {"status": "done"}
        self.create()
        self.assertEqual(len(self.runtime.jobs), 50)
        self.assertNotIn("0", self.runtime.jobs)
        self.assertEqual(self.http.get("/api/jobs").get_json()["session_id"], self.runtime.session_id)
        self.runtime.jobs = {str(index): {"status": "queued"} for index in range(10)}
        self.assertEqual(self.http.post("/api/instances", json={}).status_code, 409)

    def test_cross_origin_wrong_host_json_and_unknown_routes(self):
        self.assertEqual(self.http.post("/api/instances", json={}, headers={"Origin": "https://evil.example"}).status_code, 400)
        self.assertEqual(self.http.get("/api/environment", headers={"Host": "evil.example"}).status_code, 400)
        self.assertEqual(self.http.post("/api/instances", data="{}").status_code, 415)
        self.assertEqual(self.http.post("/api/instances", json=[]).status_code, 400)
        self.assertEqual(self.http.get("/api/not-a-route").status_code, 404)


if __name__ == "__main__":
    unittest.main()
