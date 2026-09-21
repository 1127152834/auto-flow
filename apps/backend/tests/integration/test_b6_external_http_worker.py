from __future__ import annotations

import asyncio
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread

import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_runs_external_http_family_against_local_service(
    tmp_path: Path,
) -> None:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append({"path": self.path})
            status = "ready" if len(requests) >= 2 else "pending"
            encoded = json.dumps({"data": {"status": status}}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self) -> None:
            raw = self.rfile.read(int(self.headers.get("content-length", "0")))
            body = json.loads(raw) if raw else None
            requests.append(
                {
                    "path": self.path,
                    "body": body,
                    "authorization": self.headers.get("authorization"),
                    "cookie": self.headers.get("cookie"),
                }
            )
            encoded = json.dumps(
                {"path": self.path, "received": body}, ensure_ascii=False
            ).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("set-cookie", "fixture=ok")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    origin = f"http://127.0.0.1:{server.server_port}"
    nodes = [
        {
            "id": "trigger",
            "type": "moduleNode",
            "data": {
                "moduleType": "api_trigger",
                "config": {
                    "apiUrl": f"{origin}/poll",
                    "conditionPath": "$.data.status",
                    "conditionValue": "ready",
                    "checkInterval": 0,
                    "timeout": 2,
                },
            },
        },
        {
            "id": "api",
            "type": "moduleNode",
            "data": {
                "moduleType": "api_request",
                "config": {
                    "requestUrl": f"{origin}/api",
                    "requestMethod": "POST",
                    "requestHeaders": '{"Authorization":"Bearer worker-secret"}',
                    "requestCookies": "session=cookie-secret",
                    "requestBody": '{"name":"AutoFlow"}',
                    "variableName": "api_result",
                },
            },
        },
        {
            "id": "webhook",
            "type": "moduleNode",
            "data": {
                "moduleType": "webhook_request",
                "config": {
                    "url": f"{origin}/hook",
                    "method": "POST",
                    "bodyType": "json",
                    "body": '{"source":"worker"}',
                    "saveResponse": True,
                    "responseVariable": "hook_result",
                    "saveStatus": True,
                    "statusVariable": "hook_status",
                },
            },
        },
        {
            "id": "notify",
            "type": "moduleNode",
            "data": {
                "moduleType": "notify_webhook",
                "config": {
                    "webhookUrl": f"{origin}/notify",
                    "message": '{"message":"完成"}',
                },
            },
        },
    ]
    try:
        await manager.start(
            "http-family-run",
            "profile-1",
            None,
            {
                "runId": "http-family-run",
                "workflowId": "http-family-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "artifacts"),
                "document": {
                    "nodes": nodes,
                    "edges": [
                        {"id": "trigger-api", "source": "trigger", "target": "api"},
                        {"id": "api-hook", "source": "api", "target": "webhook"},
                        {"id": "hook-notify", "source": "webhook", "target": "notify"},
                    ],
                    "variables": [],
                },
            },
        )
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert manager.busy() is False
        assert [item["path"] for item in requests] == [
            "/poll",
            "/poll",
            "/api",
            "/hook",
            "/notify",
        ]
        assert requests[2]["authorization"] == "Bearer worker-secret"
        assert requests[2]["cookie"] == "session=cookie-secret"
        assert len(completed) == 4
        assert all(event.get("success") is True for event in completed)
        assert any(event.get("type") == "execution:completed" for event in events)
        serialized = json.dumps(events, ensure_ascii=False)
        assert "worker-secret" not in serialized
        assert "cookie-secret" not in serialized
    finally:
        await manager.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_stopping_worker_interrupts_in_flight_http_request(tmp_path: Path) -> None:
    started = Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            started.set()
            time.sleep(5)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.2,
        on_event=lambda event: events.append(event),
    )
    try:
        await manager.start(
            "http-stop-run",
            "profile-1",
            None,
            {
                "runId": "http-stop-run",
                "workflowId": "http-stop-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "artifacts"),
                "document": {
                    "nodes": [
                        {
                            "id": "api",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "api_request",
                                "config": {
                                    "requestUrl": f"http://127.0.0.1:{server.server_port}/slow",
                                    "requestMethod": "POST",
                                    "requestTimeout": 30,
                                },
                            },
                        }
                    ],
                    "edges": [],
                    "variables": [],
                },
            },
        )
        assert await asyncio.to_thread(started.wait, 1)
        before = time.monotonic()
        await manager.stop("http-stop-run")

        assert time.monotonic() - before < 1
        assert manager.busy() is False
        assert not any(
            event.get("type") == "execution:node_complete" for event in events
        )
    finally:
        await manager.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(timeout=0.1)
