from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.database.workflow_mcp import SqlAlchemyWorkflowMcp
from autoflow.providers.mcp import McpManager


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


class WorkflowMcpService:
    def __init__(
        self,
        repository: SqlAlchemyWorkflowMcp,
        credentials: CredentialStore,
        manager: McpManager | None = None,
    ) -> None:
        self._repository = repository
        self._credentials = credentials
        self._manager = manager or McpManager()
        self._command_lock = asyncio.Lock()

    def _read(self) -> tuple[dict[str, Any], int]:
        revision, secret_ref, _digest = self._repository.settings()
        if secret_ref is None:
            return {"mcpServers": {}}, 0
        try:
            payload = self._credentials.read(secret_ref)
        except Exception as error:
            raise WorkflowRunError(
                "MCP_CREDENTIAL_STORE_UNAVAILABLE",
                "系统凭据存储当前不可用",
                503,
            ) from error
        if payload is None:
            raise WorkflowRunError("MCP_CONFIG_UNAVAILABLE", "MCP 配置凭据缺失", 503)
        try:
            config = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WorkflowRunError(
                "MCP_CONFIG_INVALID", "MCP 配置存储内容无效", 500
            ) from error
        if not isinstance(config, dict) or not isinstance(
            config.get("mcpServers"), dict
        ):
            raise WorkflowRunError("MCP_CONFIG_INVALID", "MCP 配置存储内容无效", 500)
        return config, revision

    def config(self) -> dict[str, Any]:
        config, revision = self._read()
        return {**config, "revision": revision}

    def save(
        self,
        *,
        config: dict[str, Any],
        command_id: str,
        expected_revision: int,
    ) -> tuple[dict[str, Any], int]:
        request = {
            "kind": "save",
            "config": config,
            "commandId": command_id,
            "expectedRevision": expected_revision,
        }
        request_hash = hashlib.sha256(_canonical(request)).hexdigest()
        previous = self._repository.command(command_id, request_hash)
        if previous is not None:
            return previous
        config_bytes = _canonical(config)
        secret_ref = f"workflow-mcp/config/{uuid4().hex}"
        try:
            self._credentials.write(secret_ref, config_bytes)
        except Exception as error:
            raise WorkflowRunError(
                "MCP_CREDENTIAL_STORE_UNAVAILABLE",
                "系统凭据存储当前不可用",
                503,
            ) from error
        try:
            receipt, status, old_ref = self._repository.save_settings(
                expected_revision=expected_revision,
                secret_ref=secret_ref,
                config_digest=hashlib.sha256(config_bytes).hexdigest(),
                command_id=command_id,
                request_hash=request_hash,
                now=datetime.now(UTC),
            )
        except Exception:
            try:
                self._credentials.delete(secret_ref)
            except CredentialStoreUnavailableError:
                pass  # Failed save is still authoritative; orphan cleanup can retry later.
            raise
        if old_ref and old_ref != secret_ref:
            try:
                self._credentials.delete(old_ref)
            except CredentialStoreUnavailableError:
                pass  # The new revision is committed; keep it usable.
        return receipt, status

    async def startup(self) -> None:
        config, _revision = self._read()
        await self._manager.reload(config)

    async def reload(
        self, *, command_id: str, expected_revision: int
    ) -> tuple[dict[str, Any], int]:
        request = {
            "kind": "reload",
            "commandId": command_id,
            "expectedRevision": expected_revision,
        }
        request_hash = hashlib.sha256(_canonical(request)).hexdigest()
        async with self._command_lock:
            previous = self._repository.command(command_id, request_hash)
            if previous is not None:
                return previous
            config, revision = self._read()
            if revision != expected_revision:
                raise WorkflowRunError(
                    "MCP_REVISION_CONFLICT",
                    "MCP 配置已由其他窗口修改",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": revision,
                    },
                )
            result = await self._manager.reload(config)
            receipt = {
                **result,
                "commandId": command_id,
                "revision": revision,
            }
            return self._repository.record_command(
                command_id=command_id,
                request_hash=request_hash,
                expected_revision=expected_revision,
                payload=receipt,
                http_status=200,
                now=datetime.now(UTC),
            )

    def status(self) -> dict[str, Any]:
        return self._manager.status()

    def tool_schemas(self) -> list[dict[str, Any]]:
        return self._manager.tool_schemas()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self._manager.call_tool(name, arguments)
        except Exception as error:
            raise WorkflowRunError("MCP_TOOL_FAILED", str(error)[:500], 502) from error

    def command(self, command_id: str) -> dict[str, Any]:
        found = self._repository.command(command_id)
        if found is None:
            raise WorkflowRunError("MCP_COMMAND_NOT_FOUND", "MCP 命令不存在", 404)
        payload, status = found
        return {**payload, "httpStatus": status}

    async def shutdown(self) -> None:
        await self._manager.shutdown()
