"""Browser request monitor executors migrated from frozen WebRPA."""

from __future__ import annotations

# Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
# backend/app/executors/network_monitor.py.
import asyncio
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor
from .type_utils import to_int


def _stop_monitor(context: ExecutionContext, monitor_id: Any) -> None:
    monitor = context.network_monitors.pop(monitor_id, None)
    if monitor is not None:
        monitor.stop()


@register_executor
class NetworkMonitorStartExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "network_monitor_start"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        monitor_id: Any = None
        try:
            monitor_id = context.resolve_value(config.get("monitorId", "default"))
            filter_type = context.resolve_value(config.get("filterType", "api"))
            url_pattern = context.resolve_value(config.get("urlPattern", ""))
            if not monitor_id:
                return ModuleResult(success=False, error="监听器ID不能为空")
            if context.browser is None:
                return ModuleResult(
                    success=False, error="没有打开的页面，请先打开浏览器"
                )
            page = context.browser.current_page()
            _stop_monitor(context, monitor_id)
            monitor = page.begin_request_watch(
                filter_type=str(filter_type), url_pattern=str(url_pattern)
            )
            context.network_monitors[monitor_id] = monitor
            filter_desc = f"类型={filter_type}"
            if url_pattern:
                filter_desc += f"，URL包含='{url_pattern}'"
            return ModuleResult(
                success=True,
                message=(
                    f"网络监听已启动（ID: {monitor_id}，{filter_desc}），"
                    "将持续捕获请求直到停止"
                ),
                data={
                    "monitor_id": monitor_id,
                    "filter_type": filter_type,
                    "url_pattern": url_pattern,
                    "status": "monitoring",
                },
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"启动网络监听失败: {error}")


@register_executor
class NetworkMonitorWaitExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "network_monitor_wait"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        try:
            monitor_id = context.resolve_value(config.get("monitorId", "default"))
            url_pattern = context.resolve_value(config.get("urlPattern", ""))
            timeout = to_int(config.get("timeout", 30), 30, context)
            variable_name = config.get("variableName", "")
            stop_after_capture = config.get("stopAfterCapture", False)
            capture_mode = context.resolve_value(config.get("captureMode", "first"))
            if not monitor_id:
                return ModuleResult(success=False, error="监听器ID不能为空")
            if not url_pattern:
                return ModuleResult(success=False, error="URL匹配模式不能为空")
            monitor = context.network_monitors.get(monitor_id)
            if monitor is None:
                return ModuleResult(
                    success=False,
                    error=(
                        f"监听器 '{monitor_id}' 不存在，"
                        "请先使用'开始网络监听'模块启动监听"
                    ),
                )
            if not monitor.active:
                return ModuleResult(
                    success=False,
                    error=(
                        f"监听器 '{monitor_id}' 未激活，"
                        "请先使用'开始网络监听'模块启动监听"
                    ),
                )

            matched_requests: list[Any] = []
            deadline = asyncio.get_running_loop().time() + timeout
            while asyncio.get_running_loop().time() < deadline:
                if context.cancellation is not None:
                    context.cancellation.raise_if_cancelled()
                if monitor.overflowed:
                    _stop_monitor(context, monitor_id)
                    return ModuleResult(
                        success=False, error="网络监听数据超过工作流安全限制"
                    )
                matched_requests = monitor.matching_requests(str(url_pattern))
                if capture_mode == "first" and matched_requests:
                    matched_requests = matched_requests[:1]
                    break
                await asyncio.sleep(0.1)

            if not matched_requests:
                if stop_after_capture:
                    _stop_monitor(context, monitor_id)
                return ModuleResult(
                    success=False,
                    error=(
                        f"等待超时（{timeout}秒），未捕获到匹配的API请求"
                        f"（URL包含: '{url_pattern}'）"
                    ),
                )

            result_data: Any = (
                matched_requests[0]
                if capture_mode == "first"
                else matched_requests
            )
            if variable_name:
                context.set_variable(str(variable_name), result_data)
            if stop_after_capture:
                _stop_monitor(context, monitor_id)
            count = len(matched_requests)
            mode_desc = "第一个" if capture_mode == "first" else f"全部{count}个"
            return ModuleResult(
                success=True,
                message=(
                    f"成功捕获{mode_desc}匹配的API请求"
                    f"（URL包含: '{url_pattern}'）"
                    + (f"，已存入变量 {{{variable_name}}}" if variable_name else "")
                ),
                data={
                    "monitor_id": monitor_id,
                    "url_pattern": url_pattern,
                    "capture_mode": capture_mode,
                    "count": count,
                    "requests": matched_requests[:5],
                    "stopped": stop_after_capture,
                },
            )
        except asyncio.CancelledError:
            if monitor_id is not None:
                _stop_monitor(context, monitor_id)
            raise
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"等待API请求失败: {error}")


@register_executor
class NetworkMonitorStopExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "network_monitor_stop"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        try:
            monitor_id = context.resolve_value(config.get("monitorId", "default"))
            variable_name = config.get("variableName", "")
            if not monitor_id:
                return ModuleResult(success=False, error="监听器ID不能为空")
            monitor = context.network_monitors.get(monitor_id)
            if monitor is None:
                return ModuleResult(
                    success=False, error=f"监听器 '{monitor_id}' 不存在"
                )
            if monitor.overflowed:
                _stop_monitor(context, monitor_id)
                return ModuleResult(
                    success=False, error="网络监听数据超过工作流安全限制"
                )
            captured_requests = monitor.captured_requests()
            _stop_monitor(context, monitor_id)
            if variable_name:
                context.set_variable(str(variable_name), captured_requests)
            return ModuleResult(
                success=True,
                message=(
                    f"网络监听已停止（ID: {monitor_id}），"
                    f"共捕获 {len(captured_requests)} 个请求"
                    + (f"，已存入变量 {{{variable_name}}}" if variable_name else "")
                ),
                data={
                    "monitor_id": monitor_id,
                    "count": len(captured_requests),
                    "requests": captured_requests[:10],
                },
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"停止网络监听失败: {error}")
