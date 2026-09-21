from __future__ import annotations

import socket
import threading
from pathlib import Path

import httpx
import pytest
from autoflow.infrastructure.sharing import NetworkShareHost, screen_share


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_file_share_serves_two_independent_ports_and_shutdowns(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    first_port, second_port = _port(), _port()
    host = NetworkShareHost()
    try:
        one = await host.perform(
            "start_file_share",
            {
                "path": str(first),
                "port": first_port,
                "shareType": "file",
                "name": first.name,
                "allowWrite": False,
            },
        )
        two = await host.perform(
            "start_file_share",
            {
                "path": str(second),
                "port": second_port,
                "shareType": "file",
                "name": second.name,
                "allowWrite": False,
            },
        )
        assert one.success and two.success and host.busy()
        async with httpx.AsyncClient(trust_env=False) as client:
            first_response = await client.get(
                f"http://127.0.0.1:{first_port}/download"
            )
            second_response = await client.get(
                f"http://127.0.0.1:{second_port}/download"
            )
        assert first_response.content == b"first"
        assert second_response.content == b"second"
    finally:
        await host.shutdown()
    assert host.busy() is False


@pytest.mark.asyncio
async def test_screen_share_serves_frame_and_releases_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Capture:
        def __init__(self, port: int, fps: int, quality: int, scale: float) -> None:
            self.port, self.fps, self.quality, self.scale = port, fps, quality, scale
            self.latest_frame = b"jpeg-frame"
            self.frame_version = 1
            self.frame_lock = threading.Lock()
            self.frame_ready = threading.Event()
            self.stop_event = threading.Event()

        def start(self) -> None:
            self.frame_ready.set()

        def stop(self) -> None:
            self.stop_event.set()

        def join(self, timeout: float) -> None:
            del timeout

        def get_client_count(self) -> int:
            return 0

        def add_client(self, _client: object) -> None:
            return None

        def remove_client(self, _client: object) -> None:
            return None

    monkeypatch.setattr(screen_share, "ScreenCaptureThread", Capture)
    port = _port()
    host = NetworkShareHost()
    try:
        result = await host.perform(
            "start_screen_share",
            {"port": port, "fps": 10, "quality": 60, "scale": 0.5},
        )
        assert result.success and host.busy()
        async with httpx.AsyncClient(trust_env=False) as client:
            frame = await client.get(f"http://127.0.0.1:{port}/frame")
            info = await client.get(f"http://127.0.0.1:{port}/info")
        assert frame.content == b"jpeg-frame"
        assert info.json() == {
            "status": "running",
            "clients": 0,
            "fps": 10,
            "quality": 60,
        }
    finally:
        await host.shutdown()
    assert host.busy() is False


@pytest.mark.asyncio
async def test_writable_folder_share_lists_uploads_creates_and_deletes(
    tmp_path: Path,
) -> None:
    port = _port()
    host = NetworkShareHost()
    try:
        result = await host.perform(
            "start_file_share",
            {
                "path": str(tmp_path),
                "port": port,
                "shareType": "folder",
                "name": "资料",
                "allowWrite": True,
            },
        )
        assert result.success
        base = f"http://127.0.0.1:{port}"
        async with httpx.AsyncClient(trust_env=False) as client:
            listing = await client.get(f"{base}/api/list")
            created = await client.post(
                f"{base}/api/mkdir", json={"path": "/", "name": "新目录"}
            )
            uploaded = await client.post(
                f"{base}/api/upload",
                data={"path": "/"},
                files={"file": ("资料.txt", b"content")},
            )
            deleted = await client.delete(f"{base}/api/delete/资料.txt")
        assert listing.json() == {
            "success": True,
            "path": "/",
            "items": [],
            "shareName": "资料",
        }
        assert created.json()["success"] is True
        assert uploaded.json()["files"] == ["资料.txt"]
        assert deleted.json()["success"] is True
        assert (tmp_path / "新目录").is_dir()
        assert not (tmp_path / "资料.txt").exists()
    finally:
        await host.shutdown()
