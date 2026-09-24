from __future__ import annotations

import asyncio
import base64
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_generates_image_and_video_through_managed_model(
    tmp_path: Path,
) -> None:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            requests.append(
                {
                    "method": "POST",
                    "path": self.path,
                    "authorization": self.headers.get("authorization"),
                    "body": body,
                }
            )
            response = (
                {"data": [{"b64_json": base64.b64encode(b"PNG").decode()}]}
                if self.path.endswith("/images/generations")
                else {"id": "video-job"}
            )
            self._json(response)

        def do_GET(self) -> None:
            requests.append(
                {
                    "method": "GET",
                    "path": self.path,
                    "authorization": self.headers.get("authorization"),
                }
            )
            if self.path.endswith("/generations/video-job"):
                self._json(
                    {
                        "status": "completed",
                        "url": f"http://127.0.0.1:{server.server_port}/media.mp4",
                    }
                )
                return
            content = b"MP4"
            self.send_response(200)
            self.send_header("content-type", "video/mp4")
            self.send_header("content-length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _json(self, value: object) -> None:
            content = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    events: list[dict[str, object]] = []
    artifact_root = tmp_path / "artifacts"
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        payload = {
            "runId": "ai-media-run",
            "workflowId": "ai-media-flow",
            "profileId": "profile-1",
            "requiresBrowser": False,
            "artifactRoot": str(artifact_root),
            "modelBindings": [
                {
                    "modelId": "model-1",
                    "modelKey": "fixture-media-model",
                    "presetId": "custom-openai-compatible",
                    "providerKind": "openai-compatible",
                    "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                    "secret": "worker-only-secret",
                }
            ],
            "document": {
                "nodes": [
                    {
                        "id": "image",
                        "type": "moduleNode",
                        "data": {
                            "moduleType": "ai_generate_image",
                            "config": {
                                "modelId": "model-1",
                                "prompt": "一只猫",
                                "savePath": "generated/image.png",
                                "variableName": "image_paths",
                            },
                        },
                    },
                    {
                        "id": "video",
                        "type": "moduleNode",
                        "data": {
                            "moduleType": "ai_generate_video",
                            "config": {
                                "modelId": "model-1",
                                "prompt": "海上日出",
                                "savePath": "generated/video.mp4",
                                "variableName": "video_path",
                            },
                        },
                    },
                ],
                "edges": [{"id": "edge", "source": "image", "target": "video"}],
                "variables": [],
            },
        }
        await manager.start("ai-media-run", "profile-1", None, payload)
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert manager.busy() is False
        assert [event.get("success") for event in completed] == [True, True]
        assert len(requests) == 4
        assert all(
            request.get("authorization") == "Bearer worker-only-secret"
            for request in requests[:3]
        )
        assert requests[0]["body"]["model"] == "fixture-media-model"
        assert requests[1]["body"]["model"] == "fixture-media-model"
        assert (
            artifact_root / "runs/ai-media-run/outputs/generated/image.png"
        ).read_bytes() == b"PNG"
        assert (
            artifact_root / "runs/ai-media-run/outputs/generated/video.mp4"
        ).read_bytes() == b"MP4"
        assert "worker-only-secret" not in json.dumps(events, ensure_ascii=False)
        assert any(event.get("type") == "execution:completed" for event in events)
    finally:
        await manager.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
