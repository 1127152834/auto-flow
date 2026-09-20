from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import BinaryOutputSnapshot, ExecutionContext


class SSHGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, integration: str, payload: dict[str, Any]) -> Any:
        self.calls.append((integration, payload))
        if integration == "ssh_execute":
            return {"output": "ok\n", "error": "", "exitCode": 0}
        if integration == "ssh_download":
            return {"content": b"downloaded", "identity": "remote-v1"}
        return {"ok": True}


class SSHArtifacts:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.outputs: dict[str, bytes] = {"upload.txt": b"uploaded"}

    async def read_binary_output(
        self, *, output_path: str, max_bytes: int
    ) -> BinaryOutputSnapshot:
        content = self.outputs[output_path]
        assert len(content) <= max_bytes
        return BinaryOutputSnapshot(content, f"local:{len(content)}")

    async def write_binary_output(
        self,
        *,
        output_path: str,
        content: bytes,
        mime_type: str,
        expected_identity: str | None = None,
    ) -> str:
        del mime_type, expected_identity
        self.outputs[output_path] = content
        return str(self.root / output_path)

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        raise NotImplementedError

    async def write_text(self, **_kwargs: Any) -> str:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_ssh_family_uses_named_provider_session_and_artifact_boundary(
    tmp_path: Path,
) -> None:
    gateway = SSHGateway()
    artifacts = SSHArtifacts(tmp_path)
    context = ExecutionContext(
        variables={"password": "ssh-secret"},
        sensitive_variables={"password"},
        external_integrations=gateway,
        artifacts=artifacts,
    )
    registry = build_production_executor_registry()

    connect = await registry.get("ssh_connect").execute(
        {
            "host": "127.0.0.1",
            "port": 2222,
            "username": "tester",
            "password": "{password}",
            "connectionName": "server",
            "timeout": 5,
        },
        context,
    )
    command = await registry.get("ssh_execute_command").execute(
        {
            "connectionName": "server",
            "command": "printf ok",
            "outputVariable": "out",
            "errorVariable": "err",
            "exitCodeVariable": "code",
            "timeout": 4,
        },
        context,
    )
    upload = await registry.get("ssh_upload_file").execute(
        {
            "connectionName": "server",
            "localPath": "upload.txt",
            "remotePath": "/remote/upload.txt",
        },
        context,
    )
    download = await registry.get("ssh_download_file").execute(
        {
            "connectionName": "server",
            "remotePath": "/remote/download.txt",
            "localPath": "download.txt",
        },
        context,
    )
    disconnect = await registry.get("ssh_disconnect").execute(
        {"connectionName": "server"}, context
    )

    assert all(item.success for item in (connect, command, upload, download, disconnect))
    assert context.variables["out"] == "ok\n"
    assert context.variables["err"] == ""
    assert context.variables["code"] == 0
    assert artifacts.outputs["download.txt"] == b"downloaded"
    assert [name for name, _payload in gateway.calls] == [
        "ssh_connect",
        "ssh_execute",
        "ssh_upload",
        "ssh_download",
        "ssh_disconnect",
    ]
    assert gateway.calls[2][1]["content"] == b"uploaded"
    assert gateway.calls[3][1]["remotePath"] == "/remote/download.txt"
    assert context.node_uses_sensitive_values is True
