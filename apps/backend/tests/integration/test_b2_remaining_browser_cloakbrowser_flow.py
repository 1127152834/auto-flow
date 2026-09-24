from __future__ import annotations

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
async def test_real_cloakbrowser_runs_remaining_browser_family(
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
        / "workflow-b2-remaining-browser.html"
    ).read_bytes()
    observed_paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            observed_paths.append(self.path)
            if self.path.startswith("/api/remaining"):
                body = b'{"ok":true}'
                content_type = "application/json"
            elif self.path == "/data":
                body = fixture
                content_type = "text/html; charset=utf-8"
            else:
                body = b"<!doctype html><title>AutoFlow B2 home</title><p>home</p>"
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
    origin = f"http://127.0.0.1:{server.server_port}"
    module_types = [
        "open_page",
        "open_page",
        "switch_tab",
        "switch_tab",
        "extract_table_data",
        "network_capture",
    ]
    configs = [
        {"url": f"{origin}/home", "openMode": "current_tab"},
        {"url": f"{origin}/data", "openMode": "new_tab"},
        {
            "switchMode": "first",
            "saveTitleVariable": "first_title",
        },
        {
            "switchMode": "title",
            "tabTitle": "AutoFlow B2 数据页",
            "matchMode": "exact",
            "saveIndexVariable": "data_index",
            "saveTitleVariable": "data_title",
            "saveUrlVariable": "data_url",
        },
        {"tableSelector": "#orders-table", "variableName": "table_rows"},
        {
            "captureMode": "browser",
            "filterType": "all",
            "searchKeyword": "/api/remaining",
            "captureDuration": 0.5,
            "variableName": "captured_urls",
        },
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
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.success is True
    assert context.variables["first_title"] == "AutoFlow B2 home"
    assert context.variables["data_title"] == "AutoFlow B2 数据页"
    assert context.variables["data_index"] == 1
    assert context.variables["table_rows"] == [
        ["订单", "金额"],
        ["A-001", "88"],
        ["A-002", "99"],
    ]
    captured_urls = context.variables["captured_urls"]
    assert captured_urls
    assert all("/api/remaining" in url for url in captured_urls)
    assert "fixture-secret" not in json.dumps(captured_urls, ensure_ascii=False)
    assert any(path.startswith("/api/remaining") for path in observed_paths)
