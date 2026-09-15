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
async def test_real_cloakbrowser_runs_web_basic_family(
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

    module_types = [
        "open_page",
        "wait_element",
        "hover_element",
        "inject_javascript",
        "switch_iframe",
        "wait_element",
        "switch_to_main",
    ]
    configs = [
        {
            "url": Path(__file__)
            .parents[1]
            .joinpath("fixtures", "workflow-page.html")
            .resolve()
            .as_uri(),
            "openMode": "current_tab",
        },
        {"selector": "#workflow-input", "waitCondition": "visible"},
        {"selector": "#workflow-submit", "hoverDuration": 0},
        {
            "javascriptCode": (
                "return document.querySelector('#click-count').textContent"
            ),
            "injectMode": "current",
            "saveResult": "click_count",
        },
        {"locateBy": "selector", "iframeSelector": "#workflow-frame"},
        {"selector": "#frame-value", "waitCondition": "visible"},
        {},
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
    assert result.executed_node_ids == tuple(
        f"node-{index}" for index in range(len(module_types))
    )
    assert context.variables["click_count"] == "0"
