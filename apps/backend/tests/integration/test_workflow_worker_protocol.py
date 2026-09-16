from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from autoflow.infrastructure.process.workflow_worker import (
    WorkflowWorkerBusy,
    WorkflowWorkerManager,
)


def _fake_worker(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "fake-workflow-worker.py"
    script.write_text(
        """
import json, subprocess, sys, time
command = json.loads(sys.stdin.readline())
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])
print(json.dumps({'type':'ready','runId':command['runId'],'profileId':command['profileId'],'childPid':child.pid}), flush=True)
print(json.dumps({'type':'event','seq':1,'name':'worker_ready'}), flush=True)
sys.stdin.read()
time.sleep(300)
""",
        encoding="utf-8",
    )
    return (sys.executable, str(script))


def _command_worker(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "command-workflow-worker.py"
    script.write_text(
        """
import json, sys
command = json.loads(sys.stdin.readline())
print(json.dumps({'type':'ready','runId':command['runId'],'profileId':command['profileId']}), flush=True)
reply = json.loads(sys.stdin.readline())
print(json.dumps({**reply, 'type':'command-observed'}), flush=True)
""",
        encoding="utf-8",
    )
    return (sys.executable, str(script))


def _crashing_worker(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "crashing-workflow-worker.py"
    script.write_text(
        """
import json, os, subprocess, sys, time
command = json.loads(sys.stdin.readline())
child = subprocess.Popen(
    [
        sys.executable,
        '-c',
        'import time; time.sleep(300)',
        os.environ['CLOAKBROWSER_CACHE_DIR'],
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(json.dumps({'type':'ready','runId':command['runId'],'profileId':command['profileId'],'childPid':child.pid}), flush=True)
time.sleep(0.05)
sys.exit(17)
""",
        encoding="utf-8",
    )
    return (sys.executable, str(script))


@pytest.mark.asyncio
async def test_worker_start_stream_and_stop_clean_the_real_process_tree(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"test binary identity")
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        command=_fake_worker(tmp_path),
        termination_timeout=0.2,
        on_event=lambda event: events.append(event),
    )
    payload = {"runId": "run-1", "profileId": "profile-1", "document": {}}

    session = await manager.start("run-1", "profile-1", executable, payload)
    await asyncio.sleep(0.05)

    assert session.run_id == "run-1"
    assert session.profile_id == "profile-1"
    assert session.pid in manager.active_processes()
    assert events == [{"type": "event", "seq": 1, "name": "worker_ready"}]
    with pytest.raises(WorkflowWorkerBusy):
        await manager.start("run-2", "profile-2", executable, payload)

    await manager.stop("run-1")

    assert manager.active_processes() == []
    assert manager.busy() is False
    with pytest.raises(ProcessLookupError):
        os.kill(session.child_pid, 0)
    assert not any((tmp_path / "workflow-worker").rglob("run-1"))


@pytest.mark.asyncio
async def test_worker_manager_delivers_one_structured_runtime_command(
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        command=_command_worker(tmp_path),
        termination_timeout=0.2,
        on_event=lambda event: events.append(event),
    )
    await manager.start(
        "run-command",
        "profile-1",
        None,
        {"runId": "run-command", "profileId": "profile-1"},
    )

    await manager.send_command(
        "run-command",
        {
            "type": "input_prompt_result",
            "commandId": "command-1",
            "requestId": "request-1",
            "value": "原文",
        },
    )
    for _ in range(100):
        if events:
            break
        await asyncio.sleep(0.01)

    assert events == [
        {
            "type": "command-observed",
            "commandId": "command-1",
            "requestId": "request-1",
            "value": "原文",
        }
    ]
    await manager.shutdown()


@pytest.mark.asyncio
async def test_real_worker_waits_for_input_then_resumes_node_execution(
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    payload = {
        "runId": "input-run",
        "workflowId": "input-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": "prompt",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "input_prompt",
                        "config": {
                            "variableName": "answer",
                            "inputMode": "integer",
                            "promptTitle": "输入",
                        },
                    },
                }
            ],
            "edges": [],
            "variables": [{"name": "answer", "value": 0}],
        },
    }
    await manager.start("input-run", "profile-1", None, payload)
    for _ in range(200):
        if any(event.get("type") == "execution:input_prompt" for event in events):
            break
        await asyncio.sleep(0.01)
    prompt = next(
        event for event in events if event.get("type") == "execution:input_prompt"
    )
    assert not any(event.get("type") == "execution:node_complete" for event in events)

    await manager.send_command(
        "input-run",
        {
            "type": "input_prompt_result",
            "commandId": "command-1",
            "requestId": prompt["requestId"],
            "value": "42",
        },
    )
    for _ in range(300):
        if not manager.busy():
            break
        await asyncio.sleep(0.01)

    assert any(
        event.get("type") == "execution:command_applied"
        and event.get("commandId") == "command-1"
        for event in events
    )
    completed = next(
        event for event in events if event.get("type") == "execution:node_complete"
    )
    assert completed["success"] is True
    assert completed["data"] == {"value": 42}
    assert any(event.get("type") == "execution:completed" for event in events)
    assert manager.busy() is False


@pytest.mark.asyncio
async def test_real_worker_runs_frozen_nested_workflow_snapshot(
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    child = {
        "id": "child-id",
        "name": "子工作流",
        "nodes": [
            {
                "id": "child-set",
                "type": "moduleNode",
                "data": {
                    "moduleType": "set_variable",
                    "config": {"variableName": "child", "variableValue": "2"},
                },
            }
        ],
        "edges": [],
        "variables": [],
    }
    payload = {
        "runId": "nested-run",
        "workflowId": "parent-id",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "workflowDependencies": {
            "child-id": child,
            "子工作流": child,
            "子工作流.json": child,
        },
        "document": {
            "nodes": [
                {
                    "id": "call",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "run_workflow_file",
                        "config": {
                            "workflowFile": "子工作流",
                            "resultVariable": "summary",
                        },
                    },
                }
            ],
            "edges": [],
            "variables": [{"name": "parent", "value": 1}],
        },
    }
    await manager.start("nested-run", "profile-1", None, payload)
    for _ in range(300):
        if not manager.busy():
            break
        await asyncio.sleep(0.01)

    completed = [
        event for event in events if event.get("type") == "execution:node_complete"
    ]
    assert [(event["nodeId"], event["success"]) for event in completed] == [
        ("child-set", True),
        ("call", True),
    ]
    assert completed[-1]["data"] == {
        "workflow": "子工作流",
        "file": "子工作流.json",
        "success": True,
        "executed_nodes": 1,
        "failed_nodes": 0,
        "error": None,
    }
    assert any(event.get("type") == "subflow:started" for event in events)
    assert any(event.get("type") == "subflow:completed" for event in events)
    assert any(event.get("type") == "execution:completed" for event in events)


@pytest.mark.asyncio
async def test_worker_start_rejects_bad_handshake_and_releases_slot(tmp_path: Path) -> None:
    script = tmp_path / "bad-worker.py"
    script.write_text("print('not-json', flush=True)\n", encoding="utf-8")
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"test binary identity")
    manager = WorkflowWorkerManager(
        tmp_path,
        command=(sys.executable, str(script)),
        start_timeout=1,
        termination_timeout=0.2,
    )

    with pytest.raises(RuntimeError, match="启动确认"):
        await manager.start(
            "run-failed",
            "profile-1",
            executable,
            {"runId": "run-failed", "profileId": "profile-1"},
        )

    assert manager.busy() is False
    assert manager.active_processes() == []


@pytest.mark.asyncio
async def test_stop_during_start_interrupts_handshake_and_cleans_slot(tmp_path: Path) -> None:
    script = tmp_path / "silent-worker.py"
    script.write_text(
        "import sys, time\nsys.stdin.readline()\ntime.sleep(300)\n",
        encoding="utf-8",
    )
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"test binary identity")
    manager = WorkflowWorkerManager(
        tmp_path,
        command=(sys.executable, str(script)),
        start_timeout=300,
        termination_timeout=0.2,
    )
    opening = asyncio.create_task(
        manager.start(
            "run-starting",
            "profile-1",
            executable,
            {"runId": "run-starting", "profileId": "profile-1"},
        )
    )
    for _ in range(100):
        if manager.active_processes():
            break
        await asyncio.sleep(0.01)

    await manager.stop("run-starting")

    with pytest.raises((RuntimeError, asyncio.CancelledError)):
        await opening
    assert manager.busy() is False
    assert manager.active_processes() == []


@pytest.mark.asyncio
async def test_shutdown_also_stops_a_worker_that_is_still_starting(tmp_path: Path) -> None:
    script = tmp_path / "silent-shutdown-worker.py"
    script.write_text(
        "import sys, time\nsys.stdin.readline()\ntime.sleep(300)\n",
        encoding="utf-8",
    )
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"test binary identity")
    manager = WorkflowWorkerManager(
        tmp_path,
        command=(sys.executable, str(script)),
        start_timeout=300,
        termination_timeout=0.2,
    )
    opening = asyncio.create_task(
        manager.start(
            "run-shutdown-start",
            "profile-1",
            executable,
            {"runId": "run-shutdown-start", "profileId": "profile-1"},
        )
    )
    for _ in range(100):
        if manager.active_processes():
            break
        await asyncio.sleep(0.01)

    await manager.shutdown()

    await asyncio.gather(opening, return_exceptions=True)
    assert manager.busy() is False
    assert manager.active_processes() == []


@pytest.mark.asyncio
async def test_shutdown_reaps_worker_spawned_before_start_receives_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_spawn = asyncio.create_subprocess_exec
    spawned = asyncio.Event()
    release_spawn = asyncio.Event()
    processes: list[asyncio.subprocess.Process] = []

    async def delayed_spawn(*args: object, **kwargs: object) -> asyncio.subprocess.Process:
        process = await real_spawn(*args, **kwargs)
        processes.append(process)
        spawned.set()
        await release_spawn.wait()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_spawn)
    manager = WorkflowWorkerManager(
        tmp_path,
        command=(sys.executable, "-c", "import time; time.sleep(300)"),
        termination_timeout=0.2,
    )
    opening = asyncio.create_task(
        manager.start(
            "run-spawn-race",
            "profile-1",
            None,
            {"runId": "run-spawn-race", "profileId": "profile-1"},
        )
    )

    try:
        await asyncio.wait_for(spawned.wait(), timeout=5)
        closing = asyncio.create_task(manager.shutdown())
        for _ in range(100):
            if opening.cancelling():
                break
            await asyncio.sleep(0.01)
        assert opening.cancelling()

        release_spawn.set()
        await asyncio.wait_for(closing, timeout=5)
        await asyncio.gather(opening, return_exceptions=True)

        assert processes[0].returncode is not None
        assert manager.busy() is False
        assert manager.active_processes() == []
    finally:
        release_spawn.set()
        for process in processes:
            if process.returncode is None:
                process.kill()
                await process.wait()


@pytest.mark.asyncio
async def test_event_consumer_failure_still_cleans_worker_tree(tmp_path: Path) -> None:
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"test binary identity")

    def fail_event(_event: dict[str, object]) -> None:
        raise RuntimeError("event persistence failed")

    manager = WorkflowWorkerManager(
        tmp_path,
        command=_fake_worker(tmp_path),
        termination_timeout=0.2,
        on_event=fail_event,
    )
    session = await manager.start(
        "run-event-failure",
        "profile-1",
        executable,
        {"runId": "run-event-failure", "profileId": "profile-1"},
    )

    for _ in range(100):
        if not manager.busy():
            break
        await asyncio.sleep(0.01)

    assert manager.busy() is False
    assert manager.active_processes() == []
    assert manager.failure("run-event-failure") == "WORKER_EVENT_CONSUMER_FAILED"
    if session.child_pid is not None:
        with pytest.raises(ProcessLookupError):
            os.kill(session.child_pid, 0)


@pytest.mark.asyncio
async def test_worker_exit_callback_runs_after_process_and_temp_cleanup(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"test binary identity")
    observed: list[tuple[str, int, bool, bool]] = []
    manager: WorkflowWorkerManager

    async def on_exit(run_id: str, return_code: int) -> None:
        observed.append(
            (
                run_id,
                return_code,
                manager.busy(),
                any((tmp_path / "workflow-worker").rglob(run_id)),
            )
        )

    manager = WorkflowWorkerManager(
        tmp_path,
        command=_fake_worker(tmp_path),
        termination_timeout=0.2,
        on_exit=on_exit,
    )
    await manager.start(
        "run-exit", "profile-1", executable, {"runId": "run-exit", "profileId": "profile-1"}
    )

    await manager.stop("run-exit")

    assert observed == [("run-exit", -15, False, False)]


@pytest.mark.asyncio
async def test_worker_crash_cleans_descendants_before_reporting_nonzero_exit(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"test binary identity")
    exited = asyncio.Event()
    observed: list[tuple[str, int, bool, bool]] = []
    manager: WorkflowWorkerManager

    async def on_exit(run_id: str, return_code: int) -> None:
        observed.append(
            (
                run_id,
                return_code,
                manager.busy(),
                any((tmp_path / "workflow-worker").rglob(run_id)),
            )
        )
        exited.set()

    manager = WorkflowWorkerManager(
        tmp_path,
        command=_crashing_worker(tmp_path),
        termination_timeout=0.2,
        on_exit=on_exit,
    )
    session = await manager.start(
        "run-crash",
        "profile-1",
        executable,
        {"runId": "run-crash", "profileId": "profile-1"},
    )

    await asyncio.wait_for(exited.wait(), timeout=5)

    assert observed == [("run-crash", 17, False, False)]
    assert manager.active_processes() == []
    assert manager.busy() is False
    if session.child_pid is not None:
        with pytest.raises(ProcessLookupError):
            os.kill(session.child_pid, 0)
