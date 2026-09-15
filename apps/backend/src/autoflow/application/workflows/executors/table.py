"""数据表格操作模块执行器"""

from __future__ import annotations

# ruff: noqa: BLE001 -- frozen executors preserve broad exception handling.
# Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
# backend/app/executors/table.py.
import asyncio
import csv
import io
import json
from datetime import date, datetime, time
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor

_MAX_TABLE_ROWS = 100_000
_MAX_TABLE_COLUMNS = 500
_MAX_ROW_DATA_BYTES = 1024 * 1024
_MAX_CSV_BYTES = 8 * 1024 * 1024
_MAX_XLSX_BYTES = 64 * 1024 * 1024
_MAX_TABLE_CELLS = 1_000_000
_MAX_TABLE_NORMALIZED_BYTES = 32 * 1024 * 1024
_VALID_EXPORT_EXTENSIONS = (".xlsx", ".xls", ".csv")
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


async def _checkpoint(context: ExecutionContext, index: int) -> None:
    if context.cancellation is None or index % 256:
        return
    context.cancellation.raise_if_cancelled()
    await asyncio.sleep(0)
    context.cancellation.raise_if_cancelled()


class _CsvCapacityError(Exception):
    pass


def _raise_if_cancelled(context: ExecutionContext) -> None:
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()


def _validate_json_shape(value: Any, *, depth: int = 0) -> int:
    if depth > 20:
        raise ValueError("行数据结构超过工作流安全限制")
    if isinstance(value, dict):
        count = len(value)
        for key, item in value.items():
            count += _validate_json_shape(key, depth=depth + 1)
            count += _validate_json_shape(item, depth=depth + 1)
    elif isinstance(value, (list, tuple)):
        count = len(value)
        for item in value:
            count += _validate_json_shape(item, depth=depth + 1)
    else:
        count = 1
    if count > 100_000:
        raise ValueError("行数据结构超过工作流安全限制")
    return count


def _table_has_sensitive_data(context: ExecutionContext) -> bool:
    return bool(context.sensitive_table_cells)


def _shift_sensitive_rows_after_delete(
    context: ExecutionContext, deleted_index: int
) -> None:
    context.sensitive_table_cells = {
        (row_index - 1 if row_index > deleted_index else row_index, column)
        for row_index, column in context.sensitive_table_cells
        if row_index != deleted_index
    }


def _table_capacity_error(rows: list[dict[str, Any]]) -> str | None:
    if len(rows) > _MAX_TABLE_ROWS:
        return "数据表格超过工作流安全限制"
    columns: set[Any] = set()
    normalized_bytes = 0
    for row in rows:
        columns.update(row)
        if len(columns) > _MAX_TABLE_COLUMNS:
            return "数据表格列数超过工作流安全限制"
        for key, value in row.items():
            normalized_bytes += len(str(key).encode("utf-8"))
            normalized_bytes += len(str(_csv_cell(value)).encode("utf-8"))
            if normalized_bytes > _MAX_TABLE_NORMALIZED_BYTES:
                return "数据表格内容超过工作流安全限制"
    if len(rows) * len(columns) > _MAX_TABLE_CELLS:
        return "数据表格单元格数量超过工作流安全限制"
    return None


class _LimitedTextBuffer(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.byte_count = 0

    def write(self, value: str) -> int:
        byte_count = len(value.encode("utf-8"))
        if self.byte_count + byte_count > _MAX_CSV_BYTES:
            raise _CsvCapacityError
        self.byte_count += byte_count
        return super().write(value)


@register_executor
class TableAddRowExecutor(ModuleExecutor):
    """添加数据行模块执行器"""

    @property
    def module_type(self) -> str:
        return "table_add_row"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        raw_row_data = config.get("rowData", "")
        row_data_str, sensitive = context.resolve_value_with_sensitivity(raw_row_data)

        if not row_data_str:
            return ModuleResult(success=False, error="行数据不能为空")

        try:
            _raise_if_cancelled(context)
            if (
                not isinstance(row_data_str, str)
                or len(row_data_str.encode("utf-8")) > _MAX_ROW_DATA_BYTES
            ):
                return ModuleResult(success=False, error="行数据超过工作流安全限制")
            row_data = json.loads(row_data_str)

            if not isinstance(row_data, dict):
                return ModuleResult(success=False, error="行数据必须是JSON对象格式")
            if len(row_data) > _MAX_TABLE_COLUMNS:
                return ModuleResult(
                    success=False, error="数据表格列数超过工作流安全限制"
                )
            _validate_json_shape(row_data)
            capacity_error = _table_capacity_error([*context.data_rows, row_data])
            if capacity_error is not None:
                return ModuleResult(success=False, error=capacity_error)

            _raise_if_cancelled(context)
            row_index = len(context.data_rows)
            context.data_rows.append(row_data)
            if sensitive:
                context.sensitive_table_cells.update(
                    (row_index, column) for column in row_data
                )

            return ModuleResult(
                success=True,
                message=f"已添加数据行，当前共 {len(context.data_rows)} 行",
                data={
                    "row": None if sensitive else row_data,
                    "total_rows": len(context.data_rows),
                },
            )

        except json.JSONDecodeError as e:
            return ModuleResult(success=False, error=f"JSON解析失败: {e!s}")
        except Exception as e:
            return ModuleResult(success=False, error=f"添加数据行失败: {e!s}")


@register_executor
class TableAddColumnExecutor(ModuleExecutor):
    """添加数据列模块执行器"""

    @property
    def module_type(self) -> str:
        return "table_add_column"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        column_name, column_sensitive = context.resolve_value_with_sensitivity(
            config.get("columnName", "")
        )
        default_value, default_sensitive = context.resolve_value_with_sensitivity(
            config.get("defaultValue", "")
        )

        if not column_name:
            return ModuleResult(success=False, error="列名不能为空")
        if column_sensitive:
            return ModuleResult(success=False, error="列名不能使用凭据值")

        try:
            if len(context.data_rows) > _MAX_TABLE_ROWS:
                return ModuleResult(success=False, error="数据表格超过工作流安全限制")

            staged_rows = []
            for index, row in enumerate(context.data_rows):
                await _checkpoint(context, index)
                staged_row = row.copy()
                if column_name not in staged_row:
                    staged_row[column_name] = default_value
                staged_rows.append(staged_row)

            if not staged_rows:
                staged_rows.append({column_name: default_value})

            capacity_error = _table_capacity_error(staged_rows)
            if capacity_error is not None:
                return ModuleResult(success=False, error=capacity_error)

            _raise_if_cancelled(context)
            context.data_rows[:] = staged_rows
            if default_sensitive:
                context.sensitive_table_cells.update(
                    (index, column_name) for index in range(len(staged_rows))
                )

            return ModuleResult(
                success=True,
                message=f"已添加列 '{column_name}'",
                data={
                    "column": column_name,
                    "default": None if default_sensitive else default_value,
                },
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"添加数据列失败: {e!s}")


@register_executor
class TableSetCellExecutor(ModuleExecutor):
    """设置单元格模块执行器"""

    @property
    def module_type(self) -> str:
        return "table_set_cell"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        row_index_str, row_index_sensitive = context.resolve_value_with_sensitivity(
            str(config.get("rowIndex", "0"))
        )
        column_name, column_sensitive = context.resolve_value_with_sensitivity(
            config.get("columnName", "")
        )
        cell_value, cell_sensitive = context.resolve_value_with_sensitivity(
            config.get("cellValue", "")
        )

        if not column_name:
            return ModuleResult(success=False, error="列名不能为空")
        if column_sensitive:
            return ModuleResult(success=False, error="列名不能使用凭据值")
        if row_index_sensitive:
            return ModuleResult(success=False, error="行索引不能使用凭据值")

        try:
            row_index = int(row_index_str)
        except ValueError:
            return ModuleResult(success=False, error=f"无效的行索引: {row_index_str}")

        if not context.data_rows:
            return ModuleResult(success=False, error="数据表格为空")

        if row_index < 0:
            row_index = len(context.data_rows) + row_index

        if row_index < 0 or row_index >= len(context.data_rows):
            return ModuleResult(success=False, error=f"行索引 {row_index} 超出范围")

        try:
            await _checkpoint(context, 0)
            staged_rows = list(context.data_rows)
            staged_row = context.data_rows[row_index].copy()
            staged_row[column_name] = cell_value
            staged_rows[row_index] = staged_row
            capacity_error = _table_capacity_error(staged_rows)
            if capacity_error is not None:
                return ModuleResult(success=False, error=capacity_error)
            context.data_rows[row_index] = staged_row
            cell_identity = (row_index, column_name)
            if cell_sensitive:
                context.sensitive_table_cells.add(cell_identity)
            else:
                context.sensitive_table_cells.discard(cell_identity)

            return ModuleResult(
                success=True,
                message=(
                    f"已设置 [{row_index}][{column_name}]"
                    if cell_sensitive
                    else f"已设置 [{row_index}][{column_name}] = {cell_value}"
                ),
                data={
                    "row": row_index,
                    "column": column_name,
                    "value": None if cell_sensitive else cell_value,
                },
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"设置单元格失败: {e!s}")


@register_executor
class TableGetCellExecutor(ModuleExecutor):
    """获取单元格模块执行器"""

    @property
    def module_type(self) -> str:
        return "table_get_cell"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        row_index_str, row_index_sensitive = context.resolve_value_with_sensitivity(
            str(config.get("rowIndex", "0"))
        )
        column_name, column_sensitive = context.resolve_value_with_sensitivity(
            config.get("columnName", "")
        )
        variable_name = config.get("variableName", "")

        if not column_name:
            return ModuleResult(success=False, error="列名不能为空")
        if column_sensitive:
            return ModuleResult(success=False, error="列名不能使用凭据值")
        if row_index_sensitive:
            return ModuleResult(success=False, error="行索引不能使用凭据值")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")

        try:
            row_index = int(row_index_str)
        except ValueError:
            return ModuleResult(success=False, error=f"无效的行索引: {row_index_str}")

        if not context.data_rows:
            return ModuleResult(success=False, error="数据表格为空")

        if row_index < 0:
            row_index = len(context.data_rows) + row_index

        if row_index < 0 or row_index >= len(context.data_rows):
            return ModuleResult(success=False, error=f"行索引 {row_index} 超出范围")

        row = context.data_rows[row_index]

        if column_name not in row:
            return ModuleResult(success=False, error=f"列 '{column_name}' 不存在")

        await _checkpoint(context, 0)
        value = row[column_name]
        sensitive = (row_index, column_name) in context.sensitive_table_cells
        context.set_variable(variable_name, value, sensitive=sensitive)

        return ModuleResult(
            success=True,
            message=(
                f"已获取 [{row_index}][{column_name}]"
                if sensitive
                else f"获取 [{row_index}][{column_name}] = {value}"
            ),
            data=None if sensitive else value,
        )


@register_executor
class TableDeleteRowExecutor(ModuleExecutor):
    """删除数据行模块执行器"""

    @property
    def module_type(self) -> str:
        return "table_delete_row"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        row_index_str, row_index_sensitive = context.resolve_value_with_sensitivity(
            str(config.get("rowIndex", "0"))
        )

        if row_index_sensitive:
            return ModuleResult(success=False, error="行索引不能使用凭据值")

        try:
            row_index = int(row_index_str)
        except ValueError:
            return ModuleResult(success=False, error=f"无效的行索引: {row_index_str}")

        if not context.data_rows:
            return ModuleResult(success=False, error="数据表格为空")

        original_index = row_index
        if row_index < 0:
            row_index = len(context.data_rows) + row_index

        if row_index < 0 or row_index >= len(context.data_rows):
            return ModuleResult(
                success=False, error=f"行索引 {original_index} 超出范围"
            )

        try:
            await _checkpoint(context, 0)
            sensitive = any(
                sensitive_row == row_index
                for sensitive_row, _ in context.sensitive_table_cells
            )
            deleted_row = context.data_rows.pop(row_index)
            _shift_sensitive_rows_after_delete(context, row_index)

            return ModuleResult(
                success=True,
                message=f"已删除第 {row_index} 行，剩余 {len(context.data_rows)} 行",
                data={
                    "deleted": None if sensitive else deleted_row,
                    "remaining": len(context.data_rows),
                },
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"删除数据行失败: {e!s}")


@register_executor
class TableClearExecutor(ModuleExecutor):
    """清空数据表模块执行器"""

    @property
    def module_type(self) -> str:
        return "table_clear"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        try:
            await _checkpoint(context, 0)
            row_count = len(context.data_rows)
            context.data_rows.clear()
            context.current_row.clear()
            context.sensitive_table_cells.clear()

            return ModuleResult(
                success=True,
                message=f"已清空数据表格 (原有 {row_count} 行)",
                data={"cleared_rows": row_count},
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"清空数据表失败: {e!s}")


def _export_file_name(
    *, export_format: Any, file_name_pattern: Any, timestamp: str
) -> tuple[str, str]:
    file_name = (
        str(file_name_pattern).replace("{时间戳}", timestamp)
        if file_name_pattern
        else f"data_{timestamp}"
    )
    extension = ".xlsx" if export_format == "excel" else ".csv"
    for valid_extension in _VALID_EXPORT_EXTENSIONS:
        if file_name.lower().endswith(valid_extension) and valid_extension != extension:
            file_name = file_name[: -len(valid_extension)]
            break
    if not file_name.lower().endswith(extension):
        file_name += extension
    return file_name, extension


def _artifact_output_path(save_path: Any, file_name: str, extension: str) -> str:
    save_path_text = str(save_path).strip() if save_path else ""
    normalized = save_path_text.replace("\\", "/")
    if normalized:
        lower = normalized.lower()
        if any(lower.endswith(value) for value in _VALID_EXPORT_EXTENSIONS):
            path = PurePosixPath(normalized).with_suffix(extension)
        else:
            path = PurePosixPath(normalized) / file_name
    else:
        path = PurePosixPath(file_name.replace("\\", "/"))

    windows_path = PureWindowsPath(save_path_text or file_name)
    if bool(windows_path.drive) or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("导出路径无效")
    return path.as_posix()


def _csv_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        # CSV has no cell type metadata. Prefix spreadsheet formula-like text so
        # values collected from a page remain literal when the CSV is opened.
        return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value
    if isinstance(value, (int, float, datetime, date, time)):
        return value
    if isinstance(value, (list, dict, tuple, set)):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            return str(value)
    return str(value)


async def _csv_content(context: ExecutionContext) -> tuple[str, int]:
    columns: list[Any] = []
    seen_columns: set[Any] = set()
    for row_index, row in enumerate(context.data_rows):
        await _checkpoint(context, row_index)
        for key in row:
            if key not in seen_columns:
                if len(columns) >= _MAX_TABLE_COLUMNS:
                    raise _CsvCapacityError
                seen_columns.add(key)
                columns.append(key)

    output = _LimitedTextBuffer()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([_csv_cell(column) for column in columns])
    for row_index, row in enumerate(context.data_rows):
        await _checkpoint(context, row_index)
        writer.writerow([_csv_cell(row.get(column)) for column in columns])
    return output.getvalue(), output.byte_count


@register_executor
class TableExportExecutor(ModuleExecutor):
    """导出数据表模块执行器"""

    @property
    def module_type(self) -> str:
        return "table_export"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        export_format, format_sensitive = context.resolve_value_with_sensitivity(
            config.get("exportFormat", "excel")
        )
        save_path, path_sensitive = context.resolve_value_with_sensitivity(
            config.get("savePath", "")
        )
        file_name_pattern, name_sensitive = context.resolve_value_with_sensitivity(
            config.get("fileNamePattern", "")
        )
        sheet_name, sheet_sensitive = context.resolve_value_with_sensitivity(
            config.get("sheetName", "数据")
        )
        variable_name = config.get("variableName", "")

        if not context.data_rows:
            return ModuleResult(success=False, error="数据表格为空，无法导出")
        if len(context.data_rows) > _MAX_TABLE_ROWS:
            return ModuleResult(success=False, error="数据表格超过工作流安全限制")
        if _table_has_sensitive_data(context):
            return ModuleResult(success=False, error="数据表格包含凭据值，不能导出")
        if any((format_sensitive, path_sensitive, name_sensitive, sheet_sensitive)):
            return ModuleResult(success=False, error="导出配置不能使用凭据值")
        if export_format not in {"excel", "csv"}:
            return ModuleResult(
                success=False, error=f"不支持的导出格式: {export_format}"
            )

        try:
            timestamp = context.clock.now().strftime("%Y%m%d_%H%M%S")
            file_name, extension = _export_file_name(
                export_format=export_format,
                file_name_pattern=file_name_pattern,
                timestamp=timestamp,
            )
            final_path = _artifact_output_path(save_path, file_name, extension)
        except ValueError as error:
            return ModuleResult(success=False, error=str(error))

        if context.node_artifacts is None:
            return ModuleResult(
                success=False,
                error=f"写入文件失败: 文件输出服务不可用（路径: {final_path}）",
            )

        if export_format == "excel" and context.table_workbooks is None:
            return ModuleResult(
                success=False,
                error="Excel导出服务不可用",
            )

        if export_format == "excel":
            assert context.table_workbooks is not None
            try:
                existing = await context.node_artifacts.read_binary_output(
                    output_path=final_path,
                    max_bytes=_MAX_XLSX_BYTES,
                )
                workbook_content = await context.table_workbooks.render(
                    rows=context.data_rows,
                    sheet_name=str(sheet_name),
                    existing_content=existing.content,
                    cancellation=context.cancellation,
                )
                written_path = await context.node_artifacts.write_binary_output(
                    output_path=final_path,
                    content=workbook_content,
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    expected_identity=existing.identity,
                )
            except Exception as error:
                return ModuleResult(
                    success=False,
                    error=f"写入文件失败: {error}（路径: {final_path}）",
                )

            if variable_name:
                context.set_variable(variable_name, written_path)
            row_count = len(context.data_rows)
            return ModuleResult(
                success=True,
                message=(
                    f"已导出 {row_count} 行数据到: {written_path} (Sheet: {sheet_name})"
                ),
                data={
                    "path": written_path,
                    "rows": row_count,
                    "format": export_format,
                    "sheet_name": sheet_name,
                    "file_size": len(workbook_content),
                },
            )

        try:
            content, file_size = await _csv_content(context)
        except _CsvCapacityError:
            return ModuleResult(
                success=False,
                error="CSV导出内容超过工作流安全限制",
            )
        except Exception as error:
            return ModuleResult(
                success=False,
                error=f"写入文件失败: {error}（路径: {final_path}）",
            )

        try:
            written_path = await context.node_artifacts.write_text(
                output_path=final_path,
                content=content,
                separator="\n",
                encoding="utf-8",
                append=False,
                mime_type="text/csv",
            )
        except Exception as error:
            return ModuleResult(
                success=False,
                error=f"写入文件失败: {error}（路径: {final_path}）",
            )

        if variable_name:
            context.set_variable(variable_name, written_path)

        row_count = len(context.data_rows)
        return ModuleResult(
            success=True,
            message=f"已导出 {row_count} 行数据到: {written_path}",
            data={
                "path": written_path,
                "rows": row_count,
                "format": export_format,
                "sheet_name": None,
                "file_size": file_size,
            },
        )
