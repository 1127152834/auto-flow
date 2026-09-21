"""Python script executor migrated from WebRPA@5ccb900e.

Source: backend/app/executors/python_script.py. License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_bool, to_int

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def _local_no_proxy_env(env: dict[str, str]) -> dict[str, str]:
    existing = env.get("NO_PROXY") or env.get("no_proxy") or ""
    items = [item.strip() for item in existing.split(",") if item.strip()]
    lowered = {item.lower() for item in items}
    for host in _LOCAL_HOSTS:
        if host not in lowered:
            items.append(host)
            lowered.add(host)
    merged = ",".join(items)
    return {"NO_PROXY": merged, "no_proxy": merged}


class PythonScriptExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "python_script"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        script_mode = str(config.get("scriptMode", "content"))
        script_content = context.resolve_value(config.get("scriptContent", ""))
        script_path = context.resolve_value(config.get("scriptPath", ""))
        python_path = context.resolve_value(config.get("pythonPath", ""))
        script_args = context.resolve_value(config.get("scriptArgs", ""))
        working_dir = context.resolve_value(config.get("workingDir", ""))
        timeout = max(0, to_int(config.get("timeout", 60), 60, context))
        capture_output = to_bool(config.get("captureOutput", True), True, context)

        if context.sensitive_variables:
            context.mark_sensitive_use()

        temporary_paths: list[Path] = []
        try:
            interpreter = self._interpreter(config, python_path)
            script_file, result_file = self._script(
                script_mode, script_content, script_path, temporary_paths
            )
            environment = os.environ.copy()
            environment.update(_local_no_proxy_env(environment))
            environment["WEBRPA_VARS"] = json.dumps(
                context.variables, ensure_ascii=False, default=str
            )
            command = [interpreter, script_file]
            if script_args:
                command.extend(str(script_args).split())
            cwd = (
                str(working_dir)
                if working_dir and Path(str(working_dir)).exists()
                else None
            )
            return await self._run(
                command,
                cwd=cwd,
                environment=environment,
                timeout=timeout,
                capture_output=capture_output,
                result_file=result_file,
                config=config,
                context=context,
            )
        except ValueError as error:
            return ModuleResult(success=False, error=str(error))
        except Exception as error:  # noqa: BLE001 - source exposes node errors.
            return ModuleResult(success=False, error=f"执行失败: {error}")
        finally:
            for path in temporary_paths:
                path.unlink(missing_ok=True)

    @staticmethod
    def _interpreter(config: dict[str, Any], python_path: Any) -> str:
        if to_bool(config.get("useBuiltinPython", True), True):
            return sys.executable
        if python_path:
            resolved = Path(str(python_path)).expanduser()
            if not resolved.exists():
                raise ValueError(f"指定的Python路径不存在: {resolved}")
            return str(resolved)
        return sys.executable

    @staticmethod
    def _script(
        mode: str,
        content: Any,
        path: Any,
        temporary_paths: list[Path],
    ) -> tuple[str, Path | None]:
        if mode != "content":
            if not path:
                raise ValueError("脚本文件路径不能为空")
            resolved = Path(str(path)).expanduser()
            if not resolved.is_file():
                raise ValueError(f"脚本文件不存在: {resolved}")
            return str(resolved), None
        if not content:
            raise ValueError("脚本内容不能为空")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as output:
            result_path = Path(output.name)
        temporary_paths.append(result_path)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as script:
            script.write(_wrapped_script(str(content), result_path))
            script_path = Path(script.name)
        temporary_paths.append(script_path)
        return str(script_path), result_path

    async def _run(
        self,
        command: list[str],
        *,
        cwd: str | None,
        environment: dict[str, str],
        timeout: int,
        capture_output: bool,
        result_file: Path | None,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> ModuleResult:
        pipe = asyncio.subprocess.PIPE if capture_output else None
        process = await asyncio.create_subprocess_exec(
            *command, stdout=pipe, stderr=pipe, cwd=cwd, env=environment
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        pumps = (
            [
                asyncio.create_task(
                    _pump(process.stdout, stdout_lines, "info", context)
                ),
                asyncio.create_task(
                    _pump(process.stderr, stderr_lines, "error", context)
                ),
            ]
            if capture_output
            else []
        )
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
            await asyncio.gather(*pumps, return_exceptions=True)
        except TimeoutError:
            process.kill()
            await process.wait()
            for task in pumps:
                task.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)
            return ModuleResult(success=False, error=f"脚本执行超时（{timeout}秒）")
        except BaseException:
            if process.returncode is None:
                process.kill()
                await process.wait()
            for task in pumps:
                task.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)
            raise

        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)
        script_result, updated_variables = _read_result(result_file)
        if updated_variables:
            for name, value in updated_variables.items():
                context.set_variable(name, value)
        _set_output_variables(
            config, context, stdout, stderr, process.returncode, script_result
        )
        data = {
            "stdout": stdout,
            "stderr": stderr,
            "returnCode": process.returncode,
        }
        if process.returncode != 0:
            return ModuleResult(
                success=False,
                error=(
                    f"脚本执行失败（返回码: {process.returncode}）"
                    f"\n标准错误输出:\n{stderr}"
                ),
                data=data,
            )
        data["result"] = script_result
        message = f"脚本执行成功（返回码: {process.returncode}）"
        if script_result is not None:
            message += f"，已返回结果到变量 {config.get('resultVariable', '')}"
        return ModuleResult(success=True, message=message, data=data)


async def _pump(
    stream: asyncio.StreamReader | None,
    chunks: list[str],
    level: str,
    context: ExecutionContext,
) -> None:
    if stream is None:
        return
    while line := await stream.readline():
        text = line.decode("utf-8", errors="replace").rstrip("\r\n")
        if text:
            chunks.append(text)
            try:
                await context.send_progress(f"[Python脚本] {text}", level)
            except Exception:  # noqa: BLE001, S110 - progress is best effort.
                pass


def _read_result(path: Path | None) -> tuple[Any, dict[str, Any] | None]:
    if path is None or not path.exists():
        return None, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    variables = value.get("variables") if isinstance(value, dict) else None
    return (
        value.get("result") if isinstance(value, dict) else None,
        variables if isinstance(variables, dict) else None,
    )


def _set_output_variables(
    config: dict[str, Any],
    context: ExecutionContext,
    stdout: str,
    stderr: str,
    return_code: int | None,
    result: Any,
) -> None:
    for key, value in (
        ("stdoutVariable", stdout),
        ("stderrVariable", stderr),
        ("returnCodeVariable", return_code),
    ):
        name = config.get(key, "")
        if isinstance(name, str) and name:
            context.set_variable(name, value)
    result_name = config.get("resultVariable", "")
    if isinstance(result_name, str) and result_name and result is not None:
        context.set_variable(result_name, result)


def _wrapped_script(content: str, output_path: Path) -> str:
    indented = "\n".join(f"    {line}" for line in content.split("\n"))
    return f'''import json
import os
import sys

class VarsProxy:
    def __init__(self, variables):
        object.__setattr__(self, "_variables", variables)
    def __getattr__(self, name):
        return self._variables.get(name)
    def __setattr__(self, name, value):
        self._variables[name] = value
    def __dir__(self):
        return list(self._variables.keys())
    def get(self, name, default=None):
        return self._variables.get(name, default)
    def keys(self):
        return self._variables.keys()
    def values(self):
        return self._variables.values()
    def items(self):
        return self._variables.items()

try:
    _all_vars = json.loads(os.environ.get("WEBRPA_VARS", "{{}}"))
except Exception:
    _all_vars = {{}}
vars = VarsProxy(_all_vars)

def _save_result(result):
    with open({str(output_path)!r}, "w", encoding="utf-8") as output:
        json.dump({{"result": result, "variables": vars._variables}}, output,
                  ensure_ascii=False, indent=2, default=str)

def _user_script():
{indented}

try:
    _result = _user_script()
    _save_result(_result)
except Exception as error:
    print(f"脚本执行错误: {{error}}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
