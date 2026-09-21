"""Timing and probability executors migrated from WebRPA@5ccb900e.

Sources: backend/app/executors/control.py and probability.py.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_int


class ScheduledTaskExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "scheduled_task"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}秒"
        if seconds < 3600:
            minutes, secs = divmod(seconds, 60)
            return f"{minutes}分{secs}秒" if secs else f"{minutes}分钟"
        hours, minutes = divmod(seconds, 3600)
        minutes //= 60
        return f"{hours}小时{minutes}分钟" if minutes else f"{hours}小时"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        schedule_type = context.resolve_value(config.get("scheduleType", "datetime"))
        try:
            if schedule_type == "datetime":
                target_date = context.resolve_value(config.get("targetDate", ""))
                target_time = context.resolve_value(config.get("targetTime", ""))
                if not target_date or not target_time:
                    return ModuleResult(success=False, error="请设置执行日期和时间")
                target_text = f"{target_date} {target_time}"
                target = _parse_datetime(target_text)
                if target is None:
                    return ModuleResult(
                        success=False,
                        error=(
                            f"日期时间格式错误: {target_text}，请使用 "
                            "YYYY-MM-DD HH:MM 或 YYYY-MM-DD HH:MM:SS 格式"
                        ),
                    )
                now = context.clock.now().astimezone().replace(tzinfo=None)
                if target <= now:
                    return ModuleResult(
                        success=True, message=f"目标时间 {target_text} 已过，立即执行"
                    )
                wait_seconds = (target - now).total_seconds()
                await _progress(
                    context,
                    f"⏰ 定时任务已设置，等待到 {target_text}",
                    "⏰ 定时任务已设置",
                    f"🕐 目标时间: {target_text}",
                    f"⏳ 等待时长: {self._format_duration(wait_seconds)}",
                )
                await asyncio.sleep(wait_seconds)
                return ModuleResult(
                    success=True,
                    message=f"已到达指定时间 {target_text}，开始执行",
                )
            if schedule_type == "delay":
                total_seconds = (
                    to_int(config.get("delayHours", 0), 0, context) * 3600
                    + to_int(config.get("delayMinutes", 0), 0, context) * 60
                    + to_int(config.get("delaySeconds", 0), 0, context)
                )
                if total_seconds <= 0:
                    return ModuleResult(
                        success=False,
                        error="延迟时间必须大于0，请设置延迟小时、分钟或秒数",
                    )
                duration = self._format_duration(total_seconds)
                await _progress(
                    context,
                    f"⏰ 延迟 {duration} 后执行",
                    "⏰ 延迟任务已设置",
                    f"⏳ 延迟时长: {duration}",
                )
                await asyncio.sleep(total_seconds)
                return ModuleResult(
                    success=True, message=f"延迟 {duration} 完成，开始执行"
                )
            return ModuleResult(success=False, error=f"未知的定时类型: {schedule_type}")
        except Exception as error:  # noqa: BLE001 - source returns scheduler errors.
            return ModuleResult(success=False, error=f"定时执行失败: {error}")


class ProbabilityTriggerExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "probability_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        del context
        try:
            probability = float(config.get("probability", 50))
            if not 0 <= probability <= 100:
                return ModuleResult(
                    success=False,
                    message="概率值必须在0-100之间",
                    error="概率值无效",
                )
            random_value = random.uniform(0, 100)
            branch = "path1" if random_value < probability else "path2"
            selected_probability = (
                probability if branch == "path1" else 100 - probability
            )
            return ModuleResult(
                success=True,
                message=(
                    f"触发{branch.replace('path', '路径')}（概率: {selected_probability}%, "
                    f"随机值: {random_value:.2f}）"
                ),
                branch=branch,
                data={
                    "probability": probability,
                    "random_value": random_value,
                    "selected_path": branch,
                },
            )
        except Exception as error:  # noqa: BLE001 - preserve source error result.
            return ModuleResult(
                success=False,
                message=f"概率触发器执行失败: {error}",
                error=str(error),
            )


def _parse_datetime(value: str) -> datetime | None:
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, pattern)  # noqa: DTZ007 - local schedule.
        except ValueError:
            pass
    return None


async def _progress(
    context: ExecutionContext, progress: str, *log_messages: str
) -> None:
    for message in log_messages:
        context.log_records.append(
            {
                "timestamp": context.clock.now().isoformat(),
                "level": "info",
                "message": message,
                "duration": 0,
                "nodeId": context.current_node_id or "",
            }
        )
    await context.send_progress(progress)


TIMING_PROBABILITY_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    ScheduledTaskExecutor,
    ProbabilityTriggerExecutor,
)
