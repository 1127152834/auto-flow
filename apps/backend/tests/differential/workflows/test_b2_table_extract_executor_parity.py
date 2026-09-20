from __future__ import annotations

import importlib
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.infrastructure.filesystem.workflow_table_workbook import (
    OpenpyxlTableWorkbookRenderer,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b2_table_extract_harness.py")

TABLES = {
    "#headers": [["姓名", "年龄"], ["Ada", "37"], ["李雷", "41"]],
    "#plain": [["Ada", "37"], ["李雷", "41"]],
    "#offset": [["说明", ""], ["姓名", "年龄"], ["Ada", "37"]],
}


def frozen_result(case: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(FROZEN_HARNESS), case],
        check=True,
        capture_output=True,
        text=True, encoding="utf-8",
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout)


def executor_type() -> Any:
    module = importlib.import_module(
        "autoflow.application.workflows.executors.table_extract"
    )
    return module.ExtractTableDataExecutor


class Locator:
    def __init__(
        self, selector: str, rows: list[list[str]], kind: str = "element"
    ) -> None:
        self.selector = selector
        self.rows = rows
        self.kind = kind

    @property
    def first(self) -> Locator:
        return self

    def locator(self, selector: str) -> Locator:
        if selector == "xpath=ancestor-or-self::table":
            return Locator(self.selector, self.rows, "table")
        raise AssertionError(selector)

    async def wait_for(self, **_options: Any) -> None:
        if self.selector == "#missing":
            raise TimeoutError("missing")

    async def is_visible(self) -> bool:
        return self.selector != "#outside"

    async def evaluate(self, expression: str) -> Any:
        if expression == "el => el.tagName":
            return (
                "DIV"
                if self.selector in {"#inside", "#outside"} and self.kind != "table"
                else "TABLE"
            )
        return {"rowCount": len(self.rows), "tableData": self.rows}


class Page:
    id = "page-1"
    url = "about:blank"
    closed = False

    def locator(self, selector: str) -> Locator:
        return Locator(selector, TABLES.get(selector, TABLES["#headers"]))


class Session:
    def current_page(self) -> Page:
        return Page()


class Artifacts:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def write_binary_output(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return f"/managed/{Path(kwargs['output_path']).name}"


class GridRenderer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def render_grid(self, **kwargs: Any) -> bytes:
        self.calls.append(kwargs)
        return b"xlsx"


def normalize(result: Any) -> dict[str, Any]:
    data = result.data
    if isinstance(data, dict) and data.get("excelPath"):
        data = {**data, "excelPath": Path(data["excelPath"]).name}
    return {
        "success": result.success,
        "messagePrefix": result.message.split("，", 1)[0],
        "error": result.error,
        "data": data,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["headers", "plain"])
async def test_table_rows_and_variable_output_match_frozen_source(case: str) -> None:
    config = (
        {"tableSelector": "#headers"}
        if case == "headers"
        else {
            "tableSelector": "#plain",
            "includeHeader": False,
            "headerRow": 1,
            "variableName": "rows",
        }
    )
    context = ExecutionContext(browser=Session())

    result = await executor_type()().execute(config, context)

    assert {
        "result": normalize(result),
        "variables": context.variables,
    } == frozen_result(case)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["missing", "outside"])
async def test_selector_errors_match_frozen_source(case: str) -> None:
    context = ExecutionContext(browser=Session())

    result = await executor_type()().execute({"tableSelector": f"#{case}"}, context)

    assert {
        "result": normalize(result),
        "variables": context.variables,
    } == frozen_result(case)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "include_header"),
    [("export_header", True), ("export_plain", False)],
)
async def test_excel_export_preserves_header_controls_through_managed_boundaries(
    case: str, include_header: bool
) -> None:
    renderer = GridRenderer()
    artifacts = Artifacts()
    context = ExecutionContext(
        browser=Session(),
        artifacts=artifacts,
        table_workbooks=renderer,
    )

    result = await executor_type()().execute(
        {
            "tableSelector": "#offset",
            "includeHeader": include_header,
            "headerRow": 1,
            "exportToExcel": True,
            "excelPath": "exports/table.xlsx",
            "variableName": "rows",
        },
        context,
    )

    frozen = frozen_result(case)
    assert normalize(result) == frozen["result"]
    assert context.variables == frozen["variables"]
    assert renderer.calls == [
        {
            "rows": TABLES["#offset"],
            "sheet_name": "表格数据",
            "header_row": 1,
            "include_header": include_header,
            "cancellation": None,
        }
    ]
    assert artifacts.calls == [
        {
            "output_path": "exports/table.xlsx",
            "content": b"xlsx",
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "expected_identity": None,
        }
    ]
    assert frozen["values"] == [["说明", None], ["姓名", "年龄"], ["Ada", "37"]]
    assert frozen["headerBold"] == [include_header, include_header]


@pytest.mark.asyncio
async def test_export_reports_missing_grid_renderer_without_writing() -> None:
    result = await executor_type()().execute(
        {"tableSelector": "#headers", "exportToExcel": True},
        ExecutionContext(browser=Session(), artifacts=Artifacts()),
    )

    assert result.success is False
    assert result.error == "导出Excel失败: 表格提取Excel渲染接口不可用"


@pytest.mark.asyncio
async def test_real_openpyxl_grid_renderer_and_artifact_writer() -> None:
    artifacts = Artifacts()
    result = await executor_type()().execute(
        {
            "tableSelector": "#offset",
            "includeHeader": True,
            "headerRow": 1,
            "exportToExcel": True,
            "excelPath": "exports/真实表格.xlsx",
        },
        ExecutionContext(
            browser=Session(),
            artifacts=artifacts,
            table_workbooks=OpenpyxlTableWorkbookRenderer(),
        ),
    )

    assert result.success is True
    assert len(artifacts.calls) == 1
    content = artifacts.calls[0]["content"]
    workbook = load_workbook(io.BytesIO(content))
    try:
        sheet = workbook["表格数据"]
        assert list(sheet.values) == [
            ("说明", None),
            ("姓名", "年龄"),
            ("Ada", "37"),
        ]
        assert sheet["A1"].font.bold is False
        assert sheet["A2"].font.bold is True
        assert sheet["B2"].font.bold is True
    finally:
        workbook.close()
