from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


def _payload(run_id: str, watch_path: Path) -> dict[str, object]:
    return {
        "runId": run_id,
        "workflowId": "file-watch-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(watch_path.parent / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": "watch",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "file_watcher_trigger",
                        "config": {
                            "watchPath": str(watch_path),
                            "watchType": "created",
                            "filePattern": "*.txt",
                            "timeout": 10,
                            "saveToVariable": "event",
                        },
                    },
                },
                {
                    "id": "after",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "print_log",
                        "config": {"logMessage": "文件已创建"},
                    },
                },
            ],
            "edges": [{"id": "next", "source": "watch", "target": "after"}],
            "variables": [],
        },
    }


@pytest.mark.asyncio
async def test_real_worker_observes_file_creation_and_stops_cleanly(
    tmp_path: Path,
) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        await manager.start("file-watch-run", "profile-1", None, _payload("file-watch-run", watched))
        for _ in range(200):
            if any(
                event.get("type") == "execution:node_start"
                and event.get("nodeId") == "watch"
                for event in events
            ):
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.2)
        (watched / "created.txt").write_text("ready", encoding="utf-8")
        for _ in range(300):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert manager.busy() is False
        assert [event.get("nodeId") for event in completed] == ["watch", "after"]
        assert completed[0]["data"]["eventType"] == "created"  # type: ignore[index]
        assert completed[0]["data"]["fileName"] == "created.txt"  # type: ignore[index]

        events.clear()
        await manager.start("file-stop-run", "profile-1", None, _payload("file-stop-run", watched))
        for _ in range(200):
            if any(event.get("nodeId") == "watch" for event in events):
                break
            await asyncio.sleep(0.01)
        await manager.stop("file-stop-run")
        assert manager.busy() is False
        assert not any(event.get("nodeId") == "after" for event in events)
    finally:
        await manager.shutdown()
