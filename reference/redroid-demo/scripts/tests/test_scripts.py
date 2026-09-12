"""Script regressions without Docker, Android, downloads, or PowerShell execution."""
import ast
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


batch = load("batch_demo", "examples/batch_demo.py")
builder = load("build_root", "scripts/build_root.py")
root_check = load("check_root", "scripts/check_root.py")


class LateCreateClient:
    """Lost create response; device 2 appears only after device 1 was cleaned."""
    def __init__(self):
        self.prefix = None
        self.round = 0
        self.deleted = []

    def request(self, path, body=None, png=False):
        if path == "/api/environment":
            return {"ready": True}
        if path == "/api/jobs":
            if not self.prefix:
                return {"jobs": []}
            self.round += 1
            return {"jobs": [{"id": "create", "action": "create", "status": "running" if self.round < 3 else "done",
                              "results": [] if self.round == 1 else [{"name": self.prefix + " 1"}]}]}
        if path == "/api/instances":
            instances = [{"id": "other", "name": "unrelated"}] if self.prefix else []
            if self.prefix and self.round in (1, 2):
                instance_id = f"ours-{self.round}"
                if instance_id not in self.deleted:
                    instances.append({"id": instance_id, "name": self.prefix + f" {self.round}"})
            return {"instances": instances}
        if path.endswith("/actions"):
            instance_id = path.split("/")[3]
            self.deleted.append(instance_id)
            return {"job_id": instance_id}
        raise AssertionError(path)

    def submit(self, path, body):
        assert path == "/api/instances"
        self.prefix = body["name"]
        raise OSError("Connection lost after accepting creation")

    def wait(self, job_id, timeout=600):
        return {"id": job_id, "status": "done", "results": []}


class ScriptTests(unittest.TestCase):
    def test_loopback_client_bypasses_environment_proxy_but_remote_keeps_it(self):
        import os
        # Use an actual local HTTP server: environment proxy must never receive this request.
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from threading import Thread
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"local": true}')
            def log_message(self, *args):
                pass
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1", "no_proxy": "", "NO_PROXY": ""}):
                client = batch.Client(f"http://127.0.0.1:{server.server_port}")
                self.assertEqual(client.request("/api/environment"), {"local": True})
                remote = batch.Client("http://example.test")
                self.assertTrue(any(getattr(handler, "proxies", {}).get("http") == "http://127.0.0.1:1"
                                    for handler in remote.opener.handlers))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_lost_create_response_cleans_late_instance_and_preserves_unrelated(self):
        client = LateCreateClient()
        with tempfile.TemporaryDirectory() as folder, patch.object(batch.time, "sleep"):
            output = Path(folder) / "run"
            report = batch.run_demo(client, output)
            self.assertEqual(client.deleted, ["ours-1", "ours-2"])
            self.assertEqual(report["remaining_instance_ids"], [])
            self.assertEqual(report["status"], "failed")  # A cleanup success never masks the original error.
            self.assertIn("Connection lost", report["errors"][0])
            self.assertEqual(json.loads((output / "summary.json").read_text())["status"], "failed")

    def test_partial_create_continues_successful_devices_and_cleans_failed_residue(self):
        class PartialCreateClient:
            def __init__(self, failed_survives, lost_success):
                self.prefix = None
                self.failed_survives = failed_survives
                self.lost_success = lost_success
                self.deleted, self.queried, self.opened = [], [], []
            def request(self, path, body=None, png=False):
                if path == "/api/environment":
                    return {"ready": True}
                if path == "/api/jobs":
                    return {"jobs": []}
                if path == "/api/instances":
                    if not self.prefix:
                        return {"instances": []}
                    # Failed cleanup can leave a container; its result ID must remain owned.
                    ids = ["good-1", "good-2"] + (["failed"] if self.failed_survives else [])
                    instances = [{"id": key, "name": "result-ID-is-authoritative" if key == "failed" else self.prefix + " " + key}
                                 for key in ids if key not in self.deleted]
                    return {"instances": instances + [{"id": "unrelated", "name": "someone-else"}]}
                key = path.split("/")[3]
                if path.endswith("/actions"):
                    self.deleted.append(key)
                    return {"job_id": key}
                if png:
                    return b"\x89PNG\r\n\x1a\n"
                self.queried.append(key)
                if key == "failed" or key == self.lost_success:
                    raise batch.ApiError(404, "Container was already removed")
                return {"id": key, "android_status": "ready"}
            def submit(self, path, body):
                if path == "/api/instances":
                    self.prefix = body["name"]
                    return {"status": "failed", "results": [
                        {"instance_id": "failed", "status": "error"},
                        {"instance_id": "good-1", "status": "success"},
                        {"instance_id": "good-2", "status": "success"}]}
                self.opened.extend(body["instance_ids"])
                return {"status": "done", "results": []}
            def wait(self, job_id, timeout=600):
                return {"status": "done", "results": []}
        for failed_survives, lost_success in ((False, None), (True, None), (True, "good-1")):
            with self.subTest(failed_survives=failed_survives, lost_success=lost_success), \
                    tempfile.TemporaryDirectory() as folder, patch.object(batch.time, "sleep"):
                client = PartialCreateClient(failed_survives, lost_success)
                report = batch.run_demo(client, Path(folder) / "run")
                expected = ["good-2"] if lost_success else ["good-1", "good-2"]
                self.assertEqual(client.opened, expected)
                self.assertEqual([item["instance_id"] for item in report["screenshots"]], expected)
                self.assertNotIn("failed", client.queried)
                self.assertEqual("failed" in client.deleted, failed_survives)
                self.assertNotIn("unrelated", client.deleted)
                self.assertEqual(report["remaining_instance_ids"], [])
                self.assertEqual(report["status"], "failed")

    def test_cleanup_deadline_never_claims_success(self):
        client = LateCreateClient()
        client.prefix = "batch-unique"
        client.round = 1
        report = {"errors": [], "cleanup": []}
        batch.cleanup_run(client, client.prefix, set(), set(), set(), report, timeout=0)
        self.assertEqual(report["remaining_instance_ids"], ["ours-1"])
        self.assertTrue(report["errors"])
        self.assertEqual(client.deleted, [])

    def test_root_source_patches_failures_and_bounds_retries_without_importing_upstream(self):
        source = ROOT.parent / "redroid-script"
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            checkout = work / "source"
            for relative in ("redroid.py", "stuff/magisk.py", "stuff/general.py", "tools/helper.py"):
                target = checkout / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / relative, target)
            base_ref = "redroid/redroid@sha256:" + "a" * 64
            builder.patch_source(checkout, work, base_ref, "autoflow/redroid-build:unit-test")
            redroid_tree = ast.parse((checkout / "redroid.py").read_text())
            build_call = next(node for node in ast.walk(redroid_tree)
                              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                              and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess")
            self.assertTrue(next(kw.value.value for kw in build_call.keywords if kw.arg == "check"))
            self.assertIn(base_ref, (checkout / "redroid.py").read_text())
            self.assertNotIn('extract_to = "/tmp/magisk_unpack"', (checkout / "stuff/magisk.py").read_text())
            general_tree = ast.parse((checkout / "stuff/general.py").read_text())
            general_class = next(node for node in general_tree.body if isinstance(node, ast.ClassDef))
            attempts = []
            apk = work / "bad.apk"
            def download(_url, destination):
                attempts.append(destination)
                Path(destination).write_bytes(b"invalid")
                return "bad"
            namespace = {"os": __import__("os"), "hashlib": hashlib, "download_file": download,
                         "print_color": lambda *args: None, "bcolors": SimpleNamespace(YELLOW="")}
            exec(compile(ast.Module(body=[general_class], type_ignores=[]), "patched_general", "exec"), namespace)
            downloader = namespace["General"]()
            downloader.dl_file_name, downloader.act_md5, downloader.dl_link = str(apk), "expected", "unused"
            with self.assertRaises(ValueError):
                downloader.download()
            self.assertEqual(len(attempts), 3)
            # Successful subprocess stderr is progress, not a failure.
            helper_tree = ast.parse((checkout / "tools/helper.py").read_text())
            helper_run = next(node for node in helper_tree.body if isinstance(node, ast.FunctionDef) and node.name == "run")
            namespace = {"subprocess": SimpleNamespace(run=lambda **kwargs: SimpleNamespace(returncode=0, stderr=b"progress"), PIPE=-1)}
            exec(compile(ast.Module(body=[helper_run], type_ignores=[]), "patched_helper", "exec"), namespace)
            self.assertEqual(namespace["run"](["unused"]).returncode, 0)
            with self.assertRaises(RuntimeError):
                builder.patch_source(checkout, work, base_ref, "again")

    def test_root_image_check_does_not_infer_application_permission(self):
        instance = {"adb_address": "127.0.0.1:5555", "android_status": "ready", "image": "test", "image_id": "sha256:test"}
        import io
        def fake_execute(argv, timeout=20):
            return {"command": argv, "exit_code": 0, "stdout": "uid=0(root)", "stderr": ""}
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps(instance).encode())
        with patch.object(root_check, "build_opener", return_value=opener), patch.object(root_check, "execute", side_effect=fake_execute):
            report = root_check.inspect_root("http://localhost:8080", "ours")
        self.assertEqual(report["adb_shell_root"]["status"], "pass")
        self.assertEqual(report["application_root"]["status"], "unverified")

    def test_build_failure_cleanup_timeout_still_writes_original_error(self):
        import io
        import tarfile
        archive = io.BytesIO()
        source = ROOT.parent / "redroid-script"
        with tarfile.open(fileobj=archive, mode="w") as tar:
            for relative in ("redroid.py", "stuff/magisk.py", "stuff/general.py", "tools/helper.py"):
                tar.add(source / relative, arcname=relative)
        def fake_run(argv, **kwargs):
            if argv[0] == "git":
                return SimpleNamespace(stdout=archive.getvalue())
            raise subprocess.TimeoutExpired(argv, 60)
        def fake_command(argv, **kwargs):
            if argv[:2] == ["docker", "info"]:
                return json.dumps({"OSType": "linux", "Architecture": "amd64", "OperatingSystem": "Ubuntu"})
            return builder.SOURCE_SHA
        base = {"Id": "sha256:" + "b" * 64, "Architecture": "amd64", "Os": "linux",
                "RepoDigests": ["redroid/redroid@sha256:" + "a" * 64]}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(builder.platform, "system", return_value="Linux"), \
                patch.object(builder.platform, "machine", return_value="x86_64"), \
                patch.object(builder.shutil, "which", return_value="/usr/bin/tool"), \
                patch.dict(builder.os.environ, {"DOCKER_HOST": "unix:///var/run/docker.sock"}), \
                patch.object(builder, "command", side_effect=fake_command), \
                patch.object(builder, "inspect_image", return_value=base), \
                patch.object(builder.subprocess, "run", side_effect=fake_run), \
                patch.object(builder, "run_logged", side_effect=RuntimeError("Original build failure")):
            output = Path(folder) / "result"
            with self.assertRaisesRegex(RuntimeError, "Original build failure"):
                builder.build(source, output)
            report = json.loads((output / "result.json").read_text())
            self.assertEqual(report["error"], "Original build failure")
            self.assertIn("error", report["temporary_tag_cleanup"][0])
            self.assertTrue(report["base_image"]["build_ref"].startswith("redroid/redroid@sha256:"))


if __name__ == "__main__":
    unittest.main()
