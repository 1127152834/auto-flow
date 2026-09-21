from __future__ import annotations

import sys
from pathlib import Path

import pytest
from autoflow.application.workflows.executors.python_script import (
    PythonScriptExecutor,
    _local_no_proxy_env,
)
from autoflow.domain.workflows.execution import ExecutionContext


@pytest.mark.asyncio
async def test_python_content_syncs_variables_result_and_progress() -> None:
    progress: list[tuple[str, str]] = []

    async def report(message: str, level: str) -> None:
        progress.append((message, level))

    context = ExecutionContext(variables={"count": 2}, progress=report)
    result = await PythonScriptExecutor().execute(
        {
            "scriptContent": (
                'print("开始")\n'
                "vars.count += 3\n"
                'return {"answer": vars.count}'
            ),
            "resultVariable": "answer",
            "stdoutVariable": "stdout",
            "stderrVariable": "stderr",
            "returnCodeVariable": "code",
        },
        context,
    )

    assert result.success is True
    assert result.data == {
        "stdout": "开始",
        "stderr": "",
        "returnCode": 0,
        "result": {"answer": 5},
    }
    assert context.variables == {
        "count": 5,
        "answer": {"answer": 5},
        "stdout": "开始",
        "stderr": "",
        "code": 0,
    }
    assert progress == [("[Python脚本] 开始", "info")]


@pytest.mark.asyncio
async def test_python_file_mode_and_failures(tmp_path: Path) -> None:
    script = tmp_path / "script.py"
    script.write_text(
        "import os, sys\nprint(sys.argv[1])\nprint(os.getcwd())\n",
        encoding="utf-8",
    )
    result = await PythonScriptExecutor().execute(
        {
            "scriptMode": "file",
            "scriptPath": str(script),
            "scriptArgs": "first second",
            "workingDir": str(tmp_path),
            "useBuiltinPython": False,
            "pythonPath": sys.executable,
        },
        ExecutionContext(),
    )
    assert result.success is True
    assert result.data["stdout"].splitlines() == ["first", str(tmp_path)]

    executor = PythonScriptExecutor()
    assert (await executor.execute({}, ExecutionContext())).error == "脚本内容不能为空"
    assert (
        await executor.execute(
            {
                "scriptMode": "file",
                "scriptPath": str(tmp_path / "missing.py"),
            },
            ExecutionContext(),
        )
    ).error == f"脚本文件不存在: {tmp_path / 'missing.py'}"
    assert (
        await executor.execute(
            {"scriptContent": "import time; time.sleep(1)", "timeout": 0},
            ExecutionContext(),
        )
    ).error == "脚本执行超时（0秒）"
    assert (
        await executor.execute(
            {
                "scriptContent": "return 1",
                "useBuiltinPython": False,
                "pythonPath": str(tmp_path / "missing-python"),
            },
            ExecutionContext(),
        )
    ).error == f"指定的Python路径不存在: {tmp_path / 'missing-python'}"


@pytest.mark.asyncio
async def test_python_sensitive_inputs_redact_runtime_result() -> None:
    context = ExecutionContext(
        variables={"secret": "private"}, sensitive_variables={"secret"}
    )
    result = await PythonScriptExecutor().execute(
        {"scriptContent": "return vars.secret", "resultVariable": "copied"},
        context,
    )

    assert result.success is True
    assert context.node_uses_sensitive_values is True
    assert context.variables["copied"] == "private"
    assert "copied" in context.sensitive_variables


def test_python_no_proxy_preserves_existing_hosts() -> None:
    assert _local_no_proxy_env({"NO_PROXY": "internal.test,localhost"}) == {
        "NO_PROXY": "internal.test,localhost,127.0.0.1,::1,0.0.0.0",
        "no_proxy": "internal.test,localhost,127.0.0.1,::1,0.0.0.0",
    }
