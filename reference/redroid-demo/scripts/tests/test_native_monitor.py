import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("native_monitor", Path(__file__).parents[1] / "native_monitor.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
ID = "afd-ef3857a550924052"


class NativeMonitorTests(unittest.TestCase):
    def test_origin_host_and_payload_rejected_before_start(self):
        launcher = native.Launcher()
        client = native.create_app(launcher).test_client()
        with patch.object(launcher, "open") as opened:
            for host, origin, body, expected in [
                ("127.0.0.1:8082", "https://other.test", {"instance_id": ID}, 403),
                ("other.test:8082", "http://other.test:8082", {"instance_id": ID}, 400),
                ("127.0.0.1:8082", "http://127.0.0.1:8082", {"instance_id": ID, "command": "anything"}, 400),
            ]:
                r = client.post("/api/native/open", base_url="http://" + host,
                                headers={"Origin": origin}, json=body)
                self.assertEqual(r.status_code, expected)
            opened.assert_not_called()

    def test_id_and_address_validation_and_duplicate_window(self):
        launcher = native.Launcher()
        for value in (None, "../../tmp", "afd-x;echo test"):
            with self.assertRaises(native.NativeError):
                launcher.open(value)
        for value in (None, "192.168.1.2:5555", "127.0.0.1:0", "127.0.0.1:65536"):
            with self.assertRaises(native.NativeError):
                native.guest_port(value)
        self.assertEqual(native.guest_port("127.0.0.1:32768"), 32768)
        launcher.worker = SimpleNamespace(is_alive=lambda: True)
        with self.assertRaisesRegex(native.NativeError, "已有窗口"):
            launcher.open(ID)

    def test_api_identity_mismatch_never_launches_a_process(self):
        launcher = native.Launcher()
        with patch.object(native.shutil, "which", return_value="/tool"), \
                patch.object(native, "command", return_value="guest-session"), \
                patch.object(native, "api", return_value={"session_id": "other-session"}), \
                patch.object(native.subprocess, "Popen") as popen:
            launcher.launch(ID)
            popen.assert_not_called()
            self.assertEqual(launcher.snapshot()["phase"], "failed")
            self.assertIn("不一致", launcher.snapshot()["message"])

    def test_failed_android_start_does_not_launch_viewer(self):
        launcher = native.Launcher()
        replies = [
            {"session_id": "same"},
            {"busy": False, "docker_status": "exited"},
            {"job_id": "job"},
            {"status": "done", "results": [{"status": "error", "message": "boot failed"}]},
        ]
        with patch.object(native.shutil, "which", return_value="/tool"), \
                patch.object(native, "command", return_value="same"), \
                patch.object(native, "api", side_effect=replies), \
                patch.object(native.subprocess, "Popen") as popen:
            launcher.launch(ID)
            popen.assert_not_called()
            self.assertEqual(launcher.snapshot()["phase"], "failed")
            self.assertIn("boot failed", launcher.snapshot()["message"])


if __name__ == "__main__":
    unittest.main()
