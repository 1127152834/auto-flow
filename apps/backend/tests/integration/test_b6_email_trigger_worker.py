from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from threading import Event, Thread

import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_stops_during_blocked_imap_connection(tmp_path: Path) -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    release = Event()

    def accept() -> None:
        connection, _address = listener.accept()
        with connection:
            release.wait(5)

    Thread(target=accept, daemon=True).start()
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.2,
        on_event=lambda event: events.append(event),
    )
    payload = {
        "runId": "email-stop-run",
        "workflowId": "email-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": "email",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "email_trigger",
                        "config": {
                            "emailServer": "127.0.0.1",
                            "emailPort": listener.getsockname()[1],
                            "emailAccount": "user@example.com",
                            "emailPassword": "secret",
                            "timeout": 0,
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
            "edges": [{"id": "next", "source": "email", "target": "after"}],
            "variables": [],
        },
    }
    try:
        await manager.start("email-stop-run", "profile-1", None, payload)
        for _ in range(200):
            if any(event.get("nodeId") == "email" for event in events):
                break
            await asyncio.sleep(0.01)
        await manager.stop("email-stop-run")
        assert manager.busy() is False
        assert not any(event.get("nodeId") == "after" for event in events)
        assert "secret" not in repr(events)
    finally:
        release.set()
        listener.close()
        await manager.shutdown()
