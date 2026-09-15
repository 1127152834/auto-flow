"""Approved WebRPA basic browser executors with AutoFlow session adaptation.

Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
backend/app/executors/basic.py. Licensed under LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Protocol, cast

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_actions import fallback_selectors
from autoflow.providers.browser.workflow_session import (
    format_selector,
    redact_browser_error,
    redact_browser_url,
)

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor
from .type_utils import to_float, to_int


class _Locator(Protocol):
    async def wait_for(self, **options: Any) -> None: ...

    async def hover(self, **options: Any) -> None: ...


class _ElementHandle(Protocol):
    async def content_frame(self) -> _Page | None: ...


class _Page(Protocol):
    id: str
    url: str
    closed: bool
    frames: list[_Page]
    main_frame: _Page

    async def title(self) -> str: ...

    def locator(self, selector: str) -> _Locator: ...

    async def close(self) -> None: ...

    async def reload(self, **options: Any) -> object | None: ...

    async def go_back(self, **options: Any) -> object | None: ...

    async def go_forward(self, **options: Any) -> object | None: ...

    async def goto(self, url: str, **options: Any) -> object | None: ...

    async def evaluate(self, expression: str) -> Any: ...

    async def wait_for_load_state(self, state: str, **options: Any) -> None: ...

    def frame(self, *, name: str) -> _Page | None: ...

    async def wait_for_selector(
        self, selector: str, **options: Any
    ) -> _ElementHandle | None: ...

    async def query_selector_all(self, selector: str) -> list[_ElementHandle]: ...

    def on(self, event: str, callback: Any) -> None: ...

    def remove_listener(self, event: str, callback: Any) -> None: ...


def _session(context: ExecutionContext) -> Any | None:
    return getattr(context, "browser", None)


def _page(context: ExecutionContext) -> _Page | None:
    session = _session(context)
    if session is None:
        return None
    try:
        active_page = getattr(session, "active_page", None)
        return cast(
            _Page,
            active_page() if active_page is not None else session.current_page(),
        )
    except Exception:  # noqa: BLE001 -- browser state becomes a node result.
        return None


def _pages(context: ExecutionContext) -> list[_Page]:
    session = _session(context)
    if session is None:
        return []
    try:
        return list(cast(tuple[_Page, ...], session.pages()))
    except Exception:  # noqa: BLE001 -- browser state becomes a node result.
        return []


def _select_page(context: ExecutionContext, page: _Page) -> None:
    session = _session(context)
    if session is not None:
        session.select_page(page.id)
    try:
        cast(Any, context).page = page
    except (AttributeError, TypeError):
        pass


def _frame_state(context: ExecutionContext) -> dict[str, Any]:
    session = _session(context)
    if session is None:
        return {
            "in_iframe": False,
            "main_page": None,
            "current_frame": None,
            "locator": None,
        }
    state = getattr(session, "_autoflow_frame_state", None)
    if not isinstance(state, dict):
        state = {
            "in_iframe": False,
            "main_page": None,
            "current_frame": None,
            "locator": None,
        }
        session._autoflow_frame_state = state
    return state


def _active_page(context: ExecutionContext) -> _Page | None:
    session = _session(context)
    active_page = getattr(session, "active_page", None)
    if active_page is not None:
        try:
            return cast(_Page, active_page())
        except Exception:  # noqa: BLE001 -- browser state becomes a node result.
            return None
    state = _frame_state(context)
    if state["in_iframe"] and state["current_frame"] is not None:
        return cast(_Page, state["current_frame"])
    return _page(context)


async def _wait_for_element(
    page: _Page,
    selector: str,
    *,
    state: str,
    timeout: int | None,
) -> _Locator:
    locator = page.locator(format_selector(selector))
    options: dict[str, Any] = {"state": state}
    if timeout is not None:
        options["timeout_ms"] = timeout
    await locator.wait_for(**options)
    return locator


async def _smart_wait(
    page: _Page,
    selector: str,
    *,
    hints: Any,
    state: str,
    timeout: int | None,
    config: dict[str, Any],
) -> _Locator:
    try:
        return await _wait_for_element(page, selector, state=state, timeout=timeout)
    except Exception:
        for fallback in fallback_selectors(hints if isinstance(hints, dict) else None):
            try:
                locator = await _wait_for_element(
                    page, fallback, state=state, timeout=3000
                )
                config["selector"] = fallback
                return locator
            except Exception:  # noqa: BLE001,S112 -- try the next frozen candidate.
                continue
        raise


@register_executor
class ClosePageExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "close_page"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        try:
            page = _page(context)
            if page is None:
                return ModuleResult(success=True, message="没有需要关闭的页面")
            await page.close()
            return ModuleResult(success=True, message="已关闭页面")
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"关闭页面失败: {error}")


class _NavigationExecutor(ModuleExecutor):
    requires_browser = True
    operation = ""
    success_text = ""
    no_history_text = ""
    failure_text = ""

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        wait_until = context.resolve_value(config.get("waitUntil", "load"))
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        try:
            response = await getattr(page, self.operation)(wait_until=wait_until)
            if self.no_history_text and response is None:
                return ModuleResult(success=True, message=self.no_history_text)
            return ModuleResult(
                success=True,
                message=(
                    self.success_text
                    if self.operation == "reload"
                    else f"{self.success_text}: {redact_browser_url(page.url)}"
                ),
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(
                success=False,
                error=(
                    f"{self.failure_text}: "
                    f"{redact_browser_error(error, page.url)}"
                ),
            )


@register_executor
class RefreshPageExecutor(_NavigationExecutor):
    operation = "reload"
    success_text = "已刷新页面"
    failure_text = "刷新页面失败"

    @property
    def module_type(self) -> str:
        return "refresh_page"


@register_executor
class GoBackExecutor(_NavigationExecutor):
    operation = "go_back"
    success_text = "已返回上一页"
    no_history_text = "已返回上一页（无历史记录）"
    failure_text = "返回上一页失败"

    @property
    def module_type(self) -> str:
        return "go_back"


@register_executor
class GoForwardExecutor(_NavigationExecutor):
    operation = "go_forward"
    success_text = "已前进下一页"
    no_history_text = "已前进下一页（无前进记录）"
    failure_text = "前进下一页失败"

    @property
    def module_type(self) -> str:
        return "go_forward"


@register_executor
class HoverElementExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "hover_element"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        hover_duration = to_float(config.get("hoverDuration", 0.5), 0.5, context)
        force_raw = config.get("force", False)
        if isinstance(force_raw, str):
            force_raw = context.resolve_value(force_raw)
        force = force_raw in [True, "true", "True", "1", 1]
        timeout_ms = to_int(config.get("timeout", 30), 30, context) * 1000
        if not selector:
            return ModuleResult(success=False, error="选择器不能为空")
        page = _active_page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        try:
            timeout = None if timeout_ms == 0 else timeout_ms
            try:
                locator = await _wait_for_element(
                    page, str(selector), state="attached", timeout=timeout
                )
            except Exception:  # noqa: BLE001 -- preserve frozen fallback.
                hints = config.get("selectorHints")
                if hints:
                    locator = await _smart_wait(
                        page,
                        str(selector),
                        hints=hints,
                        state="visible",
                        timeout=timeout,
                        config=config,
                    )
                else:
                    locator = await _wait_for_element(
                        page, str(selector), state="visible", timeout=timeout
                    )
            await locator.hover(force=force, timeout_ms=timeout)
            if hover_duration > 0:
                await asyncio.sleep(hover_duration)
            return ModuleResult(success=True, message=f"已悬停到元素: {selector}")
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"悬停元素失败: {error}")


@register_executor
class WaitElementExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "wait_element"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        wait_condition = context.resolve_value(config.get("waitCondition", "visible"))
        wait_timeout = to_int(config.get("waitTimeout", 30), 30, context) * 1000
        if not selector:
            return ModuleResult(success=False, error="选择器不能为空")
        page = _active_page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        state = {
            "visible": "visible",
            "hidden": "hidden",
            "attached": "attached",
            "detached": "detached",
        }.get(wait_condition, "visible")
        timeout = None if wait_timeout == 0 else wait_timeout
        try:
            hints = config.get("selectorHints")
            if state in {"visible", "attached"} and hints:
                await _smart_wait(
                    page,
                    str(selector),
                    hints=hints,
                    state=state,
                    timeout=timeout,
                    config=config,
                )
            else:
                await _wait_for_element(
                    page, str(selector), state=state, timeout=timeout
                )
            label = {
                "visible": "可见",
                "hidden": "隐藏/消失",
                "attached": "存在于DOM",
                "detached": "从DOM移除",
            }.get(wait_condition, wait_condition)
            return ModuleResult(
                success=True,
                message=f"元素已{label}: {selector}",
                data={"selector": selector, "condition": wait_condition},
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            error_message = str(error)
            if "Timeout" in error_message:
                return ModuleResult(
                    success=False,
                    error=(
                        f"等待超时 ({wait_timeout}ms): 元素 {selector} "
                        f"未满足条件 '{wait_condition}'"
                    ),
                )
            return ModuleResult(success=False, error=f"等待元素失败: {error_message}")


@register_executor
class HandleDialogExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "handle_dialog"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        dialog_action = context.resolve_value(config.get("dialogAction", "accept"))
        prompt_text = context.resolve_value(config.get("promptText", ""))
        save_message = config.get("saveMessage", "")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        dialog_info: dict[str, Any] = {"handled": False, "message": "", "type": ""}

        async def handle_dialog(dialog: Any) -> None:
            dialog_info.update(handled=True, message=dialog.message, type=dialog.type)
            if dialog_action == "accept":
                if dialog.type == "prompt" and prompt_text:
                    await dialog.accept(prompt_text)
                else:
                    await dialog.accept()
            else:
                await dialog.dismiss()

        try:
            page.on("dialog", handle_dialog)
            try:
                await asyncio.sleep(0.5)
            finally:
                page.remove_listener("dialog", handle_dialog)
            if save_message and dialog_info["message"]:
                context.set_variable(save_message, dialog_info["message"])
            if dialog_info["handled"]:
                action_text = "确认" if dialog_action == "accept" else "取消"
                return ModuleResult(
                    success=True,
                    message=(
                        f"已{action_text}{dialog_info['type']}弹窗: "
                        f"{dialog_info['message'][:50]}"
                    ),
                    data=dialog_info,
                )
            return ModuleResult(
                success=True,
                message="弹窗处理器已设置，等待弹窗出现",
                data={"waiting": True},
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"处理弹窗失败: {error}")


@register_executor
class InjectJavaScriptExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "inject_javascript"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        javascript_code = context.resolve_value(config.get("javascriptCode", ""))
        save_result = config.get("saveResult", "")
        inject_mode = context.resolve_value(config.get("injectMode", "current"))
        target_url = context.resolve_value(config.get("targetUrl", ""))
        target_index_value = context.resolve_value(config.get("targetIndex", "0"))
        try:
            target_index = int(target_index_value) if target_index_value else 0
        except ValueError:
            target_index = 0
        if not javascript_code:
            return ModuleResult(success=False, error="JavaScript代码不能为空")
        if _session(context) is None:
            return ModuleResult(success=False, error="没有打开的浏览器")

        workflow_variables: dict[str, Any] = {}
        sensitive_variables: set[str] = getattr(
            context, "sensitive_variables", set()
        )
        for key, value in context.variables.items():
            # AutoFlow adaptation: secret values may be used by browser actions but
            # must never be copied into a page's JavaScript context.
            if key in sensitive_variables:
                continue
            try:
                json.dumps(value)
                workflow_variables[key] = value
            except (TypeError, ValueError):
                workflow_variables[key] = str(value)
        variables_json = json.dumps(workflow_variables, ensure_ascii=False)

        try:
            all_pages = _pages(context)
            if not all_pages:
                return ModuleResult(success=False, error="没有打开的页面")
            target_pages: list[_Page] = []
            if inject_mode == "current":
                current = _active_page(context)
                if current is None:
                    return ModuleResult(success=False, error="没有当前活动页面")
                target_pages = [current]
            elif inject_mode == "all":
                target_pages = all_pages
            elif inject_mode == "url_match":
                if not target_url:
                    return ModuleResult(
                        success=False, error="URL匹配模式需要指定目标URL"
                    )
                try:
                    regex = re.compile(str(target_url).replace("*", ".*"))
                except re.error:
                    return ModuleResult(
                        success=False, error=f"无效的URL匹配模式: {target_url}"
                    )
                target_pages = [page for page in all_pages if regex.search(page.url)]
                if not target_pages:
                    return ModuleResult(
                        success=False, error=f"没有找到匹配URL的页面: {target_url}"
                    )
            elif inject_mode == "index":
                if target_index < 0 or target_index >= len(all_pages):
                    return ModuleResult(
                        success=False,
                        error=(
                            f"标签页索引超出范围: {target_index}"
                            f"（共有 {len(all_pages)} 个标签页）"
                        ),
                    )
                target_pages = [all_pages[target_index]]
            else:
                return ModuleResult(
                    success=False, error=f"不支持的注入模式: {inject_mode}"
                )

            wrapped_code = f"""
(async () => {{
    // 注入工作流变量
    const vars = {variables_json};

    // 用户代码
    {javascript_code}
}})()
"""
            results: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            for page in target_pages:
                try:
                    value = await page.evaluate(wrapped_code)
                    results.append(
                        {
                            "index": all_pages.index(page),
                            "url": redact_browser_url(page.url),
                            "title": await page.title(),
                            "result": value,
                            "success": True,
                        }
                    )
                except Exception as error:  # noqa: BLE001 -- per-page result.
                    errors.append(
                        {
                            "index": all_pages.index(page),
                            "url": redact_browser_url(page.url),
                            "error": redact_browser_error(error, page.url),
                        }
                    )
            if save_result:
                if inject_mode in {"current", "index"}:
                    if results:
                        context.set_variable(save_result, results[0]["result"])
                else:
                    context.set_variable(save_result, results)

            success_count = len(results)
            error_count = len(errors)
            total_count = success_count + error_count
            if error_count == 0:
                if inject_mode in {"current", "index"}:
                    result_text = (
                        str(results[0]["result"])
                        if results[0]["result"] is not None
                        else "undefined"
                    )
                    if len(result_text) > 100:
                        result_text = result_text[:100] + "..."
                    message = f"JavaScript执行成功，返回值: {result_text}"
                else:
                    message = f"JavaScript执行成功，已注入到 {success_count} 个标签页"
                return ModuleResult(
                    success=True,
                    message=message,
                    data={
                        "mode": inject_mode,
                        "total": total_count,
                        "success": success_count,
                        "results": results,
                    },
                )
            if success_count == 0:
                details = "\n".join(
                    f"标签页 {item['index']} ({item['url']}): {item['error']}"
                    for item in errors
                )
                return ModuleResult(
                    success=False,
                    error=(
                        f"JavaScript执行失败（{error_count}/{total_count}）:\n{details}"
                    ),
                )
            details = "\n".join(
                f"标签页 {item['index']}: {item['error']}" for item in errors
            )
            return ModuleResult(
                success=True,
                message=(
                    f"JavaScript部分执行成功（{success_count}/{total_count}），"
                    f"{error_count} 个失败"
                ),
                data={
                    "mode": inject_mode,
                    "total": total_count,
                    "success": success_count,
                    "error": error_count,
                    "results": results,
                    "errors": errors,
                },
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"JavaScript执行失败: {error}")


@register_executor
class SwitchIframeExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "switch_iframe"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        locate_by = context.resolve_value(config.get("locateBy", "index"))
        iframe_index = to_int(config.get("iframeIndex", 0), 0, context)
        iframe_name = context.resolve_value(config.get("iframeName", ""))
        iframe_selector = context.resolve_value(config.get("iframeSelector", ""))
        page = _active_page(context)
        if page is None:
            return ModuleResult(success=False, error="页面未初始化，请先打开网页")
        try:
            frame: _Page | None = None
            if locate_by == "index":
                main_frame_id = page.main_frame.id
                child_frames = [
                    item for item in page.frames if item.id != main_frame_id
                ]
                if iframe_index < 0 or iframe_index >= len(child_frames):
                    return ModuleResult(
                        success=False,
                        error=(
                            f"iframe索引超出范围: {iframe_index}"
                            f"（共有 {len(child_frames)} 个iframe）"
                        ),
                    )
                frame = child_frames[iframe_index]
            elif locate_by == "name":
                if not iframe_name:
                    return ModuleResult(success=False, error="请指定iframe的name或id")
                frame = page.frame(name=str(iframe_name))
                if frame is None:
                    try:
                        element = await page.wait_for_selector(
                            f'iframe[id="{iframe_name}"]', timeout_ms=5000
                        )
                        if element is not None:
                            frame = await element.content_frame()
                    except Exception:  # noqa: BLE001,S110 -- frozen name fallback.
                        pass
                if frame is None:
                    return ModuleResult(
                        success=False,
                        error=f"未找到name或id为 '{iframe_name}' 的iframe",
                    )
            elif locate_by == "selector":
                if not iframe_selector:
                    return ModuleResult(success=False, error="请指定iframe的CSS选择器")
                try:
                    element = await page.wait_for_selector(
                        str(iframe_selector), timeout_ms=10000
                    )
                    if element is not None:
                        frame = await element.content_frame()
                    if frame is None:
                        return ModuleResult(
                            success=False,
                            error=f"选择器 '{iframe_selector}' 找到的元素不是iframe",
                        )
                except Exception as error:  # noqa: BLE001 -- selector result.
                    return ModuleResult(
                        success=False,
                        error=f"未找到iframe: {iframe_selector}，错误: {error}",
                    )
            else:
                return ModuleResult(
                    success=False, error=f"不支持的定位方式: {locate_by}"
                )

            assert frame is not None
            try:
                await frame.wait_for_load_state("domcontentloaded", timeout_ms=10000)
                if frame.url == "about:blank" or not frame.url:
                    await asyncio.sleep(2)
                    try:
                        await frame.wait_for_selector("body", timeout_ms=3000)
                        await frame.evaluate("document.body.innerHTML")
                        nested = await frame.query_selector_all("iframe")
                        if len(nested) == 1:
                            nested_frame = await nested[0].content_frame()
                            if nested_frame is not None:
                                try:
                                    await nested_frame.wait_for_load_state(
                                        "domcontentloaded", timeout_ms=5000
                                    )
                                except Exception:  # noqa: BLE001,S110 -- advisory.
                                    pass
                                frame = nested_frame
                    except Exception:  # noqa: BLE001,S110 -- frozen fallback.
                        pass
            except Exception:  # noqa: BLE001,S110 -- frozen load is advisory.
                pass

            state = _frame_state(context)
            if not state["in_iframe"]:
                state["main_page"] = page
            state.update(
                in_iframe=True,
                current_frame=frame,
                locator={
                    "type": locate_by,
                    "value": {
                        "name": iframe_name,
                        "index": iframe_index,
                        "selector": iframe_selector,
                    }[str(locate_by)],
                },
            )
            session = _session(context)
            select_frame = getattr(session, "select_frame", None)
            if select_frame is not None:
                select_frame(frame)
            frame_url = redact_browser_url(frame.url) if frame.url else "(about:blank)"
            return ModuleResult(
                success=True,
                message=f"已切换到iframe（{locate_by}），URL: {frame_url}",
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"切换iframe失败: {error}")


@register_executor
class SwitchToMainExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "switch_to_main"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        if _session(context) is None:
            return ModuleResult(success=False, error="浏览器未初始化")
        try:
            state = _frame_state(context)
            if not state["in_iframe"]:
                page = _page(context)
                if page is None:
                    return ModuleResult(success=False, error="没有活动页面")
                return ModuleResult(
                    success=True,
                    message=f"当前已在主页面，URL: {redact_browser_url(page.url)}",
                )
            main_page = cast(_Page | None, state["main_page"])
            state.update(
                in_iframe=False, main_page=None, current_frame=None, locator=None
            )
            session = _session(context)
            clear_frame = getattr(session, "clear_frame", None)
            if clear_frame is not None:
                clear_frame()
            if main_page is None:
                page = _page(context)
                if page is None:
                    return ModuleResult(success=False, error="无法找到主页面")
            else:
                _select_page(context, main_page)
                page = main_page
            return ModuleResult(
                success=True,
                message=f"已切换回主页面，URL: {redact_browser_url(page.url)}",
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"切换回主页面失败: {error}")


@register_executor
class UseOpenedPageExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "use_opened_page"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        action = context.resolve_value(config.get("action", "use"))
        url = context.resolve_value(config.get("url", ""))
        wait_until = context.resolve_value(config.get("waitUntil", "load"))
        page_identifier = context.resolve_value(config.get("pageIdentifier", ""))
        match_mode = context.resolve_value(config.get("matchMode", "title"))
        try:
            all_pages = _pages(context)
            page = _page(context)
            if page is None:
                if not all_pages:
                    return ModuleResult(
                        success=False,
                        error="浏览器未启动，请先点击'打开浏览器'按钮",
                    )
                real_pages = [
                    item
                    for item in all_pages
                    if item.url not in ("about:blank", "chrome://newtab/", "")
                ]
                page = real_pages[-1] if real_pages else all_pages[-1]
                _select_page(context, page)

            if page_identifier:
                needle = str(page_identifier).lower()
                matched: _Page | None = None
                for candidate in all_pages:
                    try:
                        haystack = (
                            candidate.url
                            if match_mode == "url"
                            else await candidate.title()
                        )
                        if needle in (haystack or "").lower():
                            matched = candidate
                            break
                    except Exception:  # noqa: BLE001,S112 -- skip inaccessible tabs.
                        continue
                if matched is None:
                    return ModuleResult(
                        success=False,
                        error=f"未找到匹配 '{page_identifier}' 的已打开页面",
                    )
                _select_page(context, matched)
                page = matched

            if action == "use":
                return ModuleResult(
                    success=True,
                    message=f"已使用打开的网页: {redact_browser_url(page.url)}",
                    data={
                        "url": redact_browser_url(page.url),
                        "title": await page.title(),
                    },
                )
            if action == "navigate":
                if not url:
                    return ModuleResult(success=False, error="导航URL不能为空")
                response = await page.goto(
                    str(url), wait_until=wait_until, timeout_ms=60000
                )
                if response:
                    return ModuleResult(
                        success=True,
                        message=f"已导航到: {redact_browser_url(page.url)}",
                        data={
                            "url": redact_browser_url(page.url),
                            "title": await page.title(),
                        },
                    )
                return ModuleResult(
                    success=False,
                    error=f"导航失败: {redact_browser_url(str(url))}",
                )
            if action == "refresh":
                response = await page.reload(wait_until=wait_until, timeout_ms=60000)
                if response:
                    return ModuleResult(
                        success=True,
                        message=f"已刷新页面: {redact_browser_url(page.url)}",
                        data={
                            "url": redact_browser_url(page.url),
                            "title": await page.title(),
                        },
                    )
                return ModuleResult(success=False, error="刷新页面失败")
            return ModuleResult(success=False, error=f"未知的操作类型: {action}")
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            known_urls = [str(url), *[page.url for page in _pages(context)]]
            return ModuleResult(
                success=False,
                error=(
                    "操作已打开的网页失败: "
                    f"{redact_browser_error(error, *known_urls)}"
                ),
            )


WEB_BASIC_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    UseOpenedPageExecutor,
    ClosePageExecutor,
    RefreshPageExecutor,
    GoBackExecutor,
    GoForwardExecutor,
    SwitchIframeExecutor,
    SwitchToMainExecutor,
    HoverElementExecutor,
    HandleDialogExecutor,
    InjectJavaScriptExecutor,
    WaitElementExecutor,
)
