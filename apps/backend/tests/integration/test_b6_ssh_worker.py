from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
from itertools import pairwise
from pathlib import Path
from threading import Event, Thread
from typing import Any, BinaryIO

import paramiko
import pytest
from paramiko.common import (
    AUTH_FAILED,
    AUTH_SUCCESSFUL,
    OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED,
    OPEN_SUCCEEDED,
)
from paramiko.sftp import SFTP_PERMISSION_DENIED

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


class _DiskHandle(paramiko.SFTPHandle):
    readfile: BinaryIO
    writefile: BinaryIO


class _DiskSFTP(paramiko.SFTPServerInterface):
    def __init__(
        self,
        server: paramiko.ServerInterface,
        *args: Any,
        root: Path,
        **kwargs: Any,
    ) -> None:
        super().__init__(server, *args, **kwargs)
        self._root = root.resolve()

    def open(
        self, path: str, flags: int, attr: paramiko.SFTPAttributes
    ) -> paramiko.SFTPHandle | int:
        del attr
        target = (self._root / path.lstrip("/")).resolve()
        if not target.is_relative_to(self._root):
            return SFTP_PERMISSION_DENIED
        try:
            descriptor = os.open(target, flags, 0o600)
        except OSError as error:
            return paramiko.SFTPServer.convert_errno(error.errno or 0)
        handle = _DiskHandle(flags)
        if flags & os.O_WRONLY:
            handle.writefile = os.fdopen(descriptor, "wb")
        else:
            handle.readfile = os.fdopen(descriptor, "rb")
        return handle


class _SSHServerInterface(paramiko.ServerInterface):
    def __init__(self, server: _LocalSSHServer) -> None:
        self.server = server

    def check_auth_password(self, username: str, password: str) -> int:
        if username == "tester" and password == "secret":
            return AUTH_SUCCESSFUL
        return AUTH_FAILED

    def get_allowed_auths(self, _username: str) -> str:
        return "password"

    def check_channel_request(self, kind: str, _chanid: int) -> int:
        return (
            OPEN_SUCCEEDED
            if kind == "session"
            else OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        )

    def check_channel_exec_request(
        self, channel: paramiko.Channel, command: bytes
    ) -> bool:
        # Only these local test commands run; no host shell or user credentials.
        scripts = {
            b"printf ok": "import sys; sys.stdout.write('ok\\n')",
            b"unsupported": "import sys; sys.stderr.write('unsupported\\n'); sys.exit(7)",
            b"wait": "import time; time.sleep(60)",
        }
        if command not in scripts:
            return False

        def reply() -> None:
            process = subprocess.Popen(
                [sys.executable, "-c", scripts[command]],
                cwd=self.server.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.server.commands.append(process)
            self.server.command_started.set()
            try:
                while process.poll() is None:
                    transport = channel.get_transport()
                    if (
                        self.server.stop.wait(0.02)
                        or not transport
                        or not transport.is_active()
                    ):
                        return
                output, error = process.communicate(timeout=2)
                channel.sendall(output)
                channel.sendall_stderr(error)
                channel.send_exit_status(process.returncode)
                channel.shutdown_write()
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=2)

        thread = Thread(target=reply, daemon=True)
        self.server.command_threads.append(thread)
        thread.start()
        return True


class _LocalSSHServer:
    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "remote").mkdir(parents=True)
        (root / "remote/source.bin").write_bytes(b"remote-source")
        self.stop = Event()
        self.command_started = Event()
        self.commands: list[subprocess.Popen[bytes]] = []
        self.command_threads: list[Thread] = []
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen()
        self.socket.settimeout(0.1)
        self.port = self.socket.getsockname()[1]
        self.host_key = paramiko.RSAKey.generate(2048)
        self.transports: list[paramiko.Transport] = []
        self.channels: list[paramiko.Channel] = []
        self.thread = Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        self.socket.close()
        for transport in self.transports:
            transport.close()
        self.thread.join(timeout=2)
        for thread in self.command_threads:
            thread.join(timeout=3)
        assert not self.thread.is_alive()
        assert all(not thread.is_alive() for thread in self.command_threads)
        assert all(process.poll() is not None for process in self.commands)

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
                _DiskSFTP,
                root=self.root,
            )
            try:
                transport.start_server(server=_SSHServerInterface(self))
                while transport.is_active() and not self.stop.wait(0.05):
                    channel = transport.accept(0.05)
                    if channel is not None:
                        self.channels.append(channel)
            finally:
                transport.close()


@pytest.mark.asyncio
async def test_real_worker_runs_ssh_family_against_local_server(
    tmp_path: Path,
) -> None:
    server = _LocalSSHServer(tmp_path / "remote-host")
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
                    "remotePath": "/remote/upload.bin",
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
        assert completed[1]["data"] == {"output": "ok\n", "error": "", "exit_code": 0}
        assert (server.root / "remote/upload.bin").read_bytes() == b"local-upload"
        assert (
            artifact_root / "runs" / "ssh-run" / "outputs" / "download.bin"
        ).read_bytes() == b"local-upload"
        assert manager.active_processes() == []
        assert server.transports and not any(t.is_active() for t in server.transports)
        assert any(event.get("type") == "execution:completed" for event in events)
        assert "secret" not in str(events)
    finally:
        await manager.shutdown()
        server.close()


@pytest.mark.asyncio
async def test_worker_closes_ssh_session_after_node_failure(tmp_path: Path) -> None:
    server = _LocalSSHServer(tmp_path / "remote-host")
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
        failed = next(
            event
            for event in events
            if event.get("nodeId") == "fail"
            and event.get("type") == "execution:node_complete"
        )
        assert failed["success"] is False
        assert failed["data"] == {
            "output": "",
            "error": "unsupported\n",
            "exit_code": 7,
        }
        assert manager.active_processes() == []
        assert server.transports
        assert not any(transport.is_active() for transport in server.transports)
        assert "secret" not in str(events)
    finally:
        await manager.shutdown()
        server.close()


def _node(node_id: str, kind: str, **config: Any) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "moduleNode",
        "data": {"moduleType": kind, "config": config},
    }


def _payload(tmp_path: Path, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "runId": "ssh-boundary-run",
        "workflowId": "ssh-boundary-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "workspace"),
        "document": {
            "nodes": nodes,
            "edges": [
                {"id": f"e-{i}", "source": left["id"], "target": right["id"]}
                for i, (left, right) in enumerate(pairwise(nodes))
            ],
            "variables": [],
        },
    }


async def _wait_clean(manager: WorkflowWorkerManager, server: _LocalSSHServer) -> None:
    async with asyncio.timeout(10):
        while (
            manager.busy()
            or any(t.is_active() for t in server.transports)
            or any(p.poll() is None for p in server.commands)
        ):
            await asyncio.sleep(0.02)
    assert manager.active_processes() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["authentication", "missing-file", "disconnected"])
async def test_real_ssh_failures_do_not_run_following_nodes(
    tmp_path: Path, failure: str
) -> None:
    server = _LocalSSHServer(tmp_path / "remote-host")
    server.start()
    events: list[dict[str, Any]] = []
    manager = WorkflowWorkerManager(
        tmp_path, termination_timeout=0.5, on_event=events.append
    )
    nodes = [
        _node(
            "connect",
            "ssh_connect",
            host="127.0.0.1",
            port=server.port,
            username="tester",
            password="wrong" if failure == "authentication" else "secret",
            timeout=5,
        )
    ]
    if failure == "missing-file":
        nodes.append(
            _node(
                "missing",
                "ssh_download_file",
                remotePath="/remote/absent",
                localPath="absent.bin",
            )
        )
    elif failure == "disconnected":
        nodes.extend(
            [
                _node("disconnect", "ssh_disconnect"),
                _node(
                    "after-disconnect",
                    "ssh_execute_command",
                    command="printf ok",
                    timeout=5,
                ),
            ]
        )
    nodes.append(
        _node("must-not-run", "ssh_execute_command", command="printf ok", timeout=5)
    )
    try:
        await manager.start(
            "ssh-boundary-run", "profile-1", None, _payload(tmp_path, nodes)
        )
        await _wait_clean(manager, server)
        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert completed[-1]["success"] is False
        assert (
            completed[-1]["nodeId"]
            == {
                "authentication": "connect",
                "missing-file": "missing",
                "disconnected": "after-disconnect",
            }[failure]
        )
        assert not any(event.get("nodeId") == "must-not-run" for event in events)
        assert any(event.get("type") == "execution:failed" for event in events)
        assert not (
            tmp_path / "workspace/runs/ssh-boundary-run/outputs/absent.bin"
        ).exists()
        assert server.transports
        assert "secret" not in str(events)
    finally:
        await manager.shutdown()
        server.close()


@pytest.mark.asyncio
async def test_stopping_real_ssh_command_closes_worker_and_connection(
    tmp_path: Path,
) -> None:
    server = _LocalSSHServer(tmp_path / "remote-host")
    server.start()
    events: list[dict[str, Any]] = []
    manager = WorkflowWorkerManager(
        tmp_path, termination_timeout=0.5, on_event=events.append
    )
    nodes = [
        _node(
            "connect",
            "ssh_connect",
            host="127.0.0.1",
            port=server.port,
            username="tester",
            password="secret",
            timeout=5,
        ),
        _node("waiting", "ssh_execute_command", command="wait", timeout=60),
        _node("must-not-run", "ssh_execute_command", command="printf ok", timeout=5),
    ]
    try:
        await manager.start(
            "ssh-boundary-run", "profile-1", None, _payload(tmp_path, nodes)
        )
        assert await asyncio.to_thread(server.command_started.wait, 5)
        assert manager.busy() and manager.active_processes()
        async with asyncio.timeout(5):
            await manager.stop("ssh-boundary-run")
            await _wait_clean(manager, server)
        assert server.transports
        assert not any(event.get("nodeId") == "must-not-run" for event in events)
        assert not any(
            event.get("type") == "execution:node_complete"
            and event.get("nodeId") == "waiting"
            and event.get("success") is True
            for event in events
        )
        assert "secret" not in str(events)
    finally:
        await manager.shutdown()
        server.close()


def _serve_fixture() -> None:
    """Expose the same loopback service to the separately scheduled Electron test."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--status", required=True, type=Path)
    args = parser.parse_args()
    server = _LocalSSHServer(args.root)
    signal.signal(signal.SIGTERM, lambda *_: server.stop.set())
    signal.signal(signal.SIGINT, lambda *_: server.stop.set())

    def close_on_eof() -> None:
        sys.stdin.read()
        server.stop.set()

    Thread(target=close_on_eof, daemon=True).start()

    def report(closed: bool = False) -> None:
        value = {
            "port": server.port,
            "closed": closed,
            "connections": len(server.transports),
            "activeConnections": sum(t.is_active() for t in server.transports),
            "commands": [p.poll() for p in server.commands],
        }
        temporary = args.status.with_suffix(".tmp")
        temporary.write_text(json.dumps(value), encoding="utf-8")
        temporary.replace(args.status)

    server.start()
    try:
        report()
        while not server.stop.wait(0.05):
            report()
    finally:
        server.close()
        report(closed=True)


if __name__ == "__main__":
    _serve_fixture()
