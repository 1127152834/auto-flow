"""Log executors migrated from WebRPA@5ccb900e.

Sources: backend/app/executors/basic.py and advanced.py.
License and adaptation record: LICENSE.WebRPA.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult


class PrintLogExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "print_log"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        message = context.resolve_value(config.get("logMessage", "")) or "(空日志)"
        level = context.resolve_value(config.get("logLevel", "info")) or "info"
        return ModuleResult(
            success=True,
            message=str(message),
            data={"level": str(level), "message": str(message)},
            log_level=str(level),
        )


class ExportLogExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "export_log"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        writer = context.node_artifacts
        if writer is None:
            return ModuleResult(success=False, error="运行产物服务不可用")
        log_format = str(config.get("logFormat", "txt")).lower()
        if log_format not in {"txt", "json", "csv"}:
            log_format = "txt"
        output_path = str(context.resolve_value(config.get("outputPath", "")) or "")
        if not output_path:
            stamp = context.clock.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"logs/workflow_log_{stamp}.{log_format}"
        logs = [dict(item) for item in context.log_records if isinstance(item, Mapping)]
        include_timestamp = config.get("includeTimestamp", True) is not False
        include_level = config.get("includeLevel", True) is not False
        include_duration = config.get("includeDuration", True) is not False
        try:
            content, encoding, mime_type = _serialize_logs(
                logs,
                log_format,
                include_timestamp=include_timestamp,
                include_level=include_level,
                include_duration=include_duration,
            )
            actual_path = await writer.write_text(
                output_path=output_path,
                content=content,
                separator="",
                encoding=encoding,
                append=False,
                mime_type=mime_type,
            )
        except Exception as error:  # noqa: BLE001 - file errors become node errors.
            return ModuleResult(success=False, error=f"导出日志失败: {error}")
        result = {
            "output_path": actual_path,
            "log_count": len(logs),
            "format": log_format,
            "file_size": len(content.encode(encoding)),
        }
        variable_name = config.get("resultVariable", "")
        if isinstance(variable_name, str) and variable_name:
            context.set_variable(variable_name, result)
        return ModuleResult(
            success=True,
            message=f"已导出 {len(logs)} 条日志到 {actual_path}",
            data=result,
        )


def _serialize_logs(
    logs: list[dict[str, Any]],
    log_format: str,
    *,
    include_timestamp: bool,
    include_level: bool,
    include_duration: bool,
) -> tuple[str, str, str]:
    fields: list[str] = []
    if include_timestamp:
        fields.append("timestamp")
    if include_level:
        fields.append("level")
    fields.append("message")
    if include_duration:
        fields.append("duration")
    fields.append("nodeId")
    filtered = [{key: item.get(key, "") for key in fields} for item in logs]
    if log_format == "json":
        return (
            json.dumps(filtered, ensure_ascii=False, indent=2),
            "utf-8",
            "application/json",
        )
    if log_format == "csv":
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(filtered)
        return output.getvalue(), "utf-8-sig", "text/csv"
    lines: list[str] = []
    for item in filtered:
        parts: list[str] = []
        if include_timestamp and item.get("timestamp"):
            parts.append(f"[{item['timestamp']}]")
        if include_level and item.get("level"):
            parts.append(f"[{str(item['level']).upper()}]")
        parts.append(str(item.get("message", "")))
        if include_duration and item.get("duration"):
            parts.append(f"({float(item['duration']):.2f}ms)")
        lines.append(" ".join(parts))
    return "\n".join(lines), "utf-8", "text/plain"


LOG_EXECUTORS = (PrintLogExecutor, ExportLogExecutor)
