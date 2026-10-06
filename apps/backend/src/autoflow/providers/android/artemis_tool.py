"""ARTEMIS tool provider: install into an isolated venv, run the bridge subprocess, parse its JSON lines."""

import asyncio
import contextlib
import json
import os
import shutil
import sys
import urllib.request
import zipfile
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import psutil  # type: ignore[import-untyped]

from autoflow.domain.android.ai_test import redact
from autoflow.domain.android.ports import AndroidError

ARTEMIS_COMMIT = "351ca8422f7b5b54e80a9c1ce03a222e02415b6b"
_ARCHIVE_URL = f"https://github.com/google/artemis/archive/{ARTEMIS_COMMIT}.zip"
_STDOUT_LIMIT = 16 * 1024 * 1024
_HELPER_TIMEOUT = 600

Downloader = Callable[[str, Path], None]
Runner = Callable[[list[str], Callable[[str], None]], Awaitable[int]]


@dataclass(frozen=True)
class ToolStatus:
    state: Literal["missing_prerequisite", "not_installed", "installing", "ready", "failed"]
    version: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class ModelEnv:
    provider_kind: str
    base_url: str | None
    model_key: str
    secret: str = field(repr=False, default="")


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out)


async def _run_command(command: list[str], on_output: Callable[[str], None]) -> int:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert process.stdout is not None
    async for raw in process.stdout:
        on_output(raw.decode("utf-8", "replace").rstrip())
    return await process.wait()


def _kill_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
        victims = [*parent.children(recursive=True), parent]
    except psutil.NoSuchProcess:
        return
    for victim in victims:
        with contextlib.suppress(psutil.NoSuchProcess):
            victim.kill()


async def _stop(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        _kill_tree(process.pid)
    await process.wait()


def _extract(zip_path: Path, target: Path) -> None:
    """Extract the archive, stripping its single top-level directory."""
    if target.exists():
        shutil.rmtree(target)
    scratch = target.parent / "_extract"
    shutil.rmtree(scratch, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(scratch)
    (top,) = list(scratch.iterdir())
    top.replace(target)
    shutil.rmtree(scratch, ignore_errors=True)


def _spawn_options() -> dict[str, Any]:
    return {} if sys.platform == "win32" else {"start_new_session": True}


class ArtemisTool:
    def __init__(
        self,
        root: Path,
        bridge: Path | None = None,
        uv: str | None = None,
        python: str | None = None,
        downloader: Downloader = _download,
        runner: Runner = _run_command,
    ) -> None:
        self.root = root
        self.bridge = bridge or Path(__file__).with_name("artemis_bridge.py")
        self._uv = uv
        self._python = python
        self._downloader = downloader
        self._runner = runner
        self._installing = False
        self._failed: str | None = None
        self.tool_dir = root / "tools" / "artemis"

    def _resolve_uv(self) -> str | None:
        return self._uv or os.environ.get("AUTOFLOW_UV_PATH") or shutil.which("uv")

    @property
    def _venv(self) -> Path:
        return self.tool_dir / ".venv"

    @property
    def _venv_python(self) -> Path:
        return self._venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    def status(self) -> ToolStatus:
        if self._installing:
            return ToolStatus("installing")
        if self._resolve_uv() is None:
            return ToolStatus("missing_prerequisite", None, "需要先安装 uv（Python 工具管理器）")
        try:
            commit = json.loads((self.tool_dir / "installed.json").read_text("utf-8")).get("commit")
        except (OSError, ValueError, AttributeError):
            commit = None
        if commit == ARTEMIS_COMMIT and self._venv.exists():
            return ToolStatus("ready", ARTEMIS_COMMIT)
        if self._failed:
            return ToolStatus("failed", None, self._failed)
        return ToolStatus("not_installed")

    async def install(self, on_output: Callable[[str], None]) -> ToolStatus:
        uv = self._resolve_uv()
        if uv is None:
            raise AndroidError("AI_TOOL_INSTALL_FAILED", "需要先安装 uv（Python 工具管理器）", 502)
        if self._installing:
            raise AndroidError("AI_TOOL_INSTALL_FAILED", "安装正在进行中", 409)
        self._installing = True
        collected: list[str] = []

        def emit(line: str) -> None:
            collected.append(line)
            on_output(line)

        try:
            src = self.tool_dir / "src"
            self.tool_dir.mkdir(parents=True, exist_ok=True)
            archive = self.tool_dir / "artemis.zip"
            emit(f"下载 {_ARCHIVE_URL}")
            await asyncio.to_thread(self._downloader, _ARCHIVE_URL, archive)
            await asyncio.to_thread(_extract, archive, src)
            archive.unlink(missing_ok=True)
            python = str(self._venv_python)
            steps = [
                [uv, "venv", "--python", "3.12", str(self._venv)],
                [
                    uv, "pip", "install", "--python", python,
                    "-e", str(src / "packages" / "artemis-client"), "-e", str(src),
                ],
            ]
            for command in steps:
                code = await self._runner(command, emit)
                if code != 0:
                    raise RuntimeError(f"命令退出码 {code}: {' '.join(command[:3])}")
            (self.tool_dir / "installed.json").write_text(
                json.dumps({"commit": ARTEMIS_COMMIT}), encoding="utf-8"
            )
            self._failed = None
        except Exception as exc:
            emit(f"{type(exc).__name__}: {exc}")
            message = redact("\n".join(collected), [])
            self._failed = message
            raise AndroidError("AI_TOOL_INSTALL_FAILED", message, 502) from exc
        finally:
            self._installing = False
        return self.status()

    def _env(self, model: ModelEnv | None = None) -> dict[str, str]:
        env = dict(os.environ)
        env["ARTEMIS_HELPER_AUTO_INSTALL"] = "false"
        env["PYTHONIOENCODING"] = "utf-8"
        adb = shutil.which("adb")
        if adb:
            env["PATH"] = str(Path(adb).parent) + os.pathsep + env.get("PATH", "")
        if model is not None:
            env["AUTOFLOW_MODEL_PROVIDER_KIND"] = model.provider_kind
            env["AUTOFLOW_MODEL_BASE_URL"] = model.base_url or ""
            env["AUTOFLOW_MODEL_KEY"] = model.model_key
            env["AUTOFLOW_MODEL_SECRET"] = model.secret
        return env

    def _python_exe(self) -> str:
        return self._python or str(self._venv_python)

    async def run(
        self,
        *,
        serial: str,
        instruction: str,
        mode: str,
        max_steps: int,
        timeout_seconds: int,
        artifacts: Path,
        model: ModelEnv,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        cancel: asyncio.Event,
    ) -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            self._python_exe(), str(self.bridge), "run", "--serial", serial, "--mode", mode,
            "--max-steps", str(max_steps), "--artifacts", str(artifacts),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(model),
            limit=_STDOUT_LIMIT,
            **_spawn_options(),
        )
        stdin, stdout, stderr = process.stdin, process.stdout, process.stderr
        assert stdin and stdout and stderr
        stderr_tail: deque[str] = deque(maxlen=50)
        result: dict[str, Any] | None = None

        async def pump_stderr() -> None:
            async for raw in stderr:
                stderr_tail.append(raw.decode("utf-8", "replace").rstrip())

        async def pump_stdout() -> None:
            nonlocal result
            async for raw in stdout:
                try:
                    event = json.loads(raw.decode("utf-8", "replace"))
                except ValueError:
                    continue
                kind = event.get("type") if isinstance(event, dict) else None
                if not isinstance(kind, str):
                    continue
                if kind == "result":
                    result = event
                elif kind != "helper":
                    await on_event(event)
            await process.wait()

        err_task = asyncio.create_task(pump_stderr())
        out_task = asyncio.create_task(pump_stdout())
        cancel_task = asyncio.create_task(cancel.wait())
        try:
            try:
                stdin.write(instruction.encode("utf-8"))
                await stdin.drain()
                stdin.close()
            except OSError:
                pass  # child died early; its exit code and stderr explain why
            done, _ = await asyncio.wait(
                {out_task, cancel_task}, timeout=timeout_seconds, return_when=asyncio.FIRST_COMPLETED
            )
            if out_task not in done:
                await _stop(process)
                if cancel_task in done:
                    raise AndroidError("AI_TEST_CANCELLED", "测试已停止", 409)
                raise AndroidError("AI_TEST_TIMEOUT", f"测试超过 {timeout_seconds} 秒未完成，已结束", 504)
            out_task.result()
            await asyncio.wait_for(err_task, 5)
        except BaseException:
            await _stop(process)
            raise
        finally:
            for task in (out_task, err_task, cancel_task):
                task.cancel()
            await asyncio.gather(out_task, err_task, cancel_task, return_exceptions=True)
        if process.returncode != 0 or result is None:
            text = "\n".join(stderr_tail) or f"桥接进程退出码 {process.returncode}，未返回结果"
            raise AndroidError("AI_TEST_PROCESS_FAILED", redact(text, [model.secret]), 502)
        return result

    async def helper(self, serial: str, *, install: bool) -> bool:
        command = "helper-install" if install else "helper-status"
        process = await asyncio.create_subprocess_exec(
            self._python_exe(), str(self.bridge), command, "--serial", serial,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(),
            **_spawn_options(),
        )
        try:
            out, err = await asyncio.wait_for(process.communicate(), _HELPER_TIMEOUT)
        except BaseException:
            await _stop(process)
            raise
        if process.returncode == 0:
            for raw in out.decode("utf-8", "replace").splitlines():
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("type") == "helper":
                    return bool(event.get("installed"))
        text = err.decode("utf-8", "replace") or "辅助组件进程未返回结果"
        raise AndroidError("AI_TEST_HELPER_FAILED", redact(text, []), 502)
