"""Windows printer executor migrated from WebRPA@5ccb900e.

Source: backend/app/executors/utility_tools.py#PrinterCallExecutor.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_int


class PrinterCallExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "printer_call"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        file_path = context.resolve_value(config.get("filePath", ""))
        printer_name = context.resolve_value(config.get("printerName", ""))
        copies = to_int(config.get("copies", 1), 1, context)
        color_mode = str(context.resolve_value(config.get("colorMode", "color")))
        duplex = str(context.resolve_value(config.get("duplex", "none")))
        orientation = str(context.resolve_value(config.get("orientation", "portrait")))
        paper_size = str(context.resolve_value(config.get("paperSize", "A4")))
        if not file_path:
            return ModuleResult(success=False, error="文件路径不能为空")
        try:
            name = await asyncio.to_thread(
                _print_file,
                Path(str(file_path)),
                str(printer_name or ""),
                copies,
                color_mode,
                duplex,
                orientation,
                paper_size,
            )
            return ModuleResult(
                success=True, message=f"已发送打印任务到 {name} (份数: {copies})"
            )
        except ImportError:
            return ModuleResult(success=False, error="缺少pywin32库，无法调用打印机")
        except FileNotFoundError:
            return ModuleResult(success=False, error=f"文件不存在: {file_path}")
        except Exception as error:  # noqa: BLE001 - native printer errors become node errors.
            return ModuleResult(success=False, error=f"打印失败: {error}")


def _print_file(
    file: Path,
    printer_name: str,
    copies: int,
    color_mode: str,
    duplex: str,
    orientation: str,
    paper_size: str,
) -> str:
    import win32api  # type: ignore[import-not-found,import-untyped]
    import win32print  # type: ignore[import-not-found,import-untyped]

    if not file.exists():
        raise FileNotFoundError(file)
    printer_name = printer_name or str(win32print.GetDefaultPrinter())
    printers = [
        printer[2]
        for printer in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
    ]
    if printer_name not in printers:
        raise ValueError(f"打印机不存在: {printer_name}")
    handle = win32print.OpenPrinter(printer_name)
    try:
        properties = win32print.GetPrinter(handle, 2)
        mode = properties["pDevMode"]
        mode.Copies = copies
        mode.Color = 2 if color_mode == "grayscale" else 1
        mode.Duplex = {"long_edge": 2, "short_edge": 3}.get(duplex, 1)
        mode.Orientation = 2 if orientation == "landscape" else 1
        paper_sizes = {"A4": 9, "A3": 8, "Letter": 1, "Legal": 5, "A5": 11}
        if paper_size in paper_sizes:
            mode.PaperSize = paper_sizes[paper_size]
        properties["pDevMode"] = mode
        win32print.SetPrinter(handle, 2, properties, 0)
        win32api.ShellExecute(
            0, "print", str(file), f'/d:"{printer_name}"', ".", 0
        )
    finally:
        win32print.ClosePrinter(handle)
    return printer_name


PRINTER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (PrinterCallExecutor,)
