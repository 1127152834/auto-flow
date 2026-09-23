from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_runs_all_eight_ai_task_nodes_with_managed_model(
    tmp_path: Path,
) -> None:
    requests: list[dict[str, object]] = []
    responses = {
        "信息抽取引擎": '{"姓名":"张三"}',
        "文本分类器": '{"category":"退款"}',
        "摘要助手": "简短摘要",
        "专业翻译": "Hello",
        "情感分析引擎": '{"sentiment":"正面"}',
        "数据规整引擎": '"2026-09-21"',
        "语义去重引擎": "[0,2]",
        "智能路由决策器": '{"route":"退款"}',
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            system = body["messages"][0]["content"]
            content = next(value for marker, value in responses.items() if marker in system)
            requests.append({"authorization": self.headers.get("authorization"), "body": body})
            encoded = json.dumps(
                {"choices": [{"message": {"content": content}}]}, ensure_ascii=False
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
    configs = [
        ("extract", "ai_extract", {"inputText": "姓名张三", "fields": "姓名"}),
        ("classify", "ai_classify", {"inputText": "我要退款", "categories": "退款,咨询"}),
        ("summarize", "ai_summarize", {"inputText": "很长的原文", "maxWords": 20}),
        ("translate", "ai_translate", {"inputText": "你好", "targetLang": "英文"}),
        ("sentiment", "ai_sentiment", {"inputText": "非常满意"}),
        ("normalize", "ai_normalize", {"inputText": "2026年9月21日", "normalizeType": "date"}),
        ("dedup", "ai_dedup_semantic", {"inputList": '["苹果","Apple","香蕉"]'}),
        ("route", "ai_route", {"inputText": "我要退款", "routes": "退款:退钱;咨询:问信息"}),
    ]
    nodes = [
        {
            "id": node_id,
            "type": "moduleNode",
            "data": {
                "moduleType": module_type,
                "config": {**config, "modelId": "model-1", "variableName": node_id},
            },
        }
        for node_id, module_type, config in configs
    ]
    edges = [
        {"id": f"edge-{index}", "source": configs[index][0], "target": configs[index + 1][0]}
        for index in range(len(configs) - 1)
    ]
    try:
        payload = {
            "runId": "ai-task-run",
            "workflowId": "ai-task-flow",
            "profileId": "profile-1",
            "requiresBrowser": False,
            "artifactRoot": str(tmp_path / "artifacts"),
            "modelBindings": [
                {
                    "modelId": "model-1",
                    "modelKey": "fixture-model",
                    "presetId": "custom-openai-compatible",
                    "providerKind": "openai-compatible",
                    "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                    "secret": "worker-only-secret",
                }
            ],
            "document": {"nodes": nodes, "edges": edges, "variables": []},
        }
        await manager.start("ai-task-run", "profile-1", None, payload)
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        completed = [event for event in events if event.get("type") == "execution:node_complete"]
        assert manager.busy() is False
        assert len(completed) == 8
        assert all(event.get("success") is True for event in completed)
        assert len(requests) == 8
        assert all(request["authorization"] == "Bearer worker-only-secret" for request in requests)
        assert all(request["body"]["model"] == "fixture-model" for request in requests)
        assert "worker-only-secret" not in json.dumps(events, ensure_ascii=False)
        assert any(event.get("type") == "execution:completed" for event in events)
    finally:
        await manager.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
