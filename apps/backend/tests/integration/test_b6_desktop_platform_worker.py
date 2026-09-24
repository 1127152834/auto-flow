from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_waits_for_platform_action_and_redacts_clipboard(
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
            "platform-run",
            "profile-1",
            None,
            {
                "runId": "platform-run",
                "workflowId": "platform-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "artifacts"),
                "document": {
                    "nodes": [
                        {
                            "id": "clipboard",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "get_clipboard",
                                "config": {"variableName": "copied"},
                            },
                        },
                        {
                            "id": "after",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "print_log",
                                "config": {"logMessage": "{copied}"},
                            },
                        },
                    ],
                    "edges": [
                        {
                            "id": "clipboard-after",
                            "source": "clipboard",
                            "target": "after",
                        }
                    ],
                    "variables": [],
                },
            },
        )
        for _ in range(300):
            requests = [
                event
                for event in events
                if event.get("type") == "execution:desktop_action"
            ]
            if requests:
                break
            await asyncio.sleep(0.01)
        request = requests[0]
        assert request["action"] == "clipboard_read_text"
        assert request["payload"] == {}
        assert not any(
            event.get("type") == "execution:node_complete" for event in events
        )

        await manager.send_command(
            "platform-run",
            {
                "type": "desktop_action_result",
                "commandId": "platform-result",
                "requestId": request["requestId"],
                "claimId": "studio",
                "success": True,
                "value": "private-clipboard-value",
            },
        )
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        assert any(
            event.get("type") == "execution:command_applied"
            and event.get("commandId") == "platform-result"
            for event in events
        )
        assert any(event.get("type") == "execution:completed" for event in events)
        assert "private-clipboard-value" not in json.dumps(events)
    finally:
        await manager.shutdown()
