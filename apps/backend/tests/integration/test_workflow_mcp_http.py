from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway


async def _client(tmp_path, credentials: FakeCredentialStore):
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="mcp-http",
            instance_token="test-token",
        ),
        credential_store=credentials,
        model_gateway=FakeModelGateway(),
    )
    return app, httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"x-autoflow-token": "test-token"},
    )


@pytest.mark.asyncio
async def test_mcp_config_is_revisioned_idempotent_and_keeps_secrets_out_of_sqlite(
    tmp_path,
) -> None:
    credentials = FakeCredentialStore()
    app, client = await _client(tmp_path, credentials)
    config = {
        "mcpServers": {
            "fixture": {
                "transport": "http",
                "url": "https://mcp.example.test/api",
                "headers": {"Authorization": "Bearer secret-for-mcp"},
                "disabled": True,
            }
        }
    }
    request = {
        "commandId": "save-mcp-1",
        "expectedRevision": 0,
        "config": config,
    }
    try:
        initial = await client.get("/api/ai-assistant/mcp/config")
        saved = await client.put("/api/ai-assistant/mcp/config", json=request)
        repeated = await client.put("/api/ai-assistant/mcp/config", json=request)
        restored = await client.get("/api/ai-assistant/mcp/config")
        conflict = await client.put(
            "/api/ai-assistant/mcp/config",
            json={**request, "commandId": "save-mcp-stale"},
        )
        recovered = await client.get("/api/ai-assistant/mcp/commands/save-mcp-1")
    finally:
        await client.aclose()
        await app.state.workflow_services.shutdown()

    assert initial.json() == {"mcpServers": {}, "revision": 0}
    expected = {
        "success": True,
        "saved": True,
        "commandId": "save-mcp-1",
        "revision": 1,
    }
    assert saved.status_code == 200
    assert saved.json() == expected
    assert repeated.json() == expected
    assert restored.json() == {**config, "revision": 1}
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "MCP_REVISION_CONFLICT"
    assert recovered.json() == {**expected, "httpStatus": 200}

    database_path = tmp_path / "data" / "autoflow.sqlite3"
    assert b"secret-for-mcp" not in database_path.read_bytes()
    with sqlite3.connect(database_path) as connection:
        secret_ref = connection.execute(
            "SELECT secret_ref FROM workflow_mcp_settings WHERE id = 1"
        ).fetchone()[0]
    assert credentials.values[secret_ref]


@pytest.mark.asyncio
async def test_mcp_command_id_rejects_different_content(tmp_path) -> None:
    app, client = await _client(tmp_path, FakeCredentialStore())
    request = {
        "commandId": "save-mcp-same-id",
        "expectedRevision": 0,
        "config": {"mcpServers": {}},
    }
    try:
        assert (
            await client.put("/api/ai-assistant/mcp/config", json=request)
        ).status_code == 200
        conflict = await client.put(
            "/api/ai-assistant/mcp/config",
            json={
                **request,
                "config": {"mcpServers": {"other": {"disabled": True}}},
            },
        )
    finally:
        await client.aclose()
        await app.state.workflow_services.shutdown()

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "MCP_IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_mcp_reload_reports_disabled_servers_and_is_idempotent(tmp_path) -> None:
    app, client = await _client(tmp_path, FakeCredentialStore())
    config = {
        "mcpServers": {
            "off": {
                "transport": "stdio",
                "command": "never-started",
                "disabled": True,
            }
        }
    }
    try:
        save = await client.put(
            "/api/ai-assistant/mcp/config",
            json={
                "commandId": "save-before-reload",
                "expectedRevision": 0,
                "config": config,
            },
        )
        assert save.status_code == 200
        request = {"commandId": "reload-mcp-1", "expectedRevision": 1}
        loaded = await client.post("/api/ai-assistant/mcp/reload", json=request)
        repeated = await client.post("/api/ai-assistant/mcp/reload", json=request)
        status = await client.get("/api/ai-assistant/mcp/status")
    finally:
        await client.aclose()
        await app.state.workflow_services.shutdown()

    expected = {
        "connected": [],
        "failed": [],
        "disabled": ["off"],
        "total_servers": 1,
        "commandId": "reload-mcp-1",
        "revision": 1,
    }
    assert loaded.json() == expected
    assert repeated.json() == expected
    assert status.json() == {
        "servers": [
            {
                "name": "off",
                "transport": "stdio",
                "disabled": True,
                "connected": False,
                "tool_count": 0,
                "tools": [],
                "last_error": None,
                "connected_at": None,
                "auto_approve": [],
            }
        ],
        "total_tools_injected": 0,
    }


@pytest.mark.asyncio
async def test_mcp_reload_connects_to_real_stdio_server_and_discovers_tools(
    tmp_path,
) -> None:
    app, client = await _client(tmp_path, FakeCredentialStore())
    server = Path(__file__).parents[1] / "fixtures" / "mcp_stdio_server.py"
    try:
        saved = await client.put(
            "/api/ai-assistant/mcp/config",
            json={
                "commandId": "save-real-mcp",
                "expectedRevision": 0,
                "config": {
                    "mcpServers": {
                        "fixture": {
                            "transport": "stdio",
                            "command": sys.executable,
                            "args": [str(server)],
                        }
                    }
                },
            },
        )
        assert saved.status_code == 200
        loaded = await client.post(
            "/api/ai-assistant/mcp/reload",
            json={"commandId": "reload-real-mcp", "expectedRevision": 1},
        )
        status = await client.get("/api/ai-assistant/mcp/status")
        tool_result = await app.state.workflow_services.mcp.call_tool(
            "mcp__fixture__echo", {"text": "真实调用"}
        )
    finally:
        await client.aclose()
        await app.state.workflow_services.shutdown()

    assert loaded.status_code == 200
    assert loaded.json()["connected"] == [
        {"name": "fixture", "tool_count": 1, "transport": "stdio"}
    ]
    assert loaded.json()["failed"] == []
    assert status.json()["servers"][0]["connected"] is True
    assert status.json()["servers"][0]["tools"] == [
        {"name": "echo", "description": "Return the supplied text"}
    ]
    assert tool_result == {"is_error": False, "content": "echo:真实调用"}
