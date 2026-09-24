"""WebRPA AI page-analysis executors adapted to managed AutoFlow services.

Source: reference/WebRPA/backend/app/executors/ai_scraper.py@5ccb900e8dcf1530aae66f676d87593c416c7ebb
License: LICENSE.WebRPA
Changes: ScrapeGraphAI's private browser/model stack is replaced by the existing
CloakBrowser session and main-application managed model gateway.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .ai import invoke_managed_chat
from .ai_tasks import _extract_json
from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float

_MAX_HTML_BYTES = 1024 * 1024


class _AIPageExecutor(ModuleExecutor):
    requires_browser = True

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(config.get("modelId"), str) or not config["modelId"].strip():
            return False, "请选择主应用中的模型"
        return True, ""

    async def _html(
        self, config: dict[str, Any], context: ExecutionContext, url: str
    ) -> str:
        if context.browser is None:
            raise RuntimeError("没有打开的页面")
        current = context.browser.current_page()
        temporary = None
        page = current
        if not (url in current.url or current.url in url):
            temporary = await context.browser.new_page()
            page = temporary
            await page.goto(url, wait_until="load", timeout_ms=60_000)
        try:
            wait_seconds = to_float(config.get("waitTime", 3), 3, context)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            if context.cancellation is not None:
                context.cancellation.raise_if_cancelled()
            html = await page.content()
            size = len(html.encode("utf-8"))
            if size > _MAX_HTML_BYTES:
                raise ValueError(
                    f"页面HTML超过 {_MAX_HTML_BYTES} 字节限制（实际 {size} 字节）"
                )
            return html
        finally:
            if temporary is not None:
                await temporary.close()
                try:
                    context.browser.select_page(current.id)
                except Exception:  # noqa: BLE001,S110 - original page may be user-closed.
                    pass


class AISmartScraperExecutor(_AIPageExecutor):
    @property
    def module_type(self) -> str:
        return "ai_smart_scraper"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        url = self.get_text(config.get("url", ""), context)
        prompt = self.get_text(config.get("prompt", ""), context)
        variable_name = config.get("variableName", "")
        if not url:
            return ModuleResult(success=False, error="URL 不能为空")
        if not prompt:
            return ModuleResult(success=False, error="提取提示词不能为空")
        if not isinstance(variable_name, str) or not variable_name:
            return ModuleResult(success=False, error="变量名不能为空")
        try:
            await context.send_progress("正在使用 AI 智能爬虫提取数据...", "info")
            html = await self._html(config, context, url)
            result, _model_id = await invoke_managed_chat(
                config,
                context,
                "你是网页数据提取引擎。严格按用户要求分析所给HTML；要求JSON时只输出JSON，不要解释。",
                f"【提取要求】\n{prompt}\n\n【页面HTML】\n{html}",
                default_temperature=0.2,
            )
        except Exception as error:  # noqa: BLE001 - browser/provider errors become node errors.
            return ModuleResult(success=False, error=f"AI 智能爬虫失败: {error}")
        value = _extract_json(result.content)
        if value is None:
            value = result.content
        context.set_variable(variable_name, value)
        rendered = (
            json.dumps(value, ensure_ascii=False, indent=2)
            if not isinstance(value, str)
            else value
        )
        preview = rendered[:500] + "..." if len(rendered) > 500 else rendered
        return ModuleResult(
            success=True,
            message=f"AI 智能爬虫成功提取数据，已保存到变量 {variable_name}",
            data=preview,
        )


class AIElementSelectorExecutor(_AIPageExecutor):
    @property
    def module_type(self) -> str:
        return "ai_element_selector"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        url = self.get_text(config.get("url", ""), context)
        description = self.get_text(config.get("elementDescription", ""), context)
        variable_name = config.get("variableName", "")
        if not url:
            return ModuleResult(success=False, error="URL 不能为空")
        if not description:
            return ModuleResult(success=False, error="元素描述不能为空")
        if not isinstance(variable_name, str) or not variable_name:
            return ModuleResult(success=False, error="变量名不能为空")
        prompt = (
            f"请从HTML中找到符合描述的元素：{description}\n"
            '只输出JSON对象：{"selector":"尽可能简洁且唯一的CSS选择器",'
            '"description":"元素说明","confidence":0到100}。找不到时selector写NA。'
        )
        try:
            await context.send_progress("正在使用 AI 智能查找元素...", "info")
            html = await self._html(config, context, url)
            result, _model_id = await invoke_managed_chat(
                config,
                context,
                "你是网页元素定位引擎，只根据给定HTML返回可执行的CSS选择器。",
                f"{prompt}\n\n【页面HTML】\n{html}",
                default_temperature=0.1,
            )
        except Exception as error:  # noqa: BLE001 - browser/provider errors become node errors.
            return ModuleResult(success=False, error=f"AI 智能元素选择失败: {error}")
        parsed = _extract_json(result.content)
        if isinstance(parsed, dict) and isinstance(parsed.get("content"), dict):
            parsed = parsed["content"]
        selector = parsed.get("selector") if isinstance(parsed, dict) else result.content
        confidence = parsed.get("confidence", 0) if isinstance(parsed, dict) else 50
        detail = parsed.get("description", "") if isinstance(parsed, dict) else "AI 返回的选择器"
        if not isinstance(selector, str) or not selector or selector == "NA":
            return ModuleResult(
                success=False,
                error=f"AI 未能找到匹配的元素。返回结果: {result.content}",
            )
        context.set_variable(variable_name, selector)
        return ModuleResult(
            success=True,
            message=(
                f"AI 成功找到元素选择器: {selector}\n"
                f"描述: {detail}\n置信度: {confidence}%"
            ),
            data=selector,
        )


AI_SCRAPER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    AISmartScraperExecutor,
    AIElementSelectorExecutor,
)
