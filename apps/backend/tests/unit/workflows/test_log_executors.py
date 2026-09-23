from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import BinaryOutputSnapshot, ExecutionContext


class TextArtifacts:
    def __init__(self, root: Path) -> None:
        self.root = root

    async def write_text(
        self,
        *,
        output_path: str,
        content: str,
        separator: str,
        encoding: str,
        append: bool,
        mime_type: str,
    ) -> str:
        del separator, append, mime_type
        target = self.root / output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding.removesuffix("-sig"))
        return str(target)

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        raise NotImplementedError

    async def write_binary_output(
        self,
        *,
        output_path: str,
        content: bytes,
        mime_type: str,
        expected_identity: str | None = None,
    ) -> str:
        raise NotImplementedError

    async def read_binary_output(
        self, *, output_path: str, max_bytes: int
    ) -> BinaryOutputSnapshot:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_print_log_preserves_level_and_resolves_message() -> None:
    executor = build_production_executor_registry().get("print_log")
    context = ExecutionContext(variables={"name": "AutoFlow"})

    assert executor is not None
    result = await executor.execute(
        {"logMessage": "完成 {name}", "logLevel": "warning"}, context
    )

    assert result.success is True
    assert result.message == "完成 AutoFlow"
    assert result.log_level == "warning"
    assert result.data == {"level": "warning", "message": "完成 AutoFlow"}


@pytest.mark.asyncio
async def test_export_log_writes_confirmed_run_records_through_artifact_boundary(
    tmp_path: Path,
) -> None:
    executor = build_production_executor_registry().get("export_log")
    context = ExecutionContext(
        artifacts=TextArtifacts(tmp_path),
        log_records=[
            {
                "timestamp": "2026-09-21T00:00:00Z",
                "level": "warning",
                "message": "完成 AutoFlow",
                "duration": 12.5,
                "nodeId": "print",
            }
        ],
    )

    assert executor is not None
    result = await executor.execute(
        {
            "outputPath": "logs/run.json",
            "logFormat": "json",
            "includeTimestamp": True,
            "includeLevel": True,
            "includeDuration": True,
            "resultVariable": "export_result",
        },
        context,
    )

    assert result.success is True
    assert result.data["log_count"] == 1
    assert result.data["format"] == "json"
    assert json.loads((tmp_path / "logs/run.json").read_text()) == context.log_records
    assert context.variables["export_result"] == result.data
