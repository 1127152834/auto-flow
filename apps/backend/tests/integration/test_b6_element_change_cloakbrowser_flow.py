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
async def test_real_cloakbrowser_observes_added_element(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured = os.environ.get("AUTOFLOW_B1_CLOAK_EXECUTABLE")
    if not configured:
        pytest.skip("set AUTOFLOW_B1_CLOAK_EXECUTABLE for the real CloakBrowser test")
    executable = Path(configured)
    if not executable.is_file():
        pytest.fail("AUTOFLOW_B1_CLOAK_EXECUTABLE does not point to a file")
    fixture = tmp_path / "element-change.html"
    fixture.write_text(
        """<!doctype html><div id="list"><span>初始</span></div>
        <script>setTimeout(() => { const item = document.createElement('p');
        item.id = 'added'; item.textContent = '新增内容';
        document.querySelector('#list').appendChild(item); }, 800);</script>""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(tmp_path / "cloak-cache"))
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
    document = {
        "nodes": [
            {
                "id": "open",
                "type": "moduleNode",
                "data": {
                    "moduleType": "open_page",
                    "config": {"url": fixture.as_uri(), "openMode": "current_tab"},
                },
            },
            {
                "id": "observe",
                "type": "moduleNode",
                "data": {
                    "moduleType": "element_change_trigger",
                    "config": {
                        "selector": "#list",
                        "timeout": 5,
                        "saveNewElementSelector": "selector",
                        "saveChangeInfo": "change",
                    },
                },
            },
        ],
        "edges": [{"id": "next", "source": "open", "target": "observe"}],
        "variables": [],
    }

    async with launch_workflow_session(command) as browser:
        context = ExecutionContext(browser=browser)
        result = await WorkflowRuntime(build_production_executor_registry()).execute(
            document, context
        )

    assert result.success is True
    assert context.variables["selector"] == "#added"
    assert context.variables["change"]["addedCount"] == 1
