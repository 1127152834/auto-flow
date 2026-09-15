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
