from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from typing import Any

from autoflow.domain.workflows.browser import BrowserLocatorPort, BrowserPagePort
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_actions import wait_for_locator

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor
from .type_utils import to_int


def _truthy(value: Any, context: ExecutionContext) -> bool:
    resolved = context.resolve_value(value) if isinstance(value, str) else value
    return resolved in [True, "true", "True", "1", 1]


def _timeout_ms(config: Mapping[str, Any], context: ExecutionContext) -> int | None:
    value = to_int(config.get("timeout", 30), 30, context) * 1000
    return None if value == 0 else value


def _page(context: ExecutionContext) -> BrowserPagePort | None:
    if context.browser is None:
        return None
    try:
        return context.browser.current_page()
    except Exception:  # noqa: BLE001 -- executor serializes browser state as a node error.
        return None


@register_executor
class OpenPageExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "open_page"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        url = context.resolve_value(config.get("url", ""))
        wait_until = context.resolve_value(config.get("waitUntil", "load"))
        open_mode = context.resolve_value(config.get("openMode", "new_tab"))
        if not url:
            return ModuleResult(success=False, error="URL不能为空")
        if context.browser is None:
            return ModuleResult(success=False, error="没有打开的页面")
        try:
            page = (
                context.browser.current_page()
                if open_mode == "current_tab"
                else await context.browser.new_page()
            )
            await page.goto(
                url,
                wait_until=wait_until,
                timeout_ms=float(_timeout_ms(config, context) or 0),
            )
            await page.bring_to_front()
            return ModuleResult(success=True, message=f"已打开网页: {url}")
        except Exception as error:  # noqa: BLE001 -- provider errors are node results.
            return ModuleResult(success=False, error=f"打开网页失败: {error}")


@register_executor
class ClickElementExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "click_element"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        click_type = context.resolve_value(config.get("clickType", "single"))
        wait_for_selector = _truthy(config.get("waitForSelector", True), context)
        follow_new_tab = _truthy(config.get("followNewTab", False), context)
        timeout_ms = _timeout_ms(config, context)
        if not selector:
            return ModuleResult(success=False, error="选择器不能为空")
        page = _page(context)
        if page is None or context.browser is None:
            return ModuleResult(success=False, error="没有打开的页面")
        watch = context.browser.begin_new_page_watch()
        try:
            locator = page.locator(selector)
            if wait_for_selector:
                hints = config.get("selectorHints")
                try:
                    await locator.wait_for(state="attached", timeout_ms=timeout_ms)
                    used_selector = selector
                except Exception:  # noqa: BLE001 -- preserve frozen fallback order.
                    locator, used_selector = await wait_for_locator(
                        page,
                        selector,
                        state="visible",
                        timeout_ms=timeout_ms,
                        hints=hints if isinstance(hints, Mapping) else None,
                    )
                if used_selector != selector:
                    config["selector"] = used_selector
                    selector = used_selector
            options = {"timeout": timeout_ms}
            if click_type == "double":
                await locator.double_click(**options)
            elif click_type == "right":
                await locator.click(button="right", **options)
            else:
                await locator.click(**options)
            followed = await context.browser.settle_new_page_watch(
                watch, follow=follow_new_tab
            )
            watch = None
            suffix = f"，已跟进新标签页：{followed.url}" if followed else ""
            return ModuleResult(success=True, message=f"已点击元素: {selector}{suffix}")
        except Exception as error:  # noqa: BLE001 -- provider errors are node results.
            diagnostic = ""
            try:
                count = await page.locator(selector).count()
                if count == 0:
                    diagnostic = "（诊断：页面上找不到该选择器匹配的元素）"
                elif not await page.locator(selector).is_visible():
                    diagnostic = f"（诊断：找到 {count} 个匹配元素，但首个元素不可见）"
            except Exception:  # noqa: BLE001,S110 -- keep the original provider error.
                pass
            return ModuleResult(
                success=False, error=f"点击元素失败: {error}{diagnostic}"
            )
        finally:
            if watch is not None:
                try:
                    await context.browser.settle_new_page_watch(watch, follow=False)
                except Exception:  # noqa: BLE001,S110 -- frozen cleanup is best effort.
                    pass


@register_executor
class InputTextExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "input_text"

    async def _find_input_element(
        self, page: BrowserPagePort, selector: str
    ) -> tuple[BrowserLocatorPort, str]:
        locator = page.locator(selector)
        tag_name = await locator.evaluate("el => el.tagName.toLowerCase()")
        editable = await locator.evaluate("el => el.isContentEditable")
        if tag_name in ["input", "textarea", "select"] or editable:
            return locator, "direct"
        inner_input = locator.locator("input, textarea")
        if await inner_input.count() > 0:
            return inner_input, "inner"
        inner_editable = locator.locator('[contenteditable="true"]')
        if await inner_editable.count() > 0:
            return inner_editable, "contenteditable"
        return locator, "keyboard"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        text = context.resolve_value(config.get("text", ""))
        clear_before = _truthy(config.get("clearBefore", True), context)
        sequential = _truthy(config.get("typeSequential", False), context)
        timeout_ms = _timeout_ms(config, context)
        if not selector:
            return ModuleResult(success=False, error="选择器不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        try:
            try:
                await page.locator(selector).wait_for(
                    state="visible", timeout_ms=timeout_ms
                )
            except Exception:  # noqa: BLE001 -- frozen source continues to direct lookup.
                hints = config.get("selectorHints")
                if isinstance(hints, Mapping) and hints:
                    try:
                        _, used_selector = await wait_for_locator(
                            page,
                            selector,
                            state="visible",
                            timeout_ms=timeout_ms,
                            hints=hints,
                        )
                        config["selector"] = used_selector
                        selector = used_selector
                    except Exception:  # noqa: BLE001,S110 -- final operation returns error.
                        pass
            locator, input_type = await self._find_input_element(page, selector)
            if input_type == "keyboard":
                await locator.click(timeout=timeout_ms)
                if clear_before:
                    await page.keyboard_press("Control+A")
                    await page.keyboard_press("Backspace")
                await page.keyboard_type(text)
                return ModuleResult(
                    success=True, message=f"已通过键盘输入文本到: {selector}"
                )
            if clear_before:
                await locator.clear()
            if sequential and text:
                await locator.click(timeout=timeout_ms)
                try:
                    await locator.press_sequentially(text, delay_ms=20)
                except AttributeError:
                    await locator.type_text(text, delay_ms=20)
            else:
                await locator.fill(text)
            suffix = f" (在内部{input_type}元素)" if input_type == "inner" else ""
            return ModuleResult(success=True, message=f"已输入文本到: {selector}{suffix}")
        except Exception as error:  # noqa: BLE001 -- provider errors are node results.
            return ModuleResult(success=False, error=f"输入文本失败: {error}")


@register_executor
class GetElementInfoExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "get_element_info"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        attribute = context.resolve_value(config.get("attribute", "text"))
        variable_name = config.get("variableName", "")
        column_name = context.resolve_value(config.get("columnName", ""))
        timeout_ms = _timeout_ms(config, context)
        if not selector:
            return ModuleResult(success=False, error="选择器不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        try:
            locator = page.locator(selector)
            try:
                await locator.wait_for(state="attached", timeout_ms=timeout_ms)
            except Exception:  # noqa: BLE001 -- preserve frozen fallback ordering.
                try:
                    await locator.wait_for(state="visible", timeout_ms=timeout_ms)
                except Exception:  # noqa: BLE001 -- hints are the final fallback.
                    hints = config.get("selectorHints")
                    if isinstance(hints, Mapping) and hints:
                        try:
                            locator, used_selector = await wait_for_locator(
                                page,
                                selector,
                                state="attached",
                                timeout_ms=timeout_ms,
                                hints=hints,
                            )
                            config["selector"] = used_selector
                            selector = used_selector
                        except Exception:  # noqa: BLE001,S110 -- count determines result.
                            pass
            if await locator.count() == 0:
                return ModuleResult(success=False, error=f"未找到元素: {selector}")
            if attribute == "attributes":
                value = await locator.evaluate(
                    "(element) => { const attrs = {}; for (const attr of element.attributes) "
                    "attrs[attr.name] = attr.value; return attrs; }"
                )
            else:
                value = None
                for retry in range(3):
                    if attribute == "text":
                        value = await locator.text_content()
                    elif attribute == "innerHTML":
                        value = await locator.inner_html()
                    elif attribute == "value":
                        value = await locator.input_value()
                    else:
                        value = await locator.get_attribute(attribute)
                    if value is not None and value != "":
                        break
                    if retry < 2:
                        await asyncio.sleep(0.1)
            if isinstance(variable_name, str) and variable_name:
                context.set_variable(variable_name, value)
            if isinstance(column_name, str) and column_name:
                context.add_data_value(column_name, value)
            return ModuleResult(
                success=True, message=f"已获取元素信息: {value}", data=value
            )
        except Exception as error:  # noqa: BLE001 -- provider errors are node results.
            return ModuleResult(success=False, error=f"获取元素信息失败: {error}")


@register_executor
class ScreenshotExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "screenshot"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        screenshot_type = context.resolve_value(config.get("screenshotType", "fullpage"))
        selector = context.resolve_value(config.get("selector", ""))
        save_path = context.resolve_value(config.get("savePath", ""))
        pattern = context.resolve_value(config.get("fileNamePattern", ""))
        variable_name = config.get("variableName", "")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        if context.artifacts is None:
            return ModuleResult(success=False, error="截图产物存储未配置")
        try:
            timestamp = context.clock.now().strftime("%Y%m%d_%H%M%S")
            if pattern:
                file_name = pattern.replace("{时间戳}", timestamp)
                if not file_name.endswith(".png"):
                    file_name += ".png"
            else:
                file_name = f"screenshot_{timestamp}.png"
            if save_path:
                artifact_name = (
                    save_path
                    if save_path.endswith(".png")
                    else os.path.join(save_path, file_name)
                )
            else:
                artifact_name = file_name
            if screenshot_type == "element" and selector:
                locator, _ = await wait_for_locator(
                    page, selector, state="visible", timeout_ms=None
                )
                content = await locator.screenshot()
            else:
                content = await page.screenshot(full_page=screenshot_type != "viewport")
            final_path = await context.artifacts.write_bytes(
                name=artifact_name, content=content, mime_type="image/png"
            )
            if isinstance(variable_name, str) and variable_name:
                context.set_variable(variable_name, final_path)
            return ModuleResult(
                success=True,
                message=f"已保存截图: {final_path}",
                data={"path": final_path},
            )
        except Exception as error:  # noqa: BLE001 -- provider errors are node results.
            return ModuleResult(success=False, error=f"截图失败: {error}")
