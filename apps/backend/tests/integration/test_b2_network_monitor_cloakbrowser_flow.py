from __future__ import annotations

import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import launch_workflow_session


@pytest.mark.asyncio
async def test_real_cloakbrowser_runs_network_monitor_family(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured = os.environ.get("AUTOFLOW_B1_CLOAK_EXECUTABLE")
    if not configured:
        pytest.skip("set AUTOFLOW_B1_CLOAK_EXECUTABLE for the real CloakBrowser test")
    executable = Path(configured)
    if not executable.is_file():
        pytest.fail("AUTOFLOW_B1_CLOAK_EXECUTABLE does not point to a file")
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(tmp_path / "cloak-cache"))

    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "workflow-b2-network-monitor.html"
    ).read_bytes()
    observed_paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            observed_paths.append(self.path)
            if self.path.startswith("/api/orders"):
                body = json.dumps({"ok": True}).encode()
                content_type = "application/json"
            else:
                body = fixture
                content_type = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    page_url = f"http://127.0.0.1:{server.server_port}/fixture"
    module_types = [
        "open_page",
        "network_monitor_start",
        "click_element",
        "network_monitor_wait",
        "network_monitor_stop",
    ]
    configs = [
        {"url": page_url, "openMode": "current_tab"},
        {"monitorId": "orders", "filterType": "api", "urlPattern": "/api/"},
        {"selector": "#request-orders"},
        {
            "monitorId": "orders",
            "urlPattern": "/api/orders",
            "timeout": 5,
            "captureMode": "first",
            "variableName": "first_request",
        },
        {"monitorId": "orders", "variableName": "all_requests"},
    ]
    document = {
        "nodes": [
            {
                "id": f"node-{index}",
                "type": "moduleNode",
                "data": {"moduleType": module_type, "config": configs[index]},
            }
            for index, module_type in enumerate(module_types)
        ],
        "edges": [
            {
                "id": f"edge-{index}",
                "source": f"node-{index}",
                "target": f"node-{index + 1}",
            }
            for index in range(len(module_types) - 1)
        ],
    }
    command = {
        "fingerprintSeed": 12345,
        "expertArgs": [],
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "colorScheme": "light",
        "geoip": False,
        "humanize": False,
        "humanPreset": "default",
        "extensionPaths": [],
        "licenseKey": None,
        "browserVersion": "145.0.7632.109.2",
        "releaseChannel": "stable",
        "headless": True,
    }

    try:
        async with launch_workflow_session(command) as browser:
            context = ExecutionContext(browser=browser)
            result = await WorkflowRuntime(
                build_production_executor_registry()
            ).execute(document, context)
            for _ in range(20):
                page_status = await browser.current_page().evaluate(
                    "() => document.querySelector('#request-status').textContent"
                )
                if page_status == "done":
                    break
                await asyncio.sleep(0.05)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.success is True
    assert page_status == "done"
    assert any(path.startswith("/api/orders") for path in observed_paths)
    first_request = context.variables["first_request"]
    assert first_request["method"] == "GET"
    assert first_request["resource_type"] == "fetch"
    assert "fixture-secret" not in json.dumps(first_request, ensure_ascii=False)
    assert "%5B%E5%B7%B2%E9%9A%90%E8%97%8F%5D" in first_request["url"]
    assert first_request["headers"]["authorization"] == "[已隐藏]"
    assert first_request["headers"]["x-trace"] == "[已隐藏]"
    assert len(context.variables["all_requests"]) == 1
    assert context.network_monitors == {}
