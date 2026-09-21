from __future__ import annotations

import asyncio
import shlex
import sys
from pathlib import Path

import pytest
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


def _payload(run_id: str, command: str, artifact_root: Path) -> dict[str, object]:
    return {
        "runId": run_id,
        "workflowId": "command-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(artifact_root),
        "document": {
            "nodes": [
                {
                    "id": "command",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "run_command",
                        "config": {
                            "command": command,
                            "shell": "cmd",
                            "variableName": "output",
                        },
                    },
                },
                {
                    "id": "after",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "print_log",
                        "config": {"logMessage": "{output}"},
                    },
                },
            ],
            "edges": [
                {"id": "command-after", "source": "command", "target": "after"}
            ],
            "variables": [],
        },
    }


@pytest.mark.asyncio
async def test_real_worker_executes_command_for_following_node(tmp_path: Path) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path / "workers",
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        await manager.start(
            "command-run",
            "profile-1",
            None,
            _payload("command-run", "printf worker", tmp_path / "artifacts"),
        )
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)
        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert [event["nodeId"] for event in completed] == ["command", "after"]
        assert completed[0]["data"] == {"output": "worker", "return_code": 0}
        assert completed[1]["message"] == "worker"
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_stopping_worker_kills_command_process_tree(tmp_path: Path) -> None:
    ready = tmp_path / "ready"
    leaked = tmp_path / "leaked"
    script = tmp_path / "child.py"
    script.write_text(
        "import pathlib, time\n"
        f"pathlib.Path({str(ready)!r}).write_text('ready')\n"
        "time.sleep(0.5)\n"
        f"pathlib.Path({str(leaked)!r}).write_text('leaked')\n",
        encoding="utf-8",
    )
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
    manager = WorkflowWorkerManager(
        tmp_path / "workers",
        termination_timeout=0.2,
        on_event=lambda _event: None,
    )
    try:
        await manager.start(
            "command-stop",
            "profile-1",
            None,
            _payload("command-stop", command, tmp_path / "artifacts"),
        )
        for _ in range(300):
            if ready.exists():
                break
            await asyncio.sleep(0.01)
        assert ready.exists()
        await manager.stop("command-stop")
        await asyncio.sleep(0.6)
        assert not manager.busy()
        assert not leaked.exists()
    finally:
        await manager.shutdown()
