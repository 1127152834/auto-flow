from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.integrations.gateway import WorkflowIntegrationGateway

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_api_trigger_harness.py")


def source(payload: dict[str, Any]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "reference" / "WebRPA" / "backend")
    completed = subprocess.run(
        [sys.executable, str(HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    )
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"config": {}},
        {"config": {"apiUrl": "http://127.0.0.1", "headers": "{"}},
        {
            "config": {
                "apiUrl": "http://127.0.0.1",
                "method": "POST",
                "body": "{",
            }
        },
    ],
)
async def test_api_trigger_validation_matches_frozen_source(
    payload: dict[str, Any],
) -> None:
    context = ExecutionContext(variables=payload.get("variables", {}))
    executor = build_production_executor_registry().get("api_trigger")

    assert executor is not None
    result = await executor.execute(payload.get("config", {}), context)

    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    } == source(payload)


@pytest.mark.asyncio
async def test_api_trigger_success_matches_frozen_source() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            encoded = json.dumps({"data": {"status": "ready"}}).encode()
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
    gateway = WorkflowIntegrationGateway()
    payload = {
        "config": {
            "apiUrl": f"http://127.0.0.1:{server.server_port}/status",
            "conditionPath": "$.data.status",
            "conditionValue": "ready",
            "conditionOperator": "==",
            "checkInterval": 0,
            "timeout": 1,
            "saveToVariable": "result",
        }
    }
    try:
        expected = source(payload)
        context = ExecutionContext(external_integrations=gateway)
        executor = build_production_executor_registry().get("api_trigger")

        assert executor is not None
        result = await executor.execute(payload["config"], context)

        assert {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
            "variables": context.variables,
        } == expected
    finally:
        await gateway.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
