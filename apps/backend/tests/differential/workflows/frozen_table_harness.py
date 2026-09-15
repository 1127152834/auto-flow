# mypy: ignore-errors
# Imports execute only against the frozen WebRPA PYTHONPATH.
from __future__ import annotations

import asyncio
import io
import json
import sys
import tempfile
import types
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any

import app.executors.table as table_module
from app.executors.base import ExecutionContext
from app.executors.table import (
    TableAddColumnExecutor,
    TableAddRowExecutor,
    TableClearExecutor,
    TableDeleteRowExecutor,
    TableExportExecutor,
    TableGetCellExecutor,
    TableSetCellExecutor,
)

SOURCE_EXECUTORS = {
    executor().module_type: executor
    for executor in (
        TableAddRowExecutor,
        TableAddColumnExecutor,
        TableSetCellExecutor,
        TableGetCellExecutor,
        TableDeleteRowExecutor,
        TableClearExecutor,
        TableExportExecutor,
    )
}


async def export_contract(payload: dict[str, Any]) -> dict[str, Any]:
    captured: dict[str, Any] = {"rows": []}

    class FakeCollector:
        def add_row(self, row: dict[str, Any]) -> None:
            captured["rows"].append(row)

        def to_csv(self, path: str) -> str:
            captured["format"] = "csv"
            Path(path).write_bytes(b"csv")
            return path

        def to_excel(self, path: str, sheet_name: str) -> str:
            captured["format"] = "excel"
            captured["sheet_name"] = sheet_name
            Path(path).write_bytes(b"xlsx")
            return path

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> FixedDateTime:
            return cls(2026, 9, 16, 12, 34, 56)

    data_collector_module = types.ModuleType("app.services.data_collector")
    data_collector_module.DataCollector = FakeCollector
    original_data_collector = sys.modules.get("app.services.data_collector")
    original_datetime = table_module.datetime
    sys.modules["app.services.data_collector"] = data_collector_module
    table_module.datetime = FixedDateTime
    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config = payload["config"].copy()
            if payload.get("save_mode") == "file":
                config["savePath"] = str(
                    Path(temporary_directory) / payload["save_name"]
                )
            else:
                config["savePath"] = temporary_directory
            context = ExecutionContext(data_rows=payload["data_rows"])
            result = await TableExportExecutor().execute(config, context)
            path = result.data["path"]
            name = Path(path).name
            variables = {
                key: name if value == path else value
                for key, value in context.variables.items()
            }
            return {
                "success": result.success,
                "message": result.message.replace(path, name),
                "data": {**result.data, "path": name, "file_size": None},
                "variables": variables,
                "collector": captured,
            }
    finally:
        table_module.datetime = original_datetime
        if original_data_collector is None:
            sys.modules.pop("app.services.data_collector", None)
        else:
            sys.modules["app.services.data_collector"] = original_data_collector


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("operation") == "types":
        return {"types": sorted(SOURCE_EXECUTORS)}
    if payload.get("operation") == "export_contract":
        return await export_contract(payload)
    context = ExecutionContext(
        variables=payload.get("variables", {}),
        data_rows=payload.get("data_rows", []),
        current_row=payload.get("current_row", {}),
    )
    try:
        result = await SOURCE_EXECUTORS[payload["type"]]().execute(
            payload["config"], context
        )
        result_payload = {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
            "branch": result.branch,
        }
    except Exception as error:  # noqa: BLE001 -- capture frozen exception parity.
        result_payload = {
            "raised": type(error).__name__,
            "error": str(error),
        }
    return {
        "result": result_payload,
        "variables": context.variables,
        "data_rows": context.data_rows,
        "current_row": context.current_row,
    }


if __name__ == "__main__":
    output = io.StringIO()
    payload = json.load(sys.stdin)
    with redirect_stdout(output):
        result = asyncio.run(run(payload))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
