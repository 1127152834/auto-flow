"""Independent file/data checks for audited node failures; no external success doubles."""
from __future__ import annotations

import hashlib
import json
import shlex
import sys
from pathlib import Path

import pytest

from autoflow.application.workflows.executors.python_script import PythonScriptExecutor
from autoflow.application.workflows.executors.string_convert import CsvParseExecutor
from autoflow.application.workflows.executors.utility_tools import SHAEncryptExecutor
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.infrastructure.process.workflow_subprocess import split_script_arguments


def test_python_arguments_reject_embedded_nul_before_platform_parser():
    with pytest.raises(ValueError, match="NUL"):
        split_script_arguments("one\x00 two")


@pytest.mark.asyncio
@pytest.mark.parametrize("header, expected", [(True, []), (False, [["path", "bytes"]])])
async def test_header_only_csv_has_no_business_record(header, expected):
    context = ExecutionContext()
    result = await CsvParseExecutor().execute(
        {"csvContent": "path,bytes\n", "hasHeader": header, "resultVariable": "rows"}, context
    )
    assert result.success
    assert result.data == expected
    assert context.variables["rows"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["sha1", "sha256", "SHA512", "sha3_256"])
async def test_sha_matches_independent_repository_file_digest(algorithm):
    text = Path(__file__).read_text(encoding="utf-8")
    result = await SHAEncryptExecutor().execute({"inputText": text, "shaType": algorithm}, ExecutionContext())
    assert result.success
    assert result.data == hashlib.new(algorithm.lower(), text.encode()).hexdigest()


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["sha999", "md5", "new", "shake_128"])
async def test_invalid_sha_does_not_write_success_result(algorithm):
    context = ExecutionContext(variables={"digest": "previous"})
    result = await SHAEncryptExecutor().execute(
        {"inputText": "repository digest", "shaType": algorithm, "resultVariable": "digest"}, context
    )
    assert not result.success
    assert "不支持" in result.error
    assert context.variables["digest"] == "previous"


@pytest.mark.asyncio
async def test_python_file_arguments_preserve_real_spaced_file_and_literal_shell_text(tmp_path):
    source = tmp_path / "中文 目录" / "actual input.json"
    source.parent.mkdir()
    source.write_text(Path(__file__).parents[4].joinpath("package.json").read_text(encoding="utf-8"))
    script = tmp_path / "reader script.py"
    script.write_text('import json,sys\nfrom pathlib import Path\nprint(json.dumps([json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["name"], *sys.argv[2:]], ensure_ascii=False))\n')
    argv = [str(source), "two words", "", "$(do-not-execute)", "a'b", 'a"b']
    if sys.platform == "win32":
        import subprocess
        arguments = subprocess.list2cmdline(argv)
    else:
        arguments = shlex.join(argv)
    context = ExecutionContext()
    result = await PythonScriptExecutor().execute(
        {"scriptMode": "file", "scriptPath": str(script), "scriptArgs": arguments, "stdoutVariable": "out"}, context
    )
    assert result.success, result.error
    assert json.loads(context.variables["out"]) == [json.loads(source.read_text(encoding="utf-8"))["name"], *argv[1:]]


@pytest.mark.asyncio
async def test_python_plain_arguments_remain_separate(tmp_path):
    script = tmp_path / "args.py"
    script.write_text('import json,sys\nprint(json.dumps(sys.argv[1:]))\n')
    context = ExecutionContext()
    result = await PythonScriptExecutor().execute(
        {"scriptMode": "file", "scriptPath": str(script), "scriptArgs": "one two three", "stdoutVariable": "out"}, context
    )
    assert result.success
    assert json.loads(context.variables["out"]) == ["one", "two", "three"]


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", ["one\x00 two", '"unterminated'])
async def test_invalid_arguments_do_not_execute_or_replace_output(tmp_path, arguments):
    if sys.platform == "win32" and "\x00" not in arguments:
        # Native Windows command-line rules accept unmatched final quotes.
        assert split_script_arguments(arguments) == ["unterminated"]
        return
    marker = tmp_path / "executed"
    script = tmp_path / "must-not-run.py"
    script.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    context = ExecutionContext(variables={"out": "previous"})
    result = await PythonScriptExecutor().execute(
        {"scriptMode": "file", "scriptPath": str(script), "scriptArgs": arguments, "stdoutVariable": "out"}, context
    )
    assert not result.success
    assert result.error
    assert not marker.exists()
    assert context.variables["out"] == "previous"
