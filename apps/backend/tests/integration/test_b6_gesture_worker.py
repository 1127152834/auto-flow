from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from autoflow.infrastructure.gesture import gesture_model_path
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


async def _wait(manager: WorkflowWorkerManager) -> None:
    for _ in range(500):
        if not manager.busy():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("workflow worker did not finish")


@pytest.mark.asyncio
async def test_gesture_node_loads_workspace_definitions_in_real_worker(
    tmp_path: Path,
) -> None:
    data_file = tmp_path / "gestures" / "custom_gestures.json"
    data_file.parent.mkdir()
    data_file.write_text(json.dumps({}), encoding="utf-8")
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path / "workers",
        worker_env={
            "AUTOFLOW_GESTURE_DATA_FILE": str(data_file),
            "AUTOFLOW_GESTURE_MODEL_PATH": str(gesture_model_path()),
        },
        termination_timeout=0.5,
        on_event=events.append,
    )
    payload = {
        "runId": "gesture-run",
        "workflowId": "gesture-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": "gesture",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "gesture_trigger",
                        "config": {"gestureName": "未录制手势", "timeout": 1},
                    },
                }
            ],
            "edges": [],
            "variables": [],
        },
    }
    try:
        await manager.start("gesture-run", "profile-1", None, payload)
        await _wait(manager)
    finally:
        await manager.shutdown()

    terminal = next(event for event in events if event["type"] == "execution:failed")
    assert terminal["error"] == "自定义手势不存在: 未录制手势，请先录制该手势"
