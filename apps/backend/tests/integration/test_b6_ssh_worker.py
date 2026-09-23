from __future__ import annotations

import asyncio
import os
import socket
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any

import paramiko
import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


class _MemoryHandle(paramiko.SFTPHandle):
    def __init__(
        self, flags: int, files: dict[str, bytearray], lock: Lock, path: str
    ) -> None:
        super().__init__(flags)
        self._files = files
        self._lock = lock
        self._path = path

    def read(self, offset: int, length: int) -> bytes:
        with self._lock:
            return bytes(self._files.get(self._path, bytearray())[offset : offset + length])

    def write(self, offset: int, data: bytes) -> int:
        with self._lock:
            content = self._files.setdefault(self._path, bytearray())
            if offset > len(content):
                content.extend(b"\0" * (offset - len(content)))
            content[offset : offset + len(data)] = data
        return paramiko.SFTP_OK


class _MemorySFTP(paramiko.SFTPServerInterface):
    def __init__(
        self,
        server: paramiko.ServerInterface,
        *args: Any,
        files: dict[str, bytearray],
        lock: Lock,
        **kwargs: Any,
    ) -> None:
        super().__init__(server, *args, **kwargs)
        self._files = files
        self._lock = lock

    def open(
        self, path: str, flags: int, attr: paramiko.SFTPAttributes
    ) -> _MemoryHandle | int:
        del attr
        with self._lock:
            if flags & os.O_CREAT:
                self._files.setdefault(path, bytearray())
            if flags & os.O_TRUNC:
                self._files[path] = bytearray()
            if path not in self._files:
                return paramiko.SFTP_NO_SUCH_FILE
        return _MemoryHandle(flags, self._files, self._lock, path)


class _SSHServerInterface(paramiko.ServerInterface):
    def check_auth_password(self, username: str, password: str) -> int:
        if username == "tester" and password == "secret":
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, _username: str) -> str:
        return "password"

    def check_channel_request(self, kind: str, _chanid: int) -> int:
        return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_exec_request(
        self, channel: paramiko.Channel, command: bytes
    ) -> bool:
        def reply() -> None:
            if command == b"printf ok":
                channel.send(b"ok\n")
                channel.send_exit_status(0)
            else:
                channel.send_stderr(b"unsupported\n")
                channel.send_exit_status(1)
            channel.shutdown_write()

        Thread(target=reply, daemon=True).start()
        return True


class _LocalSSHServer:
    def __init__(self) -> None:
        self.files: dict[str, bytearray] = {
            "/remote/source.bin": bytearray(b"remote-source")
        }
        self.lock = Lock()
        self.stop = Event()
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen()
        self.socket.settimeout(0.1)
        self.port = self.socket.getsockname()[1]
        self.host_key = paramiko.RSAKey.generate(1024)
        self.transports: list[paramiko.Transport] = []
        self.thread = Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        self.socket.close()
        for transport in self.transports:
            transport.close()
        self.thread.join(timeout=2)

    def _serve(self) -> None:
        while not self.stop.is_set():
            try:
                client, _address = self.socket.accept()
            except (TimeoutError, OSError):
                continue
            transport = paramiko.Transport(client)
            self.transports.append(transport)
            transport.add_server_key(self.host_key)
            transport.set_subsystem_handler(
                "sftp",
                paramiko.SFTPServer,
                _MemorySFTP,
                files=self.files,
                lock=self.lock,
            )
            try:
                transport.start_server(server=_SSHServerInterface())
                while transport.is_active() and not self.stop.wait(0.05):
                    transport.accept(0.05)
            finally:
                transport.close()


@pytest.mark.asyncio
async def test_real_worker_runs_ssh_family_against_local_server(
    tmp_path: Path,
) -> None:
    server = _LocalSSHServer()
    server.start()
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    artifact_root = tmp_path / "workspace"
    upload = artifact_root / "runs" / "ssh-run" / "outputs" / "upload.bin"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"local-upload")
    nodes = [
        {
            "id": "connect",
            "type": "moduleNode",
            "data": {
                "moduleType": "ssh_connect",
                "config": {
                    "connectionName": "fixture",
                    "host": "127.0.0.1",
                    "port": server.port,
                    "username": "tester",
                    "password": "secret",
                    "timeout": 5,
                },
            },
        },
        {
            "id": "command",
            "type": "moduleNode",
            "data": {
                "moduleType": "ssh_execute_command",
                "config": {
                    "connectionName": "fixture",
                    "command": "printf ok",
                    "outputVariable": "out",
                    "timeout": 5,
                },
            },
        },
        {
            "id": "upload",
            "type": "moduleNode",
            "data": {
                "moduleType": "ssh_upload_file",
                "config": {
                    "connectionName": "fixture",
                    "localPath": "upload.bin",
                    "remotePath": "/remote/upload.bin",
                },
            },
        },
        {
            "id": "download",
            "type": "moduleNode",
            "data": {
                "moduleType": "ssh_download_file",
                "config": {
                    "connectionName": "fixture",
                    "remotePath": "/remote/source.bin",
                    "localPath": "download.bin",
                },
            },
        },
        {
            "id": "disconnect",
            "type": "moduleNode",
            "data": {
                "moduleType": "ssh_disconnect",
                "config": {"connectionName": "fixture"},
            },
        },
    ]
    try:
        await manager.start(
            "ssh-run",
            "profile-1",
            None,
            {
                "runId": "ssh-run",
                "workflowId": "ssh-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(artifact_root),
                "document": {
                    "nodes": nodes,
                    "edges": [
                        {
                            "id": f"edge-{index}",
                            "source": nodes[index]["id"],
                            "target": nodes[index + 1]["id"],
                        }
                        for index in range(len(nodes) - 1)
                    ],
                    "variables": [],
                },
            },
        )
        for _ in range(1000):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert manager.busy() is False
        assert len(completed) == 5
        assert all(event.get("success") is True for event in completed)
        assert bytes(server.files["/remote/upload.bin"]) == b"local-upload"
        assert (
            artifact_root / "runs" / "ssh-run" / "outputs" / "download.bin"
        ).read_bytes() == b"remote-source"
        assert any(event.get("type") == "execution:completed" for event in events)
        assert "secret" not in str(events)
    finally:
        await manager.shutdown()
        server.close()


@pytest.mark.asyncio
async def test_worker_closes_ssh_session_after_node_failure(tmp_path: Path) -> None:
    server = _LocalSSHServer()
    server.start()
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        await manager.start(
            "ssh-failure-run",
            "profile-1",
            None,
            {
                "runId": "ssh-failure-run",
                "workflowId": "ssh-failure-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "workspace"),
                "document": {
                    "nodes": [
                        {
                            "id": "connect",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "ssh_connect",
                                "config": {
                                    "host": "127.0.0.1",
                                    "port": server.port,
                                    "username": "tester",
                                    "password": "secret",
                                    "timeout": 5,
                                },
                            },
                        },
                        {
                            "id": "fail",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "ssh_execute_command",
                                "config": {"command": "unsupported", "timeout": 5},
                            },
                        },
                    ],
                    "edges": [
                        {"id": "connect-fail", "source": "connect", "target": "fail"}
                    ],
                    "variables": [],
                },
            },
        )
        for _ in range(1000):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)
        for _ in range(100):
            if server.transports and not any(
                transport.is_active() for transport in server.transports
            ):
                break
            await asyncio.sleep(0.01)

        assert any(event.get("type") == "execution:failed" for event in events)
        assert server.transports
        assert not any(transport.is_active() for transport in server.transports)
        assert "secret" not in str(events)
    finally:
        await manager.shutdown()
        server.close()
