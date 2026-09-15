from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ArtifactWriter, ExecutionContext
from autoflow.providers.browser.workflow_session import launch_workflow_session


class FileArtifacts:
    def __init__(self, root: Path) -> None:
        self.root = root

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        del mime_type
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)


@pytest.mark.asyncio
async def test_real_cloakbrowser_runs_advanced_browser_family(
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

    upload = tmp_path / "upload.txt"
    upload.write_text("AutoFlow 上传", encoding="utf-8")
    fixture_url = (
        Path(__file__)
        .parents[1]
        .joinpath("fixtures", "workflow-b2-web-actions.html")
        .resolve()
        .as_uri()
    )
    module_types = [
        "open_page",
        "select_dropdown",
        "set_checkbox",
        "drag_element",
        "scroll_page",
        "upload_file",
        "save_image",
        "get_child_elements",
        "get_sibling_elements",
        "element_exists",
        "element_visible",
    ]
    configs = [
        {"url": fixture_url, "openMode": "current_tab"},
        {"selector": "#choice", "selectBy": "value", "value": "second"},
        {"selector": "#enabled", "checked": True},
        {"sourceSelector": "#drag-source", "targetSelector": "#drag-target"},
        {"direction": "down", "distance": 300, "scrollMode": "wheel"},
        {"selector": "#upload", "filePath": str(upload)},
        {
            "selector": "#fixture-image",
            "savePath": "fixture-image.png",
            "variableName": "saved_image",
        },
        {"parentSelector": "#children", "variableName": "children"},
        {
            "elementSelector": "#sibling-target",
            "siblingType": "all",
            "variableName": "siblings",
        },
        {"selector": "#bottom-marker"},
        {"selector": "#enabled"},
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

    async with launch_workflow_session(command) as browser:
        context = ExecutionContext(
            browser=browser,
            artifacts=cast(ArtifactWriter, FileArtifacts(tmp_path / "artifacts")),
        )
        result = await WorkflowRuntime(
            build_production_executor_registry()
        ).execute(document, context)
        state = await browser.current_page().evaluate(
            """() => ({
              choice: document.querySelector('#choice').value,
              checked: document.querySelector('#enabled').checked,
              dropped: document.querySelector('#drag-target').dataset.dropped,
              upload: document.querySelector('#upload').files[0]?.name
            })"""
        )

    assert result.success is True
    assert state == {
        "choice": "second",
        "checked": True,
        "dropped": "true",
        "upload": "upload.txt",
    }
    assert context.variables["children"] == ["#child-a", "#child-b"]
    assert context.variables["siblings"] == ["#sibling-a", "#sibling-b"]
    assert Path(context.variables["saved_image"]).read_bytes().startswith(b"\x89PNG")
