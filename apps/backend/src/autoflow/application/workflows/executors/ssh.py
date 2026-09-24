"""SSH executors migrated from WebRPA@5ccb900e.

Source: backend/app/executors/ssh.py. License: LICENSE.WebRPA.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float, to_int

MAX_SSH_FILE_BYTES = 64 * 1024 * 1024


async def _call(
    context: ExecutionContext, integration: str, payload: dict[str, Any]
) -> Any:
    if context.external_integrations is None:
        raise RuntimeError("SSH服务不可用")
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()
    result = await context.external_integrations.call(integration, payload)
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()
    return result


def _text(config: Mapping[str, Any], key: str, context: ExecutionContext) -> str:
    value = context.resolve_value(config.get(key, ""))
    return "" if value is None else str(value)


class SSHConnectExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "ssh_connect"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        host = _text(config, "host", context)
        username = _text(config, "username", context)
        password = _text(config, "password", context)
        key_file = _text(config, "keyFile", context)
        if not host or not username:
            return ModuleResult(
                success=False,
                message="SSH连接配置不完整（主机和用户名必填）",
                error="配置不完整",
            )
        if not password and not key_file:
            return ModuleResult(
                success=False, message="必须提供密码或密钥文件", error="认证信息缺失"
            )
        key_content: bytes | None = None
        port = to_int(config.get("port", 22), 22, context)
        if key_file:
            reader = context.node_artifacts
            if reader is None:
                return ModuleResult(success=False, error="运行产物服务不可用")
            try:
                snapshot = await reader.read_binary_output(
                    output_path=key_file, max_bytes=1024 * 1024
                )
                key_content = snapshot.content
            except Exception as error:  # noqa: BLE001 - file errors become node errors.
                return ModuleResult(success=False, error=f"读取SSH密钥失败: {error}")
            if key_content is None:
                return ModuleResult(success=False, error="读取SSH密钥失败")
        try:
            await _call(
                context,
                "ssh_connect",
                {
                    "connectionName": str(config.get("connectionName") or "ssh_conn"),
                    "host": host,
                    "port": port,
                    "username": username,
                    "password": password,
                    "keyContent": key_content,
                    "timeoutSeconds": to_float(config.get("timeout", 30), 30, context),
                },
            )
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=str(error) or "SSH连接失败")
        return ModuleResult(
            success=True, message=f"成功连接到SSH服务器: {username}@{host}:{port}"
        )


class SSHExecuteCommandExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "ssh_execute_command"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        command = _text(config, "command", context)
        if not command:
            return ModuleResult(success=False, message="命令不能为空", error="命令为空")
        try:
            raw = await _call(
                context,
                "ssh_execute",
                {
                    "connectionName": str(config.get("connectionName") or "ssh_conn"),
                    "command": command,
                    "timeoutSeconds": to_float(config.get("timeout", 30), 30, context),
                },
            )
            if not isinstance(raw, Mapping):
                raise TypeError("SSH服务返回格式异常")
            output = str(raw.get("output") or "")
            error = str(raw.get("error") or "")
            exit_code = int(raw.get("exitCode", -1))
        except Exception as exc:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=str(exc) or "SSH命令执行失败")
        context.set_variable(str(config.get("outputVariable") or "ssh_output"), output)
        context.set_variable(str(config.get("errorVariable") or "ssh_error"), error)
        context.set_variable(
            str(config.get("exitCodeVariable") or "ssh_exit_code"), exit_code
        )
        return ModuleResult(
            success=exit_code == 0,
            message=f"命令执行{'成功' if exit_code == 0 else '失败'}，退出码: {exit_code}",
            data={"output": output, "error": error, "exit_code": exit_code},
        )


class SSHUploadFileExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "ssh_upload_file"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        local_path = _text(config, "localPath", context)
        remote_path = _text(config, "remotePath", context)
        if not local_path or not remote_path:
            return ModuleResult(success=False, error="路径为空", message="本地路径和远程路径不能为空")
        reader = context.node_artifacts
        if reader is None:
            return ModuleResult(success=False, error="运行产物服务不可用")
        try:
            snapshot = await reader.read_binary_output(
                output_path=local_path, max_bytes=MAX_SSH_FILE_BYTES
            )
            if snapshot.content is None:
                raise RuntimeError("上传文件不可用")
            await _call(
                context,
                "ssh_upload",
                {
                    "connectionName": str(config.get("connectionName") or "ssh_conn"),
                    "remotePath": remote_path,
                    "content": snapshot.content,
                },
            )
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=f"SSH文件上传失败: {error}")
        return ModuleResult(success=True, message=f"文件上传成功: {local_path} -> {remote_path}")


class SSHDownloadFileExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "ssh_download_file"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        remote_path = _text(config, "remotePath", context)
        local_path = _text(config, "localPath", context)
        if not remote_path or not local_path:
            return ModuleResult(success=False, error="路径为空", message="远程路径和本地路径不能为空")
        writer = context.node_artifacts
        if writer is None:
            return ModuleResult(success=False, error="运行产物服务不可用")
        try:
            raw = await _call(
                context,
                "ssh_download",
                {
                    "connectionName": str(config.get("connectionName") or "ssh_conn"),
                    "remotePath": remote_path,
                    "maxBytes": MAX_SSH_FILE_BYTES,
                },
            )
            if not isinstance(raw, Mapping) or not isinstance(raw.get("content"), bytes):
                raise TypeError("SSH下载结果无效")
            actual_path = await writer.write_binary_output(
                output_path=local_path,
                content=raw["content"],
                mime_type="application/octet-stream",
            )
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=f"SSH文件下载失败: {error}")
        return ModuleResult(
            success=True,
            message=f"文件下载成功: {remote_path} -> {actual_path}",
            data=actual_path,
        )


class SSHDisconnectExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "ssh_disconnect"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        name = str(config.get("connectionName") or "ssh_conn")
        try:
            await _call(context, "ssh_disconnect", {"connectionName": name})
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=str(error) or "SSH断开连接失败")
        return ModuleResult(success=True, message=f"SSH连接 {name} 已断开")


SSH_EXECUTORS = (
    SSHConnectExecutor,
    SSHExecuteCommandExecutor,
    SSHUploadFileExecutor,
    SSHDownloadFileExecutor,
    SSHDisconnectExecutor,
)
