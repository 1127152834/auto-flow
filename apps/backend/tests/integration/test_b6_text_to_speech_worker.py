from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
@pytest.mark.parametrize("success", [True, False])
async def test_real_worker_waits_for_confirmed_speech_result(
    tmp_path: Path, success: bool
) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        await manager.start(
            f"speech-{'ok' if success else 'fail'}",
            "profile-1",
            None,
            {
                "runId": f"speech-{'ok' if success else 'fail'}",
                "workflowId": "speech-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "artifacts"),
                "document": {
                    "nodes": [
                        {
                            "id": "voice",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "text_to_speech",
                                "config": {
                                    "text": "通知",
                                    "lang": "zh-CN",
                                    "rate": 0.8,
                                    "pitch": 1.2,
                                    "volume": 0,
                                },
                            },
                        },
                        {
                            "id": "after",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "print_log",
                                "config": {"logMessage": "after"},
                            },
                        },
                    ],
                    "edges": [
                        {"id": "voice-after", "source": "voice", "target": "after"}
                    ],
                    "variables": [],
                },
            },
        )
        for _ in range(300):
            requests = [
                event for event in events if event.get("type") == "execution:tts_request"
            ]
            if requests:
                break
            await asyncio.sleep(0.01)
        request = requests[0]
        assert request["text"] == "通知"
        assert request["lang"] == "zh-CN"
        assert request["rate"] == 0.8
        assert request["pitch"] == 1.2
        assert request["volume"] == 0.0
        command: dict[str, object] = {
            "type": "tts_result",
            "commandId": "speech-result",
            "requestId": request["requestId"],
            "claimId": "studio",
            "success": success,
        }
        if not success:
            command["error"] = "语音不可用"
        await manager.send_command(str(request["runId"]), command)
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert [event["nodeId"] for event in completed] == (
            ["voice", "after"] if success else ["voice"]
        )
        assert completed[0]["success"] is success
        assert any(
            event.get("type") == "execution:command_applied"
            and event.get("commandId") == "speech-result"
            for event in events
        )
        assert any(
            event.get("type")
            == ("execution:completed" if success else "execution:failed")
            for event in events
        )
    finally:
        await manager.shutdown()
