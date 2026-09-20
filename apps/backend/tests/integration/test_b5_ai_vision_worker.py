from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_runs_ai_vision_with_managed_model(tmp_path: Path) -> None:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            requests.append(
                {"authorization": self.headers.get("authorization"), "body": body}
            )
            encoded = json.dumps(
                {"choices": [{"message": {"content": "一张测试图片"}}]},
                ensure_ascii=False,
            ).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
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
    try:
        payload = {
            "runId": "ai-vision-run",
            "workflowId": "ai-vision-flow",
            "profileId": "profile-1",
            "requiresBrowser": False,
            "artifactRoot": str(tmp_path / "artifacts"),
            "modelBindings": [
                {
                    "modelId": "model-1",
                    "modelKey": "fixture-vision",
                    "presetId": "custom-openai-compatible",
                    "providerKind": "openai-compatible",
                    "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                    "secret": "worker-only-secret",
                }
            ],
            "document": {
                "nodes": [
                    {
                        "id": "vision",
                        "type": "moduleNode",
                        "data": {
                            "moduleType": "ai_vision",
                            "config": {
                                "modelId": "model-1",
                                "imageSource": "url",
                                "imageUrl": "https://image.example/sample.png",
                                "userPrompt": "识别",
                                "variableName": "vision_result",
                            },
                        },
                    }
                ],
                "edges": [],
                "variables": [],
            },
        }
        await manager.start("ai-vision-run", "profile-1", None, payload)
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        assert manager.busy() is False
        assert len(requests) == 1
        assert requests[0]["authorization"] == "Bearer worker-only-secret"
        content = requests[0]["body"]["messages"][0]["content"]
        assert content[0]["image_url"]["url"] == "https://image.example/sample.png"
        assert content[1] == {"type": "text", "text": "识别"}
        assert "worker-only-secret" not in json.dumps(events, ensure_ascii=False)
        completed = [
            event
            for event in events
            if event.get("type") == "execution:node_complete"
        ]
        assert completed[0]["success"] is True
        assert completed[0]["data"]["response"] == "一张测试图片"
        assert any(event.get("type") == "execution:completed" for event in events)
    finally:
        await manager.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
