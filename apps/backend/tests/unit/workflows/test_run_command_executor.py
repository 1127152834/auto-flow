from __future__ import annotations

import sys

import pytest
from autoflow.application.workflows.executors import run_command
from autoflow.application.workflows.executors.run_command import RunCommandExecutor
from autoflow.domain.workflows.execution import ExecutionContext


@pytest.mark.asyncio
async def test_run_command_returns_output_and_sets_variable() -> None:
    context = ExecutionContext()
    result = await RunCommandExecutor().execute(
        {"command": "printf hello", "shell": "cmd", "variableName": "output"},
        context,
    )

    assert result.success is True
    assert result.message == "命令执行成功: hello"
    assert result.data == {"output": "hello", "return_code": 0}
    assert context.variables["output"] == "hello"


@pytest.mark.asyncio
async def test_run_command_failure_timeout_and_empty() -> None:
    executor = RunCommandExecutor()
    failed = await executor.execute(
        {"command": "printf boom >&2; exit 7", "shell": "cmd"},
        ExecutionContext(),
    )
    timed_out = await executor.execute(
        {"command": "sleep 1", "shell": "cmd", "timeout": 0},
        ExecutionContext(),
    )

    assert failed.success is False
    assert failed.error == "命令执行失败 (返回码: 7): boom"
    assert timed_out.error == "命令执行超时 (0秒)"
    assert (await executor.execute({}, ExecutionContext())).error == "命令不能为空"


@pytest.mark.asyncio
async def test_run_command_marks_sensitive_derived_output() -> None:
    context = ExecutionContext(
        variables={"secret": "private"}, sensitive_variables={"secret"}
    )
    result = await RunCommandExecutor().execute(
        {
            "command": "printf {secret}",
            "shell": "cmd",
            "variableName": "copied",
        },
        context,
    )

    assert result.success is True
    assert context.variables["copied"] == "private"
    assert "copied" in context.sensitive_variables


def test_powershell_requires_pwsh_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_command.sys, "platform", "linux")
    monkeypatch.setattr(run_command.shutil, "which", lambda _name: None)

    with pytest.raises(ValueError, match="未安装 PowerShell"):
        run_command._command_argv("Write-Output ok", "powershell")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell adaptation")
def test_cmd_maps_to_posix_shell() -> None:
    assert run_command._command_argv("printf ok", "cmd") == [
        "/bin/sh",
        "-c",
        "printf ok",
    ]
