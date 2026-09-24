from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module_type", "config"),
    [
        ("hotkey_trigger", {"hotkey": "ctrl+shift+f12", "timeout": 0}),
        ("mouse_trigger", {"triggerType": "left_click", "timeout": 0}),
    ],
)
async def test_real_worker_cleans_global_input_listener_or_platform_failure(
    tmp_path: Path, module_type: str, config: dict[str, object]
) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.2,
        on_event=lambda event: events.append(event),
    )
    run_id = module_type.replace("_", "-")
    payload = {
        "runId": run_id,
        "workflowId": "input-trigger-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": "trigger",
                    "type": "moduleNode",
                    "data": {"moduleType": module_type, "config": config},
                },
                {
                    "id": "after",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "print_log",
                        "config": {"logMessage": "不应执行"},
                    },
                },
            ],
            "edges": [{"id": "next", "source": "trigger", "target": "after"}],
            "variables": [],
        },
    }
    try:
        await manager.start(run_id, "profile-1", None, payload)
        for _ in range(200):
            if (
                any(event.get("nodeId") == "trigger" for event in events)
                or not manager.busy()
            ):
                break
            await asyncio.sleep(0.01)
        if manager.busy():
            await manager.stop(run_id)
        assert manager.busy() is False
        assert not any(event.get("nodeId") == "after" for event in events)
    finally:
        await manager.shutdown()
