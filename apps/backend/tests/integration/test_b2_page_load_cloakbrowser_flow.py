from __future__ import annotations

import os
from pathlib import Path

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import launch_workflow_session


@pytest.mark.asyncio
async def test_real_cloakbrowser_runs_page_load_family(
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
    document = {
        "nodes": [
            {
                "id": "open",
                "type": "moduleNode",
                "data": {
                    "moduleType": "open_page",
                    "config": {
                        "url": Path(__file__).parents[1]
                        .joinpath("fixtures", "workflow-page.html")
                        .resolve()
                        .as_uri(),
                        "openMode": "current_tab",
                    },
                },
            },
            {
                "id": "wait",
                "type": "moduleNode",
                "data": {
                    "moduleType": "wait_page_load",
                    "config": {"waitUntil": "load", "timeout": 5},
                },
            },
            {
                "id": "status",
                "type": "moduleNode",
                "data": {
                    "moduleType": "page_load_complete",
                    "config": {
                        "checkState": "domcontentloaded",
                        "saveToVariable": "page_ready",
                    },
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "open", "target": "wait"},
            {"id": "e2", "source": "wait", "target": "status"},
        ],
        "variables": [],
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

    async with launch_workflow_session(command) as browser:
        context = ExecutionContext(browser=browser)
        result = await WorkflowRuntime(
            build_production_executor_registry()
        ).execute(document, context)

    assert result.success is True
    assert result.executed_node_ids == ("open", "wait", "status")
    assert context.variables["page_ready"] is True
