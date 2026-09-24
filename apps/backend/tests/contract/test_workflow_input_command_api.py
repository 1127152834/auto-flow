from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.events.workflows import (
    StudioEventJournal,
    workflow_events_router,
)
from autoflow.adapters.http.errors import install_error_handlers


class FakeCommands:
    def __init__(self) -> None:
        self.submitted: list[tuple[str, str, dict[str, Any]]] = []

    async def submit_event_command(
        self, command_id: str, event: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        self.submitted.append((command_id, event, dict(data)))
        return {"commandId": command_id, "success": True}, 200

    def event_command(self, command_id: str) -> tuple[dict[str, Any], int]:
        return {"commandId": command_id, "success": True, "httpStatus": 200}, 200

    def input_prompt_state(self, request_id: str) -> dict[str, str]:
        return {
            "requestId": request_id,
            "workflowId": "flow",
            "nodeId": "prompt",
            "status": "pending",
        }

    def js_script_state(self, request_id: str) -> dict[str, str]:
        return {
            "requestId": request_id,
            "workflowId": "flow",
            "nodeId": "script",
            "status": "claimed",
            "claimId": "studio",
        }

    def tts_request_state(self, request_id: str) -> dict[str, str]:
        return {
            "requestId": request_id,
            "workflowId": "flow",
            "nodeId": "voice",
            "status": "pending",
        }

    def desktop_action_state(self, request_id: str) -> dict[str, str]:
        return {
            "requestId": request_id,
            "workflowId": "flow",
            "nodeId": "clipboard",
            "status": "pending",
        }


def test_input_command_http_contract_uses_camel_case_and_queryable_receipts() -> None:
    commands = FakeCommands()
    app = FastAPI()
    app.include_router(workflow_events_router(StudioEventJournal(), commands))
    client = TestClient(app)

    response = client.post(
        "/api/events/commands",
        json={
            "commandId": "command-1",
            "event": "input_prompt_result",
            "data": {"requestId": "request-1", "value": "原文"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {"commandId": "command-1", "success": True}
    assert commands.submitted == [
        (
            "command-1",
            "input_prompt_result",
            {"requestId": "request-1", "value": "原文"},
        )
    ]
    assert client.get("/api/events/commands/command-1").json() == {
        "commandId": "command-1",
        "success": True,
        "httpStatus": 200,
    }
    assert client.get("/api/events/input-prompts/request-1").json() == {
        "requestId": "request-1",
        "workflowId": "flow",
        "nodeId": "prompt",
        "status": "pending",
    }
    assert client.get("/api/events/js-requests/script-1").json() == {
        "requestId": "script-1",
        "workflowId": "flow",
        "nodeId": "script",
        "status": "claimed",
        "claimId": "studio",
    }
    assert client.get("/api/events/tts-requests/speech-1").json() == {
        "requestId": "speech-1",
        "workflowId": "flow",
        "nodeId": "voice",
        "status": "pending",
        "claimId": None,
    }
    assert client.get("/api/events/desktop-actions/platform-1").json() == {
        "requestId": "platform-1",
        "workflowId": "flow",
        "nodeId": "clipboard",
        "status": "pending",
        "claimId": None,
    }


def test_input_command_http_contract_rejects_malformed_envelopes() -> None:
    app = FastAPI()
    app.include_router(workflow_events_router(StudioEventJournal(), FakeCommands()))
    client = TestClient(app)

    assert client.post(
        "/api/events/commands",
        json={"commandId": "", "event": "input_prompt_result", "data": {}},
    ).status_code == 422
    assert client.post(
        "/api/events/commands",
        json={"commandId": "command", "event": "input_prompt_result", "data": []},
    ).status_code == 422


@pytest.mark.parametrize("event", ["input_prompt_result", "js_script_claim", "js_script_result", "tts_claim", "tts_result", "desktop_action_claim", "desktop_action_result"])
def test_scoped_interaction_rejects_foreign_requests_before_dispatch(event: str) -> None:
    class ScopedCommands(FakeCommands):
        def request_run(self, request_id: str) -> str | None:
            return "owned-run" if request_id == "owned-request" else None

        def command_run(self, command_id: str) -> str | None:
            return "owned-run"

    class Runs:
        def belongs_to_project(self, run_id: str, project_id: str) -> bool:
            return run_id == "owned-run" and project_id == "own"

    commands = ScopedCommands()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflow_events_router(StudioEventJournal(), commands, Runs()))
    client = TestClient(app)
    command = {"commandId": "command", "event": event, "data": {"requestId": "owned-request", "value": "answer"}}
    assert client.post("/api/events/commands?projectId=other", json=command).status_code == 404
    assert not commands.submitted
    assert client.post("/api/events/commands?projectId=own", json=command).status_code == 200
    assert len(commands.submitted) == 1
    assert client.get("/api/events/commands/command?projectId=other").status_code == 404
    assert client.get("/api/events/commands/command?projectId=own").status_code == 200
    for collection in ("input-prompts", "js-requests", "tts-requests", "desktop-actions"):
        assert client.get(f"/api/events/{collection}/owned-request?projectId=other").status_code == 404
        assert client.get(f"/api/events/{collection}/owned-request?projectId=own").status_code == 200
        assert client.get(f"/api/events/{collection}/missing?projectId=own").status_code == 404
