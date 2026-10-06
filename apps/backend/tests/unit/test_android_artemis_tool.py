import asyncio
import contextlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import psutil
import pytest

from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android import artemis_tool
from autoflow.providers.android.artemis_tool import (
    ARTEMIS_COMMIT,
    ArtemisTool,
    ModelEnv,
)

BRIDGE = Path(__file__).parents[1] / "fixtures" / "fake_artemis_bridge.py"
SECRET = "sk-super-secret-123"


@pytest.fixture
def tool(tmp_path):
    return ArtemisTool(tmp_path / "root", bridge=BRIDGE, uv="uv", python=sys.executable)


def kwargs(tmp_path, events=None, cancel=None, **extra):
    async def on_event(e):
        if events is not None:
            events.append(e)

    return {
        "serial": "emulator-5554", "instruction": "打开设置", "mode": "flash", "max_steps": 5,
        "timeout_seconds": 30, "artifacts": tmp_path, "model": ModelEnv("openai", None, "m", SECRET),
        "on_event": on_event, "cancel": cancel or asyncio.Event(),
    } | extra


@pytest.mark.asyncio
async def test_run_streams_steps_and_returns_result(tool, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "ok")
    events: list = []
    result = await tool.run(**kwargs(tmp_path, events))
    assert [e["type"] for e in events] == ["step", "step"] and result["succeeded"] is True


@pytest.mark.asyncio
async def test_garbage_lines_ignored(tool, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "garbage")
    events: list = []
    result = await tool.run(**kwargs(tmp_path, events))
    assert result["succeeded"] is True and len(events) == 2


@pytest.mark.asyncio
async def test_crash_reports_redacted_stderr(tool, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "crash")
    with pytest.raises(AndroidError) as err:
        await tool.run(**kwargs(tmp_path))
    assert err.value.code == "AI_TEST_PROCESS_FAILED"
    assert SECRET not in err.value.message and "fatal" in err.value.message


@pytest.mark.asyncio
async def test_timeout_kills_process_tree(tool, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "child")
    monkeypatch.setenv("FAKE_PID_FILE", str(tmp_path / "pid"))
    with pytest.raises(AndroidError) as err:
        await tool.run(**kwargs(tmp_path, timeout_seconds=2))
    assert err.value.code == "AI_TEST_TIMEOUT"
    assert not psutil.pid_exists(int((tmp_path / "pid").read_text()))


@pytest.mark.asyncio
async def test_cancel_kills_and_raises(tool, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "child")
    monkeypatch.setenv("FAKE_PID_FILE", str(tmp_path / "pid"))
    cancel = asyncio.Event()
    task = asyncio.create_task(tool.run(**kwargs(tmp_path, cancel=cancel)))
    for _ in range(100):
        if (tmp_path / "pid").exists():
            break
        await asyncio.sleep(0.1)
    cancel.set()
    with pytest.raises(AndroidError) as err:
        await task
    assert err.value.code == "AI_TEST_CANCELLED"
    assert not psutil.pid_exists(int((tmp_path / "pid").read_text()))


@pytest.mark.asyncio
async def test_env_contains_flags_and_secret_only_in_env(tool, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "ok")
    monkeypatch.setenv("FAKE_ENV_OUT", str(tmp_path / "env.json"))
    await tool.run(**kwargs(tmp_path))
    seen = json.loads((tmp_path / "env.json").read_text("utf-8"))
    assert seen["env"]["ARTEMIS_HELPER_AUTO_INSTALL"] == "false"
    assert seen["env"]["AUTOFLOW_MODEL_SECRET"] == SECRET
    assert SECRET not in " ".join(seen["argv"]) and seen["stdin"] == "打开设置"


@pytest.mark.asyncio
async def test_helper_status_and_install(tool, monkeypatch):
    monkeypatch.setenv("FAKE_HELPER", "0")
    assert await tool.helper("s", install=False) is False
    assert await tool.helper("s", install=True) is True
    monkeypatch.setenv("FAKE_MODE", "crash")
    with pytest.raises(AndroidError) as err:
        await tool.helper("s", install=True)
    assert err.value.code == "AI_TEST_HELPER_FAILED" and "helper boom" in err.value.message


def test_status_missing_uv(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.delenv("AUTOFLOW_UV_PATH", raising=False)
    assert ArtemisTool(tmp_path).status().state == "missing_prerequisite"


def _fake_zip(url: str, dest: Path) -> None:
    with zipfile.ZipFile(dest, "w") as z:
        z.writestr(f"artemis-{ARTEMIS_COMMIT}/pyproject.toml", "")
        z.writestr(f"artemis-{ARTEMIS_COMMIT}/packages/artemis-client/pyproject.toml", "")


@pytest.mark.asyncio
async def test_install_success_writes_marker_and_streams(tmp_path):
    commands: list = []
    seen_state: list = []

    async def runner(cmd, on_output):
        commands.append(cmd)
        seen_state.append(tool.status().state)
        on_output("ok line")
        return 0

    tool = ArtemisTool(tmp_path, bridge=BRIDGE, uv="uv", downloader=_fake_zip, runner=runner)
    assert tool.status().state == "not_installed"
    lines: list = []
    (tool.tool_dir / ".venv").mkdir(parents=True)
    status = await tool.install(lines.append)
    assert status.state == "ready" and "ok line" in lines
    assert seen_state == ["installing", "installing"]
    assert commands[0][:4] == ["uv", "venv", "--python", "3.12"]
    assert commands[1][:3] == ["uv", "pip", "install"] and commands[1].count("-e") == 2
    assert (tool.tool_dir / "src" / "pyproject.toml").exists()
    assert json.loads((tool.tool_dir / "installed.json").read_text()) == {"commit": ARTEMIS_COMMIT}


@pytest.mark.asyncio
async def test_install_failure_raises_and_writes_no_marker(tmp_path):
    async def runner(cmd, on_output):
        on_output("pip exploded")
        return 1

    tool = ArtemisTool(tmp_path, bridge=BRIDGE, uv="uv", downloader=_fake_zip, runner=runner)
    with pytest.raises(AndroidError) as err:
        await tool.install(lambda _: None)
    assert err.value.code == "AI_TOOL_INSTALL_FAILED" and "pip exploded" in err.value.message
    assert not (tool.tool_dir / "installed.json").exists()
    assert tool.status().state == "failed"


@pytest.mark.asyncio
async def test_install_download_failure(tmp_path):
    def bad(url, dest):
        raise OSError("no network")

    tool = ArtemisTool(tmp_path, bridge=BRIDGE, uv="uv", downloader=bad)
    with pytest.raises(AndroidError) as err:
        await tool.install(lambda _: None)
    assert "no network" in err.value.message


@pytest.mark.asyncio
async def test_detached_grandchild_holding_pipes_does_not_block_result(tool, tmp_path, monkeypatch):
    import time

    monkeypatch.setenv("FAKE_MODE", "grandchild")
    monkeypatch.setenv("FAKE_PID_FILE", str(tmp_path / "pid"))
    started = time.monotonic()
    try:
        result = await tool.run(**kwargs(tmp_path))
    finally:
        if (tmp_path / "pid").exists():
            with contextlib.suppress(psutil.NoSuchProcess):
                psutil.Process(int((tmp_path / "pid").read_text())).kill()
    assert result["succeeded"] is True and time.monotonic() - started < 15


@pytest.mark.asyncio
async def test_unread_stdin_times_out(tool, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "noread")
    with pytest.raises(AndroidError) as err:
        await tool.run(**kwargs(tmp_path, instruction="测" * 4000, timeout_seconds=1))
    assert err.value.code == "AI_TEST_TIMEOUT"


@pytest.mark.asyncio
async def test_helper_timeout_is_typed(tool, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "hang")
    monkeypatch.setattr(artemis_tool, "_HELPER_TIMEOUT", 1)
    with pytest.raises(AndroidError) as err:
        await tool.helper("s", install=False)
    assert err.value.code == "AI_TEST_HELPER_FAILED"


@pytest.mark.asyncio
async def test_reinstall_failure_clears_stale_marker(tmp_path):
    async def ok(cmd, on_output):
        return 0

    async def bad(cmd, on_output):
        return 1

    tool = ArtemisTool(tmp_path, bridge=BRIDGE, uv="uv", downloader=_fake_zip, runner=ok)
    (tool.tool_dir / ".venv").mkdir(parents=True)
    assert (await tool.install(lambda _: None)).state == "ready"
    tool._runner = bad
    with pytest.raises(AndroidError):
        await tool.install(lambda _: None)
    assert tool.status().state == "failed" and not (tool.tool_dir / "artemis.zip").exists()
