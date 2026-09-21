from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


def _payload(run_id: str, script: str) -> dict[str, object]:
    return {
        "runId": run_id,
        "workflowId": "python-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": "",
        "document": {
            "nodes": [
                {
                    "id": "script",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "python_script",
                        "config": {
                            "scriptContent": script,
                            "resultVariable": "answer",
                            "stdoutVariable": "stdout",
                            "returnCodeVariable": "code",
                        },
                    },
                },
                {
                    "id": "after",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "print_log",
                        "config": {"logMessage": "{answer}:{code}"},
                    },
                },
            ],
            "edges": [{"id": "script-after", "source": "script", "target": "after"}],
            "variables": [{"name": "count", "value": 2}],
        },
    }


@pytest.mark.asyncio
async def test_real_worker_executes_python_and_syncs_variables(tmp_path: Path) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path / "workers",
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        payload = _payload(
            "python-run",
            'print("worker")\nvars.count += 4\nreturn vars.count',
        )
        payload["artifactRoot"] = str(tmp_path / "artifacts")
        await manager.start("python-run", "profile-1", None, payload)
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert [event["nodeId"] for event in completed] == ["script", "after"]
        assert completed[0]["data"] == {
            "stdout": "worker",
            "stderr": "",
            "returnCode": 0,
            "result": 6,
        }
        assert completed[1]["message"] == "6:0"
        assert any(event.get("type") == "execution:completed" for event in events)
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_stopping_worker_kills_running_python_child(tmp_path: Path) -> None:
    ready = tmp_path / "ready"
    leaked = tmp_path / "leaked"
    manager = WorkflowWorkerManager(
        tmp_path / "workers",
        termination_timeout=0.2,
        on_event=lambda _event: None,
    )
    try:
        script = (
            "import pathlib, time\n"
            f"pathlib.Path({str(ready)!r}).write_text('ready')\n"
            "time.sleep(0.5)\n"
            f"pathlib.Path({str(leaked)!r}).write_text('leaked')"
        )
        payload = _payload("python-stop", script)
        payload["artifactRoot"] = str(tmp_path / "artifacts")
        await manager.start("python-stop", "profile-1", None, payload)
        for _ in range(300):
            if ready.exists():
                break
            await asyncio.sleep(0.01)
        assert ready.exists()

        await manager.stop("python-stop")
        await asyncio.sleep(0.6)

        assert not manager.busy()
        assert not leaked.exists()
    finally:
        await manager.shutdown()
