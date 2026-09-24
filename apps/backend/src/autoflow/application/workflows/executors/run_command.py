"""Command executor migrated from WebRPA@5ccb900e.

Source: backend/app/executors/advanced.py#RunCommandExecutor.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_int


class RunCommandExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "run_command"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        command = context.resolve_value(config.get("command", ""))
        shell = context.resolve_value(config.get("shell", "cmd"))
        timeout = max(0, to_int(config.get("timeout", 30), 30, context))
        variable_name = config.get("variableName", "")
        if not command:
            return ModuleResult(success=False, error="命令不能为空")
        try:
            argv = _command_argv(str(command), str(shell))
        except ValueError as error:
            return ModuleResult(success=False, error=f"命令执行失败: {error}")
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except TimeoutError:
                await self.stop_process(process, context)
                return ModuleResult(success=False, error=f"命令执行超时 ({timeout}秒)")
            except BaseException:
                await self.stop_process(process, context)
                raise
            stdout = _decode(stdout_bytes)
            stderr = _decode(stderr_bytes)
            output = (stdout if stdout else stderr).strip()
            if isinstance(variable_name, str) and variable_name:
                context.set_variable(variable_name, output)
            if process.returncode != 0:
                return ModuleResult(
                    success=False,
                    error=(
                        f"命令执行失败 (返回码: {process.returncode}): "
                        f"{stderr or stdout}"
                    ),
                )
            display = f"{output[:100]}..." if len(output) > 100 else output
            return ModuleResult(
                success=True,
                message=f"命令执行成功: {display}",
                data={"output": output, "return_code": process.returncode},
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - process failures become node errors.
            return ModuleResult(success=False, error=f"命令执行失败: {error}")


def _command_argv(command: str, shell: str) -> list[str]:
    if sys.platform == "win32":
        return (
            ["powershell", "-Command", command]
            if shell == "powershell"
            else ["cmd", "/c", command]
        )
    if shell == "powershell":
        executable = shutil.which("pwsh")
        if executable is None:
            raise ValueError("当前系统未安装 PowerShell (pwsh)")
        return [executable, "-Command", command]
    return ["/bin/sh", "-c", command]


def _decode(value: bytes) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value.decode("gbk", errors="ignore")
