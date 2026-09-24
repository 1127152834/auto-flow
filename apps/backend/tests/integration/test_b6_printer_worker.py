from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_loads_printer_executor_and_reports_validation(
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path / "workers",
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        await manager.start(
            "printer-run",
            "profile-1",
            None,
            {
                "runId": "printer-run",
                "workflowId": "printer-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "artifacts"),
                "document": {
                    "nodes": [
                        {
                            "id": "printer",
                            "type": "moduleNode",
                            "data": {"moduleType": "printer_call", "config": {}},
                        }
                    ],
                    "edges": [],
                    "variables": [],
                },
            },
        )
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)
        failed = [event for event in events if event.get("type") == "execution:failed"]
        assert failed[-1]["error"] == "文件路径不能为空"
    finally:
        await manager.shutdown()
