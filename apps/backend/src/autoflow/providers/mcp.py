from __future__ import annotations

import asyncio
import hashlib
import os
import re
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client


def _transport(config: dict[str, Any]) -> str:
    explicit = str(config.get("transport") or "").lower().replace("-", "_")
    if explicit:
        return explicit
    if config.get("command"):
        return "stdio"
    return "sse" if "sse" in str(config.get("url") or "").lower() else "http"


def _safe_error(error: BaseException, config: dict[str, Any]) -> str:
    message = str(error) or type(error).__name__
    secrets = [
        *[str(value) for value in (config.get("env") or {}).values()],
        *[str(value) for value in (config.get("headers") or {}).values()],
    ]
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")
    url = str(config.get("url") or "")
    if url:
        parsed = urlsplit(url)
        safe_url = urlunsplit(
            (parsed.scheme, parsed.hostname or "", parsed.path, "", "")
        )
        message = message.replace(url, safe_url)
    return message[:500]


class McpConnection:
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self.transport = _transport(config)
        self.disabled = config.get("disabled") is True
        self.auto_approve = list(config.get("autoApprove") or [])
        self.connected = False
        self.connected_at: str | None = None
        self.last_error: str | None = None
        self.tools: list[dict[str, Any]] = []
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        if self.disabled:
            return
        stack = AsyncExitStack()
        try:
            if self.transport == "stdio":
                command = str(self.config.get("command") or "").strip()
                if not command:
                    raise ValueError("stdio transport 需要 command")
                params = StdioServerParameters(
                    command=command,
                    args=list(self.config.get("args") or []),
                    env={**os.environ, **dict(self.config.get("env") or {})},
                    cwd=self.config.get("cwd") or None,
                )
                read, write = await stack.enter_async_context(stdio_client(params))
            elif self.transport == "sse":
                url = str(self.config.get("url") or "").strip()
                if urlsplit(url).scheme not in {"http", "https"}:
                    raise ValueError("sse transport 需要 HTTP 或 HTTPS URL")
                read, write = await stack.enter_async_context(
                    sse_client(url=url, headers=dict(self.config.get("headers") or {}))
                )
            elif self.transport in {"http", "streamable_http"}:
                url = str(self.config.get("url") or "").strip()
                if urlsplit(url).scheme not in {"http", "https"}:
                    raise ValueError("http transport 需要 HTTP 或 HTTPS URL")
                opened = await stack.enter_async_context(
                    streamablehttp_client(
                        url=url, headers=dict(self.config.get("headers") or {})
                    )
                )
                read, write = opened[0], opened[1]
            else:
                raise ValueError(f"不支持的 transport: {self.transport}")
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            response = await session.list_tools()
            self.tools = [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema
                    if isinstance(tool.inputSchema, dict)
                    else {"type": "object", "properties": {}},
                }
                for tool in response.tools
            ]
            self._stack = stack
            self._session = session
            self.connected = True
            self.connected_at = datetime.now(UTC).isoformat()
        except Exception as error:
            await stack.aclose()
            self.last_error = _safe_error(error, self.config)
            raise

    async def disconnect(self) -> None:
        self.connected = False
        self._session = None
        stack, self._stack = self._stack, None
        if stack is not None:
            await stack.aclose()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._session is None or not self.connected:
            raise RuntimeError(f"MCP 服务器 {self.name} 未连接")
        result = await self._session.call_tool(name, arguments=arguments)
        content = []
        for item in result.content or []:
            if hasattr(item, "text"):
                content.append(str(item.text))
            elif hasattr(item, "data"):
                content.append(f"[binary {len(item.data)} bytes]")
            else:
                content.append(str(item))
        return {
            "is_error": bool(getattr(result, "isError", False)),
            "content": "\n".join(content),
        }


class McpManager:
    def __init__(self) -> None:
        self._connections: dict[str, McpConnection] = {}
        self._tools: dict[str, tuple[McpConnection, str, dict[str, Any]]] = {}

    @staticmethod
    def _tool_name(server: str, tool: str) -> str:
        raw = f"mcp__{server}__{tool}"
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", raw)
        if safe == raw and len(safe) <= 64:
            return safe
        suffix = hashlib.sha256(raw.encode()).hexdigest()[:8]
        return f"{safe[:55]}_{suffix}"

    async def reload(self, config: dict[str, Any]) -> dict[str, Any]:
        await self.shutdown()
        servers = dict(config.get("mcpServers") or {})
        connected: list[dict[str, Any]] = []
        failed: list[dict[str, str]] = []
        disabled: list[str] = []

        async def connect(name: str, server: dict[str, Any]) -> None:
            connection = McpConnection(name, server)
            self._connections[name] = connection
            if connection.disabled:
                disabled.append(name)
                return
            try:
                await connection.connect()
            except Exception:  # noqa: BLE001 - one failed server must not hide others.
                failed.append(
                    {"name": name, "error": connection.last_error or "连接失败"}
                )
            else:
                connected.append(
                    {
                        "name": name,
                        "tool_count": len(connection.tools),
                        "transport": connection.transport,
                    }
                )

        await asyncio.gather(
            *(connect(name, dict(server)) for name, server in servers.items())
        )
        for server, connection in self._connections.items():
            if not connection.connected:
                continue
            for tool in connection.tools:
                name = self._tool_name(server, str(tool["name"]))
                self._tools[name] = (connection, str(tool["name"]), tool)
        return {
            "connected": connected,
            "failed": failed,
            "disabled": disabled,
            "total_servers": len(servers),
        }

    def status(self) -> dict[str, Any]:
        return {
            "servers": [
                {
                    "name": name,
                    "transport": connection.transport,
                    "disabled": connection.disabled,
                    "connected": connection.connected,
                    "tool_count": len(connection.tools),
                    "tools": [
                        {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                        }
                        for tool in connection.tools
                    ],
                    "last_error": connection.last_error,
                    "connected_at": connection.connected_at,
                    # Kept for source compatibility; AutoFlow never uses it to bypass approval.
                    "auto_approve": list(connection.auto_approve),
                }
                for name, connection in self._connections.items()
            ],
            "total_tools_injected": sum(
                len(connection.tools)
                for connection in self._connections.values()
                if connection.connected
            ),
        }

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"[MCP·{connection.name}] {tool.get('description') or tool_name}",
                    "parameters": tool.get("inputSchema")
                    if isinstance(tool.get("inputSchema"), dict)
                    else {"type": "object", "properties": {}},
                },
            }
            for name, (connection, tool_name, tool) in self._tools.items()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        found = self._tools.get(name)
        if found is None:
            raise RuntimeError("MCP 工具不存在或服务器未连接")
        connection, tool_name, _tool = found
        return await connection.call_tool(tool_name, arguments)

    async def shutdown(self) -> None:
        self._tools.clear()
        connections, self._connections = self._connections, {}
        if connections:
            await asyncio.gather(
                *(connection.disconnect() for connection in connections.values()),
                return_exceptions=True,
            )
