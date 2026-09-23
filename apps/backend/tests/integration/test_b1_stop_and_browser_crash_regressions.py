from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.basic import (
    InputTextExecutor,
    ScreenshotExecutor,
)
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


class _Cancellation:
    cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError


class _SideEffectExecutor(ModuleExecutor):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def module_type(self) -> str:
        return "set_variable"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        self.calls += 1
        return ModuleResult(success=True)


class _Browser:
    def __init__(self, page: Any) -> None:
        self.page = page

    def current_page(self) -> Any:
        return self.page

    def active_page(self) -> Any:
        return self.page


class _BlockingInput:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.completed: list[str] = []

    async def wait_for(self, **_options: Any) -> None:
        return None

    async def evaluate(self, expression: str) -> Any:
        return "input" if "tagName" in expression else False

    async def fill(self, value: str) -> None:
        self.entered.set()
        await asyncio.Event().wait()
        self.completed.append(value)


class _InputPage:
    def __init__(self, locator: _BlockingInput) -> None:
        self._locator = locator

    def locator(self, _selector: str) -> _BlockingInput:
        return self._locator


class _ScreenshotPage:
    async def screenshot(self, *, full_page: bool = False) -> bytes:
        assert full_page is False
        return b"png"


class _BlockingArtifacts:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.writes: list[str] = []

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        assert content == b"png"
        assert mime_type == "image/png"
        self.entered.set()
        await asyncio.Event().wait()
        self.writes.append(name)
        return name


def _runtime(
    executor: type[ModuleExecutor],
) -> tuple[WorkflowRuntime, _SideEffectExecutor]:
    registry = ExecutorRegistry()
    registry.register(executor)
    registry.register(_SideEffectExecutor)
    probe = registry.get("set_variable")
    assert isinstance(probe, _SideEffectExecutor)
    return WorkflowRuntime(registry), probe


def _document(module_type: str, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "active",
                "type": "moduleNode",
                "data": {"moduleType": module_type, "config": config},
            },
            {
                "id": "after",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {}},
            },
        ],
        "edges": [{"id": "edge", "source": "active", "target": "after"}],
    }


@pytest.mark.asyncio
async def test_stop_during_input_prevents_text_completion_and_later_nodes() -> None:
    locator = _BlockingInput()
    cancellation = _Cancellation()
    runtime, after = _runtime(InputTextExecutor)
    context = ExecutionContext(
        browser=cast(Any, _Browser(_InputPage(locator))), cancellation=cancellation
    )
    execution = asyncio.create_task(
        runtime.execute(
            _document(
                "input_text",
                {
                    "selector": "#input",
                    "text": "must-not-complete",
                    "clearBefore": False,
                },
            ),
            context,
        )
    )
    await asyncio.wait_for(locator.entered.wait(), timeout=1)

    cancellation.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(execution, timeout=1)
    assert locator.completed == []
    assert after.calls == 0


@pytest.mark.asyncio
async def test_stop_during_screenshot_write_creates_no_artifact_or_later_side_effect() -> (
    None
):
    artifacts = _BlockingArtifacts()
    cancellation = _Cancellation()
    runtime, after = _runtime(ScreenshotExecutor)
    context = ExecutionContext(
        browser=cast(Any, _Browser(_ScreenshotPage())),
        artifacts=cast(Any, artifacts),
        cancellation=cancellation,
    )
    execution = asyncio.create_task(
        runtime.execute(
            _document(
                "screenshot",
                {"screenshotType": "viewport", "fileNamePattern": "cancelled"},
            ),
            context,
        )
    )
    await asyncio.wait_for(artifacts.entered.wait(), timeout=1)

    cancellation.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(execution, timeout=1)
    assert artifacts.writes == []
    assert after.calls == 0


def _browser_crash_worker(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "browser-crash-worker.py"
    script.write_text(
        """
import json, os, subprocess, sys, time
from pathlib import Path

command = json.loads(sys.stdin.readline())
if command['runId'] == 'run-browser-crash':
    child = subprocess.Popen(
        [
            sys.executable,
            '-c',
            "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('exited'); raise SystemExit(23)",
            os.environ['BROWSER_EXIT_MARKER'],
        ]
    )
    print(json.dumps({'type':'ready','runId':command['runId'],'profileId':command['profileId'],'childPid':child.pid}), flush=True)
    child.wait()
    time.sleep(300)
else:
    print(json.dumps({'type':'ready','runId':command['runId'],'profileId':command['profileId']}), flush=True)
    sys.stdin.read()
""",
        encoding="utf-8",
    )
    return (sys.executable, str(script))


async def _wait_until(predicate: Any, *, timeout: float = 5.0) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return bool(predicate())


@pytest.mark.asyncio
async def test_browser_child_crash_releases_worker_slot_for_next_run(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "browser-exited"
    exits: list[tuple[str, bool]] = []
    manager: WorkflowWorkerManager

    async def on_exit(run_id: str, _return_code: int) -> None:
        exits.append((run_id, manager.busy()))

    manager = WorkflowWorkerManager(
        tmp_path,
        command=_browser_crash_worker(tmp_path),
        worker_env={"BROWSER_EXIT_MARKER": str(marker)},
        termination_timeout=0.1,
        on_exit=on_exit,
    )
    try:
        await manager.start(
            "run-browser-crash",
            "profile-1",
            None,
            {"runId": "run-browser-crash", "profileId": "profile-1"},
        )
        assert await _wait_until(marker.exists)
        assert await _wait_until(lambda: not manager.busy())
        assert manager.active_processes() == []
        assert manager.failure("run-browser-crash") == "BROWSER_PROCESS_EXITED"
        assert exits == [("run-browser-crash", False)]

        replacement = await manager.start(
            "run-replacement",
            "profile-1",
            None,
            {"runId": "run-replacement", "profileId": "profile-1"},
        )
        assert replacement.run_id == "run-replacement"
        await manager.stop("run-replacement")
    finally:
        await manager.shutdown()
