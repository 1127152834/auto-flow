from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import DesktopActionResult, ExecutionContext


class Actions:
    def __init__(self) -> None:
        self.requests: list[tuple[str, Mapping[str, Any], float]] = []

    async def perform(
        self,
        action: str,
        payload: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> DesktopActionResult:
        self.requests.append((action, payload, timeout_seconds))
        port = int(payload.get("port", 0))
        return DesktopActionResult(
            True,
            {
                "success": True,
                "url": f"http://192.0.2.1:{port}",
                "ip": "192.0.2.1",
                "port": port,
            },
        )


@pytest.mark.asyncio
async def test_file_and_folder_shares_use_persistent_host(
    tmp_path: Path,
) -> None:
    file = tmp_path / "file.txt"
    file.write_text("abc", encoding="utf-8")
    folder = tmp_path / "folder"
    folder.mkdir()
    actions = Actions()
    context = ExecutionContext(desktop_actions=actions)
    registry = build_production_executor_registry()

    file_result = await registry.get("share_file").execute(
        {"filePath": str(file), "port": 8123, "resultVariable": "file_url"},
        context,
    )
    folder_result = await registry.get("share_folder").execute(
        {
            "folderPath": str(folder),
            "port": 8124,
            "shareName": "资料",
            "allowWrite": False,
        },
        context,
    )
    stop_result = await registry.get("stop_share").execute(
        {"port": 8124}, context
    )

    assert file_result.data["size"] == 3
    assert folder_result.data["name"] == "资料"
    assert stop_result.data == {"port": 8124}
    assert context.variables == {
        "file_url": "http://192.0.2.1:8123",
        "share_url": "http://192.0.2.1:8124",
    }
    assert [request[0] for request in actions.requests] == [
        "start_file_share",
        "start_file_share",
        "stop_file_share",
    ]


@pytest.mark.asyncio
async def test_screen_share_clamps_parameters_and_stops() -> None:
    actions = Actions()
    context = ExecutionContext(desktop_actions=actions)
    registry = build_production_executor_registry()

    started = await registry.get("start_screen_share").execute(
        {"port": 9001, "fps": 99, "quality": 1, "scale": 2}, context
    )
    stopped = await registry.get("stop_screen_share").execute(
        {"port": 9001}, context
    )

    assert started.data == {
        "url": "http://192.0.2.1:9001",
        "ip": "192.0.2.1",
        "port": 9001,
        "fps": 60,
        "quality": 10,
        "scale": 1.0,
    }
    assert stopped.data == {"port": 9001}
    assert actions.requests[0][1] == {
        "port": 9001,
        "fps": 60,
        "quality": 10,
        "scale": 1.0,
    }


@pytest.mark.asyncio
async def test_share_nodes_validate_local_paths(tmp_path: Path) -> None:
    registry = build_production_executor_registry()
    assert (await registry.get("share_file").execute({}, ExecutionContext())).error == (
        "文件路径不能为空"
    )
    folder = tmp_path / "folder"
    folder.mkdir()
    assert (
        await registry.get("share_file").execute(
            {"filePath": str(folder)}, ExecutionContext()
        )
    ).error == f"路径不是文件: {folder}"
