from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_stops_long_scheduled_task_without_running_successor(
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        await manager.start(
            "scheduled-run",
            "profile-1",
            None,
            {
                "runId": "scheduled-run",
                "workflowId": "scheduled-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "workspace"),
                "document": {
                    "nodes": [
                        {
                            "id": "schedule",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "scheduled_task",
                                "config": {
                                    "scheduleType": "delay",
                                    "delaySeconds": 60,
                                },
                            },
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
                    "edges": [{"id": "next", "source": "schedule", "target": "after"}],
                    "variables": [],
                },
            },
        )
        for _ in range(300):
            if any(
                event.get("type") == "execution:node_start"
                and event.get("nodeId") == "schedule"
                for event in events
            ):
                break
            await asyncio.sleep(0.01)
        await manager.stop("scheduled-run")

        assert manager.busy() is False
        assert not any(event.get("nodeId") == "after" for event in events)
    finally:
        await manager.shutdown()
