from __future__ import annotations

import os
from pathlib import Path

import pytest

from autoflow.application.workflows.executors.basic import (
    ClickElementExecutor,
    GetElementInfoExecutor,
    InputTextExecutor,
    OpenPageExecutor,
    ScreenshotExecutor,
)
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import launch_workflow_session


class FileArtifacts:
    def __init__(self, root: Path) -> None:
        self.root = root

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        assert mime_type == "image/png"
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)


def _png_size(content: bytes) -> tuple[int, int]:
    assert content[:8] == b"\x89PNG\r\n\x1a\n"
    assert content[12:16] == b"IHDR"
    return (
        int.from_bytes(content[16:20], "big"),
        int.from_bytes(content[20:24], "big"),
    )


@pytest.mark.asyncio
async def test_real_cloakbrowser_runs_five_node_workflow(
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

    registry = ExecutorRegistry()
    for executor in (
        OpenPageExecutor,
        InputTextExecutor,
        ClickElementExecutor,
        GetElementInfoExecutor,
        ScreenshotExecutor,
    ):
        registry.register(executor)
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
                        "waitUntil": "load",
                    },
                },
            },
            {
                "id": "input",
                "type": "moduleNode",
                "data": {
                    "moduleType": "input_text",
                    "config": {
                        "selector": "#workflow-input",
                        "text": "真实 CloakBrowser 五节点",
                        "clearBefore": True,
                    },
                },
            },
            {
                "id": "click",
                "type": "moduleNode",
                "data": {
                    "moduleType": "click_element",
                    "config": {"selector": ".workflow-action", "clickType": "single"},
                },
            },
            {
                "id": "extract",
                "type": "moduleNode",
                "data": {
                    "moduleType": "get_element_info",
                    "config": {
                        "selector": "xpath=//*[@id='workflow-output']",
                        "attribute": "text",
                        "variableName": "result",
                    },
                },
            },
            {
                "id": "shot",
                "type": "moduleNode",
                "data": {
                    "moduleType": "screenshot",
                    "config": {
                        "screenshotType": "viewport",
                        "fileNamePattern": "b1-real",
                        "variableName": "shot",
                    },
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "open", "target": "input"},
            {"id": "e2", "source": "input", "target": "click"},
            {"id": "e3", "source": "click", "target": "extract"},
            {"id": "e4", "source": "extract", "target": "shot"},
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

    async with launch_workflow_session(command) as browser:
        context = ExecutionContext(
            browser=browser,
            artifacts=FileArtifacts(tmp_path / "artifacts"),
        )
        result = await WorkflowRuntime(registry).execute(document, context)
        page = browser.current_page()
        click_count = await page.locator("#click-count").text_content()

    assert result.success is True
    assert result.executed_node_ids == ("open", "input", "click", "extract", "shot")
    assert context.variables["result"] == "真实 CloakBrowser 五节点"
    assert click_count == "1"
    screenshot = Path(context.variables["shot"])
    assert screenshot.is_file()
    assert screenshot.name == "b1-real.png"
    width, height = _png_size(screenshot.read_bytes())
    assert width > 100 and height > 100
