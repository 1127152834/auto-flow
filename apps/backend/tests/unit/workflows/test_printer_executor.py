from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


@pytest.mark.asyncio
async def test_printer_applies_source_options_and_closes_handle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    file = tmp_path / "document.txt"
    file.write_text("print", encoding="utf-8")
    mode = SimpleNamespace()
    calls: list[tuple[object, ...]] = []
    win32print = SimpleNamespace(
        PRINTER_ENUM_LOCAL=1,
        PRINTER_ENUM_CONNECTIONS=2,
        GetDefaultPrinter=lambda: "Office",
        EnumPrinters=lambda _flags: [(None, None, "Office")],
        OpenPrinter=lambda name: calls.append(("open", name)) or "handle",
        GetPrinter=lambda _handle, _level: {"pDevMode": mode},
        SetPrinter=lambda *args: calls.append(("set", *args)),
        ClosePrinter=lambda handle: calls.append(("close", handle)),
    )
    win32api = SimpleNamespace(
        ShellExecute=lambda *args: calls.append(("print", *args))
    )
    monkeypatch.setitem(sys.modules, "win32print", win32print)
    monkeypatch.setitem(sys.modules, "win32api", win32api)
    executor = build_production_executor_registry().get("printer_call")
    assert executor is not None
    result = await executor.execute(
        {
            "filePath": str(file),
            "copies": 2,
            "colorMode": "grayscale",
            "duplex": "long_edge",
            "orientation": "landscape",
            "paperSize": "A3",
        },
        ExecutionContext(),
    )

    assert result.success is True
    assert result.message == "已发送打印任务到 Office (份数: 2)"
    assert (mode.Copies, mode.Color, mode.Duplex, mode.Orientation, mode.PaperSize) == (
        2,
        2,
        2,
        2,
        8,
    )
    assert calls[-1] == ("close", "handle")


@pytest.mark.asyncio
async def test_printer_validates_file_and_printer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executor = build_production_executor_registry().get("printer_call")
    assert executor is not None
    assert (await executor.execute({}, ExecutionContext())).error == "文件路径不能为空"

    win32print = SimpleNamespace(
        PRINTER_ENUM_LOCAL=1,
        PRINTER_ENUM_CONNECTIONS=2,
        GetDefaultPrinter=lambda: "Office",
        EnumPrinters=lambda _flags: [(None, None, "Office")],
    )
    monkeypatch.setitem(sys.modules, "win32print", win32print)
    monkeypatch.setitem(sys.modules, "win32api", SimpleNamespace())
    absent = tmp_path / "absent.txt"
    assert (
        await executor.execute({"filePath": str(absent)}, ExecutionContext())
    ).error == f"文件不存在: {absent}"

    file = tmp_path / "document.txt"
    file.write_text("print", encoding="utf-8")
    assert (
        await executor.execute(
            {"filePath": str(file), "printerName": "Missing"}, ExecutionContext()
        )
    ).error == "打印失败: 打印机不存在: Missing"
