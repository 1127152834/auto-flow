from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_exports_preceding_log_records_as_registered_artifact(
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    workspace = tmp_path / "workspace"
    document = {
        "nodes": [
            {
                "id": "print",
                "type": "moduleNode",
                "data": {
                    "moduleType": "print_log",
                    "config": {"logMessage": "完成 AutoFlow", "logLevel": "warning"},
                },
            },
            {
                "id": "export",
                "type": "moduleNode",
                "data": {
                    "moduleType": "export_log",
                    "config": {
                        "outputPath": "logs/run.json",
                        "logFormat": "json",
                        "resultVariable": "export_result",
                    },
                },
            },
        ],
        "edges": [{"id": "print-export", "source": "print", "target": "export"}],
        "variables": [],
    }
    try:
        await manager.start(
            "log-run",
            "profile-1",
            None,
            {
                "runId": "log-run",
                "workflowId": "log-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(workspace),
                "document": document,
            },
        )
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        output = workspace / "runs" / "log-run" / "outputs" / "logs" / "run.json"
        exported = json.loads(output.read_text())
        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]

        assert manager.busy() is False
        assert len(completed) == 2
        assert completed[0]["message"] == "完成 AutoFlow"
        assert completed[0]["logLevel"] == "warning"
        assert exported[0]["nodeId"] == "print"
        assert exported[0]["level"] == "warning"
        assert exported[0]["message"] == "完成 AutoFlow"
        assert any(event.get("type") == "artifact:registered" for event in events)
        assert any(event.get("type") == "execution:completed" for event in events)
    finally:
        await manager.shutdown()
