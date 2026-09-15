"""Approved frozen WebRPA tab switching executor for AutoFlow.

Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
backend/app/executors/switch_tab.py. Licensed under LICENSE.WebRPA.
"""

from __future__ import annotations

import re
from typing import Any, cast

from autoflow.domain.workflows.browser import BrowserPagePort
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import (
    browser_url_is_sensitive,
    redact_browser_error,
    redact_browser_url,
)

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor


def _mark_manual_switch(context: ExecutionContext) -> None:
    try:
        cast(Any, context)._manual_tab_switch = True
    except (AttributeError, TypeError):
        pass
    if context.browser is not None:
        cast(Any, context.browser)._manual_tab_switch = True


def _current_page(context: ExecutionContext) -> BrowserPagePort | None:
    if context.browser is None:
        return None
    try:
        return context.browser.current_page()
    except Exception:  # noqa: BLE001 -- preserve frozen unknown-current behavior.
        return None


def _remember_selected_page(context: ExecutionContext, page: BrowserPagePort) -> None:
    assert context.browser is not None
    context.browser.select_page(page.id)
    try:
        cast(Any, context).page = page
    except (AttributeError, TypeError):
        pass


@register_executor
class SwitchTabExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "switch_tab"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        _mark_manual_switch(context)
        try:
            if context.browser is None:
                return ModuleResult(
                    success=False,
                    error="浏览器未启动，请先使用'打开网页'模块启动浏览器",
                )
            all_pages = list(context.browser.pages())
            if not all_pages:
                return ModuleResult(success=False, error="没有可用的标签页")

            current_page = _current_page(context)
            try:
                current_index = all_pages.index(current_page) if current_page else -1
            except ValueError:
                current_index = -1

            switch_mode = context.resolve_value(config.get("switchMode", "index"))
            match_mode = context.resolve_value(config.get("matchMode", "exact"))
            save_index_variable = config.get("saveIndexVariable", "")
            save_title_variable = config.get("saveTitleVariable", "")
            save_url_variable = config.get("saveUrlVariable", "")
            target_page: BrowserPagePort | None = None
            target_index = -1

            if switch_mode == "index":
                tab_index = context.resolve_value(config.get("tabIndex", 0))
                try:
                    tab_index = int(tab_index)
                except (ValueError, TypeError):
                    return ModuleResult(
                        success=False, error=f"标签页索引必须是数字: {tab_index}"
                    )
                if tab_index < 0 or tab_index >= len(all_pages):
                    return ModuleResult(
                        success=False,
                        error=(
                            f"标签页索引超出范围: {tab_index}"
                            f"（共有 {len(all_pages)} 个标签页，索引范围: "
                            f"0-{len(all_pages) - 1}）"
                        ),
                    )
                target_index = tab_index
                target_page = all_pages[target_index]
            elif switch_mode == "title":
                tab_title = context.resolve_value(config.get("tabTitle", ""))
                if not tab_title:
                    return ModuleResult(success=False, error="请输入标签页标题")
                for index, page in enumerate(all_pages):
                    if self._match_string(
                        await page.title(), str(tab_title), str(match_mode)
                    ):
                        target_page = page
                        target_index = index
                        break
                if target_page is None:
                    return ModuleResult(
                        success=False,
                        error=f"未找到标题匹配的标签页: {tab_title}",
                    )
            elif switch_mode == "url":
                tab_url = context.resolve_value(config.get("tabUrl", ""))
                if not tab_url:
                    return ModuleResult(success=False, error="请输入标签页URL")
                for index, page in enumerate(all_pages):
                    if self._match_string(page.url, str(tab_url), str(match_mode)):
                        target_page = page
                        target_index = index
                        break
                if target_page is None:
                    safe_tab_url = (
                        redact_browser_url(str(tab_url))
                        if browser_url_is_sensitive(str(tab_url))
                        else str(tab_url)
                    )
                    return ModuleResult(
                        success=False,
                        error=f"未找到URL匹配的标签页: {safe_tab_url}",
                    )
            elif switch_mode == "next":
                target_index = (
                    0 if current_index == -1 else (current_index + 1) % len(all_pages)
                )
                target_page = all_pages[target_index]
            elif switch_mode == "prev":
                target_index = (
                    len(all_pages) - 1
                    if current_index == -1
                    else (current_index - 1) % len(all_pages)
                )
                target_page = all_pages[target_index]
            elif switch_mode == "first":
                target_page = all_pages[0]
                target_index = 0
            elif switch_mode == "last":
                target_page = all_pages[-1]
                target_index = len(all_pages) - 1
            else:
                return ModuleResult(
                    success=False, error=f"不支持的切换模式: {switch_mode}"
                )

            if target_page is None:
                return ModuleResult(success=False, error="未找到目标标签页")

            _remember_selected_page(context, target_page)
            await target_page.bring_to_front()
            page_title = await target_page.title()
            page_url = target_page.url
            if save_index_variable:
                context.set_variable(save_index_variable, target_index)
            if save_title_variable:
                context.set_variable(save_title_variable, page_title)
            if save_url_variable:
                context.set_variable(
                    save_url_variable,
                    page_url,
                    sensitive=(
                        bool(getattr(context, "node_uses_sensitive_values", False))
                        or browser_url_is_sensitive(page_url)
                    ),
                )
            return ModuleResult(
                success=True,
                message=f"已切换到标签页 {target_index}: {page_title}",
                data={
                    "index": target_index,
                    "title": page_title,
                    "url": redact_browser_url(page_url),
                    "total_tabs": len(all_pages),
                },
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            urls = (
                [page.url for page in context.browser.pages()]
                if context.browser
                else []
            )
            return ModuleResult(
                success=False,
                error=f"切换标签页失败: {redact_browser_error(error, *urls)}",
            )

    @staticmethod
    def _match_string(text: str, pattern: str, mode: str) -> bool:
        if mode == "exact":
            return text == pattern
        if mode == "contains":
            return pattern in text
        if mode == "startswith":
            return text.startswith(pattern)
        if mode == "endswith":
            return text.endswith(pattern)
        if mode == "regex":
            try:
                return bool(re.search(pattern, text))
            except re.error:
                return False
        return text == pattern
