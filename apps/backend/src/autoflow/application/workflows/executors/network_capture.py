"""Approved browser-only network capture migrated from frozen WebRPA.

Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
backend/app/executors/advanced.py#NetworkCaptureExecutor.
"""

from __future__ import annotations

import asyncio
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor
from .type_utils import to_float

_OUT_OF_SCOPE_MODES = frozenset({"system", "proxy"})


def _raise_if_cancelled(context: ExecutionContext) -> None:
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()


async def _wait_for_capture(context: ExecutionContext, duration: float) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, duration)
    while True:
        _raise_if_cancelled(context)
        remaining = deadline - loop.time()
        if remaining <= 0:
            return
        await asyncio.sleep(min(0.1, remaining))


@register_executor
class NetworkCaptureExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "network_capture"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        capture_mode = context.resolve_value(config.get("captureMode", "browser"))
        filter_type = context.resolve_value(config.get("filterType", "all"))
        search_keyword = context.resolve_value(config.get("searchKeyword", ""))
        capture_duration = to_float(config.get("captureDuration", 5), 5, context)
        variable_name = config.get("variableName", "")

        if not variable_name:
            return ModuleResult(success=False, error="请指定存储变量名")
        if capture_mode in _OUT_OF_SCOPE_MODES:
            return ModuleResult(
                success=False,
                error=(
                    "CapabilityUnavailable: 当前 AutoFlow Web 自动化范围"
                    f"不支持 {capture_mode} 抓包模式"
                ),
            )

        try:
            if context.browser is None:
                return ModuleResult(
                    success=False,
                    error="没有打开的页面，浏览器抓包需要先打开网页",
                )
            try:
                page = context.browser.current_page()
            except Exception:  # noqa: BLE001 -- absence is a frozen node result.
                return ModuleResult(
                    success=False,
                    error="没有打开的页面，浏览器抓包需要先打开网页",
                )

            browser_filter = (
                str(filter_type) if filter_type in {"img", "media"} else "all"
            )
            url_pattern = str(search_keyword) if search_keyword else ""
            watch = page.begin_request_watch(
                filter_type=browser_filter,
                url_pattern=url_pattern,
            )
            try:
                await _wait_for_capture(context, capture_duration)
                if watch.overflowed:
                    return ModuleResult(
                        success=False,
                        error="网络抓包数据超过工作流安全限制",
                    )
                requests = watch.captured_requests()
            finally:
                watch.stop()

            urls = list(
                dict.fromkeys(
                    str(request["url"]) for request in requests if request.get("url")
                )
            )
            context.set_variable(str(variable_name), urls)
            return ModuleResult(
                success=True,
                message=(
                    f"浏览器抓包完成，捕获到 {len(urls)} 个URL，"
                    f"已存入变量 {{{variable_name}}}"
                ),
                data={
                    "status": "completed",
                    "mode": "browser",
                    "count": len(urls),
                    "urls": urls[:10],
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 -- provider errors are node results.
            return ModuleResult(success=False, error=f"网络抓包启动失败: {error}")
