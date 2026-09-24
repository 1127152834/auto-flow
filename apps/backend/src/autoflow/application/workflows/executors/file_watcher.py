"""File watcher trigger migrated from WebRPA@5ccb900e.

Source: backend/app/executors/trigger.py#FileWatcherTriggerExecutor and
backend/app/services/trigger_manager.py. License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_int


class FileWatcherTriggerExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "file_watcher_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        watch_path = context.resolve_value(config.get("watchPath", ""))
        watch_type = context.resolve_value(config.get("watchType", "any"))
        file_pattern = context.resolve_value(config.get("filePattern", "*"))
        timeout = to_int(config.get("timeout", 0), 0, context)
        save_to_variable = str(config.get("saveToVariable", "file_event"))
        if not watch_path:
            return ModuleResult(success=False, error="监控路径不能为空")
        path = Path(str(watch_path))
        if not path.exists():
            return ModuleResult(success=False, error=f"监控路径不存在: {watch_path}")

        await _progress(context, "📁 文件监控已启动")
        if not context.node_uses_sensitive_values:
            await _progress(context, f"📍 监控路径: {watch_path}")
            await _progress(context, f"🔍 监控类型: {watch_type}")
            await _progress(context, f"📄 文件模式: {file_pattern}")
        try:
            event_data = await (
                asyncio.wait_for(
                    _wait_for_change(path, str(watch_type), str(file_pattern)),
                    timeout=timeout,
                )
                if timeout > 0
                else _wait_for_change(path, str(watch_type), str(file_pattern))
            )
        except TimeoutError:
            return ModuleResult(
                success=False, error=f"文件监控等待超时（{timeout}秒）"
            )
        context.set_variable(save_to_variable, event_data)
        return ModuleResult(
            success=True,
            message=(
                f"文件事件已触发: {event_data['eventType']} - "
                f"{event_data['fileName']}"
            ),
            data=event_data,
        )


async def _wait_for_change(
    path: Path, watch_type: str, file_pattern: str
) -> dict[str, str]:
    previous = await asyncio.to_thread(_snapshot, path)
    while True:
        await asyncio.sleep(1)
        current = await asyncio.to_thread(_snapshot, path)
        events = _changes(previous, current, watch_type, file_pattern)
        if events:
            event_type, file_path = events[-1]
            return {
                "eventType": event_type,
                "filePath": file_path,
                "fileName": Path(file_path).name,
                "timestamp": datetime.now().astimezone().isoformat(),
            }
        previous = current


def _snapshot(path: Path) -> dict[str, tuple[float, int]]:
    if path.is_file():
        stat = path.stat()
        return {str(path): (stat.st_mtime, stat.st_size)}
    result: dict[str, tuple[float, int]] = {}
    for item in path.rglob("*"):
        if item.is_file():
            try:
                stat = item.stat()
            except FileNotFoundError:
                continue
            result[str(item)] = (stat.st_mtime, stat.st_size)
    return result


def _changes(
    previous: dict[str, tuple[float, int]],
    current: dict[str, tuple[float, int]],
    watch_type: str,
    file_pattern: str,
) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    if watch_type in {"created", "any"}:
        events.extend(
            ("created", path)
            for path in current
            if path not in previous and fnmatch.fnmatch(Path(path).name, file_pattern)
        )
    if watch_type in {"modified", "any"}:
        events.extend(
            ("modified", path)
            for path, state in current.items()
            if path in previous
            and state[0] != previous[path][0]
            and fnmatch.fnmatch(Path(path).name, file_pattern)
        )
    if watch_type in {"deleted", "any"}:
        events.extend(
            ("deleted", path)
            for path in previous
            if path not in current and fnmatch.fnmatch(Path(path).name, file_pattern)
        )
    return events


async def _progress(context: ExecutionContext, message: str) -> None:
    context.log_records.append(
        {
            "timestamp": context.clock.now().isoformat(),
            "level": "info",
            "message": message,
            "duration": 0,
            "nodeId": context.current_node_id or "",
        }
    )
    await context.send_progress(message)


FILE_WATCHER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    FileWatcherTriggerExecutor,
)
