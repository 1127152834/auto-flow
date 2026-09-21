from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_printer_harness.py")


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
async def test_printer_result_and_native_settings_match_frozen_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    file = tmp_path / "document.txt"
    file.write_text("print", encoding="utf-8")
    mode = SimpleNamespace()
    calls: list[list[Any]] = []
    monkeypatch.setitem(
        sys.modules,
        "win32print",
        SimpleNamespace(
            PRINTER_ENUM_LOCAL=1,
            PRINTER_ENUM_CONNECTIONS=2,
            GetDefaultPrinter=lambda: "Office",
            EnumPrinters=lambda _flags: [(None, None, "Office")],
            OpenPrinter=lambda name: calls.append(["open", name]) or "handle",
            GetPrinter=lambda _handle, _level: {"pDevMode": mode},
            SetPrinter=lambda handle, level, _properties, command: calls.append(
                ["set", handle, level, command]
            ),
            ClosePrinter=lambda handle: calls.append(["close", handle]),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "win32api",
        SimpleNamespace(ShellExecute=lambda *args: calls.append(["print", *args])),
    )
    payload = {
        "config": {
            "filePath": str(file),
            "copies": 2,
            "colorMode": "grayscale",
            "duplex": "short_edge",
            "orientation": "landscape",
            "paperSize": "A5",
        }
    }
    context = ExecutionContext()
    executor = build_production_executor_registry().get("printer_call")
    assert executor is not None
    result = await executor.execute(payload["config"], context)
    target = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
        "mode": vars(mode),
        "calls": calls,
    }

    assert target == source(payload)


@pytest.mark.asyncio
async def test_printer_empty_path_matches_frozen_source() -> None:
    context = ExecutionContext()
    executor = build_production_executor_registry().get("printer_call")
    assert executor is not None
    result = await executor.execute({}, context)
    target = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }
    expected = source({"config": {}})
    assert target == {key: expected[key] for key in target}
