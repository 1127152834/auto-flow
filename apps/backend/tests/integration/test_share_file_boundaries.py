from __future__ import annotations

import http.client
import json
import os
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest

from autoflow.infrastructure.sharing.file_share import (
    FileShareHandler,
    ThreadedHTTPServer,
)


@contextmanager
def shared_server(path: Path, kind: str = "folder"):
    handler = type(
        "QaShare",
        (FileShareHandler,),
        {
            "share_config": {"path": str(path), "type": kind, "name": "QA"},
            "allow_write": True,
        },
    )
    server = ThreadedHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def request(port, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def upload(port, filename, data, directory="/"):
    boundary = "AutoFlowOwnedQaUpload"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="path"\r\n\r\n{directory}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return request(
        port,
        "POST",
        "/api/upload",
        body,
        {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )


@pytest.fixture
def files(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    content = Path(__file__).read_bytes()
    (shared / "report.txt").write_bytes(content)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(content)
    return shared, outside, content


@pytest.mark.parametrize("route", ["", "download/", "preview/", "thumb/"])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_every_read_route_rejects_outside_symlink(files, route, method):
    shared, outside, _ = files
    (shared / "linked.txt").symlink_to(outside)
    with shared_server(shared) as port:
        status, _ = request(port, method, f"/{route}linked.txt")
    assert status == 403


@pytest.mark.parametrize(
    "path",
    [
        "/../outside.txt",
        "/%2e%2e/outside.txt",
        "/download/%2e%2e%2foutside.txt",
        "/download/..%5coutside.txt",
        "/download/C:%5coutside.txt",
        "/download/%00",
    ],
)
def test_invalid_paths_are_explicitly_rejected(files, path):
    with shared_server(files[0]) as port:
        assert request(port, "GET", path)[0] == 403


def test_authorized_file_unicode_query_range_and_head(files):
    shared, _, content = files
    (shared / "中文 空格.txt").write_bytes(content)
    with shared_server(shared) as port:
        assert request(port, "GET", "/report.txt?download=1") == (200, content)
        assert request(
            port, "GET", "/download/%E4%B8%AD%E6%96%87%20%E7%A9%BA%E6%A0%BC.txt"
        ) == (200, content)
        assert request(port, "HEAD", "/download/report.txt") == (200, b"")
        assert request(
            port, "GET", "/download/report.txt", headers={"Range": "bytes=1-4"}
        ) == (206, content[1:5])


def test_single_file_head_cannot_read_sibling(files):
    shared, _, content = files
    (shared / "sibling.txt").write_bytes(content)
    with shared_server(shared / "report.txt", "file") as port:
        assert request(port, "GET", "/download") == (200, content)
        assert request(port, "HEAD", "/sibling.txt")[0] == 404
        assert upload(port, "new.txt", content)[0] == 403


def test_preview_explicitly_reports_unsupported(files):
    with shared_server(files[0]) as port:
        status, body = request(port, "GET", "/preview/report.txt")
    assert status == 415
    assert "暂不支持" in body.decode()
    assert b"No module named" not in body


def test_duplicate_upload_never_follows_existing_or_dangling_links(files):
    shared, outside, content = files
    absent = outside.with_name("not-created.txt")
    (shared / "report_1.txt").symlink_to(absent)
    (shared / "report_2.txt").symlink_to(outside)
    with shared_server(shared) as port:
        status, body = upload(port, "report.txt", content)
    assert status == 200
    assert not absent.exists()
    assert outside.read_bytes() == content
    assert (shared / "report_3.txt").read_bytes() == content
    assert json.loads(body)["files"] == ["report_3.txt"]


def test_concurrent_uploads_do_not_overwrite(files):
    shared, _, content = files
    with shared_server(shared) as port, ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: upload(port, "same.txt", content), range(12)))
    assert all(status == 200 for status, _ in results)
    names = [json.loads(body)["files"][0] for _, body in results]
    assert len(set(names)) == 12
    assert all((shared / name).read_bytes() == content for name in names)


def test_upload_rejects_linked_parent(files):
    shared, outside, content = files
    (shared / "escape").symlink_to(outside.parent, target_is_directory=True)
    with shared_server(shared) as port:
        assert upload(port, "new.txt", content, "escape")[0] == 403
    assert not (outside.parent / "new.txt").exists()


def test_incomplete_upload_creates_nothing(files):
    shared, _, _ = files
    before = set(shared.iterdir())
    body = b'--cut\r\nContent-Disposition: form-data; name="file"; filename="partial.txt"\r\n\r\npartial'
    with shared_server(shared) as port:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
            connection.sendall(
                (
                    f"POST /api/upload HTTP/1.0\r\nContent-Type: multipart/form-data; boundary=cut\r\nContent-Length: {len(body) + 100}\r\n\r\n"
                ).encode()
                + body
            )
            connection.shutdown(socket.SHUT_WR)
            response = b""
            while chunk := connection.recv(8192):
                response += chunk
        assert b" 400 " in response.split(b"\r\n", 1)[0]
    assert set(shared.iterdir()) == before


def test_write_failure_removes_only_new_partial_file(files, monkeypatch):
    shared, _, content = files
    before = set(shared.iterdir())

    def fail_sync(_fd):
        raise OSError("QA injected write failure")

    with shared_server(shared) as port:
        monkeypatch.setattr(os, "fsync", fail_sync)
        assert upload(port, "report.txt", content)[0] == 500
    assert set(shared.iterdir()) == before
    assert (shared / "report.txt").read_bytes() == content


def test_listing_mkdir_delete_share_same_boundary(files):
    shared, outside, _ = files
    (shared / "escape").symlink_to(outside.parent, target_is_directory=True)
    with shared_server(shared) as port:
        assert request(port, "GET", "/api/list/escape")[0] == 403
        status, body = request(port, "GET", "/api/list")
        assert status == 200
        assert [item["name"] for item in json.loads(body)["items"]] == ["report.txt"]
        assert (
            request(
                port,
                "POST",
                "/api/mkdir",
                json.dumps({"path": "escape", "name": "new"}).encode(),
            )[0]
            == 403
        )
        assert request(port, "DELETE", "/api/delete/escape/outside.txt")[0] == 403
        assert outside.exists()
        assert (
            request(
                port,
                "POST",
                "/api/mkdir",
                json.dumps({"path": "/", "name": "new"}).encode(),
            )[0]
            == 200
        )
        assert request(port, "DELETE", "/api/delete/new")[0] == 200
        assert request(port, "DELETE", "/api/delete/")[0] == 403


def test_parent_replacement_cannot_redirect_upload(files, monkeypatch):
    shared, outside, content = files
    (shared / "target").mkdir()
    original_open = os.open
    replaced = False

    def swap_before_create(path, flags, *args, **kwargs):
        nonlocal replaced
        if flags & os.O_CREAT and not replaced:
            replaced = True
            (shared / "target").rename(shared / "original")
            (shared / "target").symlink_to(outside.parent, target_is_directory=True)
        return original_open(path, flags, *args, **kwargs)

    # This is an actual filesystem replacement at the creation boundary, not a
    # fake successful open. Windows holds non-delete-sharing handles and refuses
    # the replacement; POSIX continues against the already opened directory.
    with shared_server(shared) as port:
        monkeypatch.setattr(os, "open", swap_before_create)
        status, _ = upload(port, "new.txt", content, "target")
    assert not (outside.parent / "new.txt").exists()
    if os.name == "nt":
        assert status in (403, 500)
    else:
        assert status == 200
        assert (shared / "original/new.txt").read_bytes() == content
