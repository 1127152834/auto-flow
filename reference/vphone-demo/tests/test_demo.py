import base64
import http.client
import json
import plistlib
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import demo


class DemoTests(unittest.TestCase):
    def roundtrip(self, response, command=None):
        # Real Unix socket; fixture is protocol-only, not an iOS runtime.
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            path = Path(directory) / "phone.sock"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen(1)
            received = []

            def serve():
                conn, _ = listener.accept()
                with conn:
                    received.append(json.loads(conn.makefile("rb").readline()))
                    wire = json.dumps(response).encode() + b"\n"
                    for part in (wire[:5], wire[5:]):
                        conn.sendall(part)

            worker = threading.Thread(target=serve, daemon=True)
            worker.start()
            try:
                result = demo.exchange(path, command or {"t": "screenshot"}, timeout=1)
            finally:
                worker.join(2)
                listener.close()
            return result, received[0]

    def test_socket_fragmentation_and_real_pixel_mapping(self):
        command = demo.wire_command({"t": "tap", "x": 0.5, "y": 0.25}, 1290, 2796)
        frame = base64.b64encode(b"\xff\xd8\xff\xe0test\xff\xd9").decode()
        result, sent = self.roundtrip({"ok": True, "image": frame}, command)
        self.assertEqual(sent["x"], 644.5)
        self.assertEqual(sent["y"], 698.75)
        self.assertEqual(result["image"], frame)

    def test_no_image_is_failure_even_if_ok_true(self):
        for response in (
            {"ok": True},
            {"ok": False, "error": "no active VM view"},
            {"ok": True, "image": "not-base64"},
            {"ok": True, "image": "AAAA"},
        ):
            with self.subTest(response=response), self.assertRaises(ValueError):
                self.roundtrip(response)

    def test_rejects_unsafe_or_misleading_commands(self):
        invalid = [
            {"t": "shell", "command": "anything"},
            {"t": "screenshot", "path": "/tmp/x"},
            {"t": "tap", "x": 1.1, "y": 0},
            {"t": "tap", "x": float("nan"), "y": 0},
            {"t": "key", "name": "back"},
            {"t": "clipboard", "text": "中" * 1000},
            {"t": "tap", "x": True, "y": 0},
        ]
        for action in invalid:
            with self.subTest(action=action), self.assertRaises(ValueError):
                demo.wire_command(action, 100, 200)
        self.assertEqual(
            demo.wire_command({"t": "clipboard", "text": "中文"}, 100, 200)["t"], "type"
        )

    def test_device_scope_and_actual_plist_dimensions(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(demo, "LIBRARY", Path(directory)),
        ):
            phone = Path(directory) / "demo"
            phone.mkdir()
            (phone / "config.plist").write_bytes(
                plistlib.dumps({"screenConfig": {"width": 720, "height": 1280}})
            )
            self.assertEqual(demo.dimensions(demo.bundle("demo")), (720, 1280))
            self.assertFalse(demo.devices()[0]["socketPresent"])
            for name in ("../demo", "/tmp", ".", "a;ls"):
                with self.assertRaises(ValueError):
                    demo.bundle(name)
            (Path(directory) / "external").symlink_to(phone, target_is_directory=True)
            with self.assertRaises(ValueError):
                demo.bundle("external")

    def test_socket_timeout(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            path = Path(directory) / "phone.sock"
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(str(path))
                listener.listen(1)
                with self.assertRaises(TimeoutError):
                    demo.exchange(path, {"t": "screenshot"}, timeout=0.05)

    def test_http_boundaries(self):
        server = demo.ThreadingHTTPServer(("127.0.0.1", 0), demo.Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for headers in (
                {"Host": "attacker.example"},
                {"Origin": "https://attacker.example"},
                {},
            ):
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
                conn.request(
                    "POST",
                    "/api/action",
                    "{}",
                    headers={"Content-Type": "application/json", **headers},
                )
                self.assertEqual(conn.getresponse().status, 403)
                conn.close()
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
            conn.request(
                "POST",
                "/api/action",
                "{}",
                headers={
                    "Content-Type": "application/json",
                    "X-Demo-Token": demo.TOKEN,
                },
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn("error", json.loads(response.read()))
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(2)


if __name__ == "__main__":
    unittest.main()
