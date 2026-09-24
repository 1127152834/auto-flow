from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx
from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from tests.fixtures.model_management import FakeCredentialStore


class FakeWebDav:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.auth: list[tuple[str, str] | None] = []

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        request = httpx.Request(method, url)
        auth = kwargs.get("auth")
        if isinstance(auth, httpx.BasicAuth):
            prepared = httpx.Request("GET", url)
            flow = auth.auth_flow(prepared)
            authenticated = next(flow)
            header = authenticated.headers.get("Authorization", "")
            self.auth.append(("basic", header))
        else:
            self.auth.append(None)
        path = unquote(urlsplit(url).path)
        if method == "MKCOL":
            return httpx.Response(405, request=request)
        if method == "PROPFIND" and kwargs.get("headers", {}).get("Depth") == "0":
            return httpx.Response(207, request=request)
        if method == "PROPFIND":
            rows = "".join(
                f"<d:response><d:href>{name}</d:href><d:propstat><d:prop>"
                f"<d:getcontentlength>{len(content)}</d:getcontentlength>"
                "<d:getlastmodified>Sun, 21 Sep 2026 08:00:00 GMT</d:getlastmodified>"
                "</d:prop></d:propstat></d:response>"
                for name, content in self.files.items()
            )
            return httpx.Response(
                207,
                content=f'<d:multistatus xmlns:d="DAV:">{rows}</d:multistatus>',
                request=request,
            )
        name = path.rsplit("/", 1)[-1]
        if method == "PUT":
            self.files[name] = kwargs["content"]
            return httpx.Response(201, request=request)
        if method == "HEAD":
            return httpx.Response(200 if name in self.files else 404, request=request)
        if method == "GET":
            return httpx.Response(
                200 if name in self.files else 404,
                content=self.files.get(name, b""),
                request=request,
            )
        if method == "DELETE":
            self.files.pop(name, None)
            return httpx.Response(204, request=request)
        raise AssertionError((method, url, kwargs))


def _client(tmp_path: Path) -> tuple[TestClient, FakeCredentialStore]:
    secrets = FakeCredentialStore()
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="studio-webdav",
            instance_token="renderer",
        ),
        credential_store=secrets,
    )
    return TestClient(app, headers={"x-autoflow-token": "renderer"}), secrets


def test_webdav_config_keeps_password_out_of_workspace(tmp_path: Path) -> None:
    client, secrets = _client(tmp_path)
    with client:
        saved = client.post(
            "/api/local-workflows/webdav-config",
            json={
                "enabled": True,
                "url": "https://dav.example.test/root/",
                "username": "alice",
                "password": "never-in-json",
                "remoteDir": "team/workflows",
            },
        )
        assert saved.status_code == 200
        assert saved.json()["config"]["password"] == ""
        assert client.get("/api/local-workflows/webdav-config").json()["config"] == {
            "enabled": True,
            "url": "https://dav.example.test/root/",
            "username": "alice",
            "password": "",
            "remoteDir": "team/workflows",
        }
        original_secret = dict(secrets.values)
        assert client.post(
            "/api/local-workflows/webdav-config",
            json={
                "enabled": True,
                "url": "https://dav.example.test/root/",
                "username": "alice",
                "password": "",
                "remoteDir": "team/renamed",
            },
        ).status_code == 200
        assert secrets.values == original_secret
    assert b"never-in-json" not in (
        tmp_path / "workspace" / "studio-webdav.json"
    ).read_bytes()
    assert any(b"never-in-json" in value for value in secrets.values.values())


def test_enabled_webdav_routes_all_workflow_file_operations_remotely(
    tmp_path: Path, monkeypatch
) -> None:
    remote = FakeWebDav()
    monkeypatch.setattr(httpx, "request", remote.request)
    client, _ = _client(tmp_path)
    config = {
        "enabled": True,
        "url": "https://dav.example.test/root/",
        "username": "alice",
        "password": "secret",
        "remoteDir": "team/workflows",
    }
    document = {"name": "远程流程", "nodes": []}
    with client:
        assert client.post("/api/local-workflows/webdav-config", json=config).status_code == 200
        assert client.post("/api/local-workflows/webdav-test", json=config).json() == {
            "success": True
        }
        assert client.get("/api/local-workflows/default-folder").json()["folder"] == "WebDAV"
        saved = client.post(
            "/api/local-workflows/save-to-folder",
            json={"filename": "remote.json", "content": document, "folder": "/ignored"},
        )
        assert saved.json() == {"success": True, "filename": "remote.json"}
        assert json.loads(remote.files["remote.json"]) == document
        assert client.post(
            "/api/local-workflows/check-exists",
            json={"filename": "remote.json", "folder": None},
        ).json()["exists"] is True
        listed = client.post("/api/local-workflows/list", json={"folder": "WebDAV"})
        assert listed.json()["workflows"][0]["filename"] == "remote.json"
        assert client.get("/api/local-workflows/load/remote.json").json()["content"] == document
        assert client.post(
            "/api/local-workflows/self-heal",
            json={"filename": "remote.json", "folder": None, "enabled": True},
        ).json()["enabled"] is True
        assert json.loads(remote.files["remote.json"])["selfHeal"]["enabled"] is True
        assert client.post(
            "/api/local-workflows/open-folder", json={"folder": "WebDAV"}
        ).status_code == 409
        assert client.post(
            "/api/local-workflows/delete?filename=remote.json&folder=WebDAV"
        ).json() == {"success": True}
        assert remote.files == {}
    assert any(item is not None for item in remote.auth)


def test_webdav_rejects_unsafe_url_and_remote_directory(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    with client:
        for config in (
            {
                "enabled": True,
                "url": "ftp://dav.example.test/",
                "username": "",
                "password": "",
                "remoteDir": "",
            },
            {
                "enabled": True,
                "url": "https://user:pass@dav.example.test/",
                "username": "",
                "password": "",
                "remoteDir": "",
            },
            {
                "enabled": True,
                "url": "https://dav.example.test/",
                "username": "",
                "password": "",
                "remoteDir": "../escape",
            },
        ):
            response = client.post("/api/local-workflows/webdav-config", json=config)
            assert response.status_code == 422


def test_webdav_connection_test_uses_real_http_transport(tmp_path: Path) -> None:
    received: list[tuple[str, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_PROPFIND(self) -> None:
            received.append((self.headers.get("Depth", ""), self.headers.get("Authorization")))
            self.send_response(207)
            self.end_headers()

        def log_message(self, *_args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client, _ = _client(tmp_path)
    try:
        with client:
            response = client.post(
                "/api/local-workflows/webdav-test",
                json={
                    "enabled": True,
                    "url": f"http://127.0.0.1:{server.server_port}/dav/",
                    "username": "alice",
                    "password": "secret",
                    "remoteDir": "workflows",
                },
            )
            assert response.json() == {"success": True}
        assert received[0][0] == "0"
        assert received[0][1] is not None and received[0][1].startswith("Basic ")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
