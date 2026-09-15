from __future__ import annotations

from typing import Any

from autoflow.domain.workflows.browser import BrowserPagePort
from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor
from .type_utils import to_int


def _page(context: ExecutionContext) -> BrowserPagePort | None:
    if context.browser is None:
        return None
    try:
        return context.browser.current_page()
    except Exception:  # noqa: BLE001 -- browser state becomes the frozen node error.
        return None


@register_executor
class WaitPageLoadExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "wait_page_load"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        wait_until = context.resolve_value(config.get("waitUntil", "load"))
        timeout = to_int(config.get("timeout", 60), 60, context)
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="页面未打开")
        try:
            await page.wait_for_load_state(wait_until, timeout_ms=timeout * 1000)
            return ModuleResult(success=True, message=f"页面已加载完成（{wait_until}）")
        except Exception as error:  # noqa: BLE001 -- provider errors are node results.
            return ModuleResult(success=False, error=f"等待页面加载失败: {error}")


@register_executor
class PageLoadCompleteExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "page_load_complete"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        check_state = context.resolve_value(config.get("checkState", "load"))
        save_to_variable = config.get("saveToVariable", "page_loaded")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="页面未打开")
        try:
            try:
                await page.wait_for_load_state(check_state, timeout_ms=100)
                is_loaded = True
            except Exception:  # noqa: BLE001 -- a timeout is the node's false result.
                is_loaded = False
            context.set_variable(save_to_variable, is_loaded)
            return ModuleResult(
                success=True,
                message=f"页面加载状态: {'已完成' if is_loaded else '未完成'}（{check_state}）",
                data={"loaded": is_loaded},
            )
        except Exception as error:  # noqa: BLE001 -- preserve the frozen error contract.
            return ModuleResult(success=False, error=f"检查页面加载状态失败: {error}")
