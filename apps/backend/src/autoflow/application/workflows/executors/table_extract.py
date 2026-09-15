"""Approved HTML table extractor migrated from frozen WebRPA.

Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
backend/app/executors/extract_table_data.py. Licensed under LICENSE.WebRPA.

Excel output is deliberately routed through the AutoFlow workflow workbook
renderer and artifact writer so the executor cannot write arbitrary host paths.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.registry import register_executor
from autoflow.domain.workflows.execution import ExecutionContext

_MAX_ROWS = 100_000
_MAX_COLUMNS = 500
_MAX_CELLS = 1_000_000
_MAX_TEXT_BYTES = 32 * 1024 * 1024
_MAX_XLSX_BYTES = 64 * 1024 * 1024
_XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_EXTRACT_TABLE_SCRIPT = """
el => {
  const rows = Array.from(el.querySelectorAll('tr'));
  if (rows.length > 100000) {
    return {error: '表格行数超过工作流安全限制'};
  }

  const encoder = new TextEncoder();
  const tableData = [];
  let cellCount = 0;
  let textBytes = 0;

  for (const row of rows) {
    const cells = Array.from(row.querySelectorAll('th, td'));
    if (cells.length === 0) continue;
    if (cells.length > 500) {
      return {error: '表格列数超过工作流安全限制'};
    }

    cellCount += cells.length;
    if (cellCount > 1000000) {
      return {error: '表格单元格数量超过工作流安全限制'};
    }

    const values = cells.map(cell => cell.innerText.trim());
    for (const value of values) {
      textBytes += encoder.encode(value).length;
      if (textBytes > 33554432) {
        return {error: '表格文本大小超过工作流安全限制'};
      }
    }
    tableData.push(values);
  }

  return {rowCount: rows.length, tableData};
}
"""


def _current_page(context: ExecutionContext) -> Any | None:
    browser = context.browser
    if browser is None:
        return None
    try:
        active_page = getattr(browser, "active_page", None)
        return active_page() if active_page is not None else browser.current_page()
    except Exception:  # noqa: BLE001 -- browser state is serialized as a node result.
        return None


def _validate_table_data(value: Any) -> tuple[list[list[str]] | None, str | None]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None, "表格数据格式无效"
    if len(value) > _MAX_ROWS:
        return None, "表格行数超过工作流安全限制"

    rows: list[list[str]] = []
    cell_count = 0
    text_bytes = 0
    for raw_row in value:
        if not isinstance(raw_row, Sequence) or isinstance(
            raw_row, (str, bytes, bytearray)
        ):
            return None, "表格数据格式无效"
        if len(raw_row) > _MAX_COLUMNS:
            return None, "表格列数超过工作流安全限制"

        row: list[str] = []
        for raw_cell in raw_row:
            if not isinstance(raw_cell, str):
                return None, "表格数据格式无效"
            row.append(raw_cell)
            text_bytes += len(raw_cell.encode("utf-8"))
        rows.append(row)
        cell_count += len(row)

        if cell_count > _MAX_CELLS:
            return None, "表格单元格数量超过工作流安全限制"
        if text_bytes > _MAX_TEXT_BYTES:
            return None, "表格文本大小超过工作流安全限制"

    return rows, None


@register_executor
class ExtractTableDataExecutor(ModuleExecutor):
    """Extract a two-dimensional string array from an HTML table."""

    requires_browser = True

    @property
    def module_type(self) -> str:
        return "extract_table_data"

    async def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> ModuleResult:

        selector = self.get_text(config.get("tableSelector", ""), context).strip()
        if not selector:
            return ModuleResult(success=False, error="表格选择器不能为空")

        page = _current_page(context)
        if page is None:
            return ModuleResult(success=False, error="未找到活动页面")

        variable_name = config.get("variableName", "table_data")
        export_to_excel = config.get("exportToExcel", False)
        excel_path = self.get_text(config.get("excelPath", ""), context).strip()
        include_header = config.get("includeHeader", True)
        header_row = int(config.get("headerRow", 0))

        table = page.locator(selector).first
        try:
            await table.wait_for(state="attached", timeout_ms=10_000)
        except Exception:  # noqa: BLE001 -- locator failures map to frozen result.
            return ModuleResult(success=False, error=f"未找到表格元素: {selector}")

        try:
            if not await table.is_visible():
                return ModuleResult(success=False, error=f"表格元素不可见: {selector}")

            tag_name = await table.evaluate("el => el.tagName")
            if str(tag_name).upper() != "TABLE":
                table = table.locator("xpath=ancestor-or-self::table").first
                if not await table.is_visible():
                    return ModuleResult(success=False, error="选择的元素不在表格内")

            extracted = await table.evaluate(_EXTRACT_TABLE_SCRIPT)
            if not isinstance(extracted, Mapping):
                return ModuleResult(
                    success=False, error="提取表格失败: 表格数据格式无效"
                )

            extraction_error = extracted.get("error")
            if extraction_error:
                return ModuleResult(
                    success=False, error=f"提取表格失败: {extraction_error}"
                )

            row_count = extracted.get("rowCount")
            if not isinstance(row_count, int):
                return ModuleResult(
                    success=False, error="提取表格失败: 表格数据格式无效"
                )
            if row_count == 0:
                return ModuleResult(success=False, error="表格中没有行")

            table_data, validation_error = _validate_table_data(
                extracted.get("tableData")
            )
            if validation_error is not None:
                return ModuleResult(
                    success=False, error=f"提取表格失败: {validation_error}"
                )
            assert table_data is not None
            if not table_data:
                return ModuleResult(success=False, error="表格为空或未找到数据")
        except Exception as exc:  # noqa: BLE001 -- preserve frozen executor errors.
            return ModuleResult(success=False, error=f"提取表格失败: {exc}")

        if variable_name:
            context.set_variable(variable_name, table_data)
        column_count = max((len(row) for row in table_data), default=0)
        result_data: dict[str, Any] = {
            "rowCount": len(table_data),
            "columnCount": column_count,
            "tableData": table_data,
        }
        message = f"成功提取表格数据（{len(table_data)}行 x {column_count}列）"

        if not export_to_excel:
            return ModuleResult(success=True, data=result_data, message=message)

        try:
            if context.artifacts is None:
                raise RuntimeError("文件输出服务不可用")

            renderer = context.table_workbooks
            render_grid = getattr(renderer, "render_grid", None)
            if not callable(render_grid):
                raise TypeError("表格提取Excel渲染接口不可用")

            content = await render_grid(
                rows=table_data,
                sheet_name="表格数据",
                header_row=header_row,
                include_header=include_header,
                cancellation=context.cancellation,
            )
            if not isinstance(content, bytes) or not content:
                raise RuntimeError("Excel渲染结果无效")
            if len(content) > _MAX_XLSX_BYTES:
                raise RuntimeError("Excel文件大小超过工作流安全限制")

            output_path = excel_path or "table_data.xlsx"
            written_path = await context.artifacts.write_binary_output(
                output_path=output_path,
                content=content,
                mime_type=_XLSX_MIME_TYPE,
                expected_identity=None,
            )
        except Exception as exc:  # noqa: BLE001 -- renderer/artifact errors are results.
            return ModuleResult(success=False, error=f"导出Excel失败: {exc}")

        result_data["excelPath"] = written_path
        return ModuleResult(
            success=True,
            data=result_data,
            message=f"{message}，已导出到: {written_path}",
        )
