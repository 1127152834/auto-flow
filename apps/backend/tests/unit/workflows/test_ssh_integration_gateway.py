from __future__ import annotations

from typing import Any, Self

import pytest

from autoflow.providers.integrations import WorkflowIntegrationGateway


class _Channel:
    def recv_exit_status(self) -> int:
        return 0


class _Stream:
    channel = _Channel()

    def __init__(self, content: bytes) -> None:
        self.content = content

    def read(self, _size: int = -1) -> bytes:
        return self.content


class _RemoteFile:
    def __init__(self, files: dict[str, bytes], path: str, mode: str) -> None:
        self.files = files
        self.path = path
        self.mode = mode

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def write(self, content: bytes) -> None:
        self.files[self.path] = content

    def read(self, size: int = -1) -> bytes:
        return self.files[self.path][:size]


class _SFTP:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def file(self, path: str, mode: str) -> _RemoteFile:
        return _RemoteFile(self.files, path, mode)


class _SSHClient:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {"/remote/source": b"downloaded"}
        self.closed = False
        self.connect_args: dict[str, Any] = {}

    def set_missing_host_key_policy(self, _policy: object) -> None:
        return None

    def connect(self, **kwargs: Any) -> None:
        self.connect_args = kwargs

    def exec_command(self, command: str, *, timeout: float):
        assert command == "printf ok"
        assert timeout == 4
        return _Stream(b""), _Stream(b"ok\n"), _Stream(b"")

    def open_sftp(self) -> _SFTP:
        return _SFTP(self.files)

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_ssh_gateway_owns_named_session_and_closes_it(monkeypatch) -> None:
    client = _SSHClient()
    monkeypatch.setattr("paramiko.SSHClient", lambda: client)
    gateway = WorkflowIntegrationGateway()

    await gateway.call(
        "ssh_connect",
        {
            "connectionName": "server",
            "host": "127.0.0.1",
            "port": 2222,
            "username": "tester",
            "password": "secret",
            "timeoutSeconds": 5,
        },
    )
    command = await gateway.call(
        "ssh_execute",
        {
            "connectionName": "server",
            "command": "printf ok",
            "timeoutSeconds": 4,
        },
    )
    await gateway.call(
        "ssh_upload",
        {
            "connectionName": "server",
            "remotePath": "/remote/upload",
            "content": b"uploaded",
        },
    )
    download = await gateway.call(
        "ssh_download",
        {
            "connectionName": "server",
            "remotePath": "/remote/source",
            "maxBytes": 64,
        },
    )

    assert client.connect_args["allow_agent"] is False
    assert client.connect_args["look_for_keys"] is False
    assert command == {"output": "ok\n", "error": "", "exitCode": 0}
    assert client.files["/remote/upload"] == b"uploaded"
    assert download == {"content": b"downloaded"}

    await gateway.close()

    assert client.closed is True
    with pytest.raises(RuntimeError, match="SSH连接 server 不存在"):
        await gateway.call(
            "ssh_execute", {"connectionName": "server", "command": "true"}
        )


@pytest.mark.asyncio
async def test_ssh_download_rejects_oversized_remote_file(monkeypatch) -> None:
    client = _SSHClient()
    client.files["/remote/source"] = b"too-large"
    monkeypatch.setattr("paramiko.SSHClient", lambda: client)
    gateway = WorkflowIntegrationGateway()
    await gateway.call(
        "ssh_connect",
        {"host": "host", "username": "user", "password": "secret"},
    )

    with pytest.raises(RuntimeError, match="64 MiB"):
        await gateway.call(
            "ssh_download", {"remotePath": "/remote/source", "maxBytes": 3}
        )

    await gateway.close()
