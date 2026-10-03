"""Web state primitives: cookies, page storage and request interception (remediation M2 R2-28).

All three change only the local browser state; nothing is sent outside the run,
so they are side-effect free for retry purposes (R2-10). Cookie and storage
values read by these nodes are treated as sensitive outputs.
"""

from __future__ import annotations

import json
from typing import Any, cast

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor

_STORAGE_AREAS = {"local": "localStorage", "session": "sessionStorage"}


def _text(config: dict[str, Any], key: str, context: ExecutionContext, default: str = "") -> str:
    value = context.resolve_value(config.get(key, default))
    return "" if value is None else str(value).strip()


def _session(context: ExecutionContext) -> Any:
    return context.browser


def _page(context: ExecutionContext) -> Any:
    browser = context.browser
    if browser is None:
        return None
    try:
        return cast(Any, browser).active_page()
    except Exception:  # noqa: BLE001 -- no page is a normal node failure below.
        return None


def _store(context: ExecutionContext, name: str, value: Any) -> None:
    if name:
        context.set_variable(name, value, sensitive=True)


@register_executor
class WebCookieExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "web_cookie"

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        session = _session(context)
        if session is None:
            return ModuleResult(False, error="没有打开的浏览器")
        operation = str(config.get("operation") or "get")
        name = _text(config, "name", context)
        page = _page(context)
        url = _text(config, "url", context) or (page.url if page is not None else "")
        try:
            if operation == "get":
                cookies = await session.cookies([url] if url.startswith("http") else None)
                found = [cookie for cookie in cookies if not name or cookie.get("name") == name]
                value: Any = (found[0].get("value") if found else None) if name else found
                _store(context, _text(config, "variableName", context), value)
                return ModuleResult(True, message=f"已读取 {len(found)} 个 Cookie", data={"count": len(found)})
            if operation == "set":
                if not name:
                    return ModuleResult(False, error="Cookie 名称不能为空")
                cookie: dict[str, Any] = {"name": name, "value": _text(config, "value", context)}
                domain = _text(config, "domain", context)
                if domain:
                    cookie.update(domain=domain, path=_text(config, "path", context) or "/")
                elif url.startswith("http"):
                    cookie["url"] = url
                else:
                    return ModuleResult(False, error="写入 Cookie 需要网址或域名")
                await session.add_cookies([cookie])
                return ModuleResult(True, message=f"已写入 Cookie {name}")
            if operation in {"delete", "clear"}:
                if operation == "delete" and not name:
                    return ModuleResult(False, error="删除 Cookie 需要名称")
                await session.clear_cookies(name=name or None, domain=_text(config, "domain", context) or None)
                return ModuleResult(True, message="已删除 Cookie" if name else "已清空 Cookie")
            return ModuleResult(False, error=f"不支持的 Cookie 操作: {operation}")
        except Exception as error:  # noqa: BLE001 -- the reason becomes the node error.
            return ModuleResult(False, error=f"Cookie 操作失败: {error}")


@register_executor
class WebStorageExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "web_storage"

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        page = _page(context)
        if page is None:
            return ModuleResult(False, error="没有打开的页面")
        area = _STORAGE_AREAS.get(str(config.get("area") or "local"))
        if area is None:
            return ModuleResult(False, error="存储类型只能是本地存储或会话存储")
        operation = str(config.get("operation") or "get")
        key = _text(config, "key", context)
        if operation in {"get", "set", "remove"} and not key:
            return ModuleResult(False, error="存储键不能为空")
        scripts = {
            "get": f"window.{area}.getItem({json.dumps(key)})",
            "getAll": f"Object.fromEntries(Object.entries(window.{area}))",
            "set": f"(window.{area}.setItem({json.dumps(key)}, {json.dumps(_text(config, 'value', context))}), true)",
            "remove": f"(window.{area}.removeItem({json.dumps(key)}), true)",
            "clear": f"(window.{area}.clear(), true)",
        }
        script = scripts.get(operation)
        if script is None:
            return ModuleResult(False, error=f"不支持的存储操作: {operation}")
        try:
            value = await page.evaluate(script)
        except Exception as error:  # noqa: BLE001 -- e.g. storage unavailable on an opaque origin.
            return ModuleResult(False, error=f"页面存储操作失败: {error}")
        if operation in {"get", "getAll"}:
            _store(context, _text(config, "variableName", context), value)
        return ModuleResult(True, message="页面存储操作完成")


@register_executor
class WebInterceptExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "web_intercept"

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        session = _session(context)
        if session is None:
            return ModuleResult(False, error="没有打开的浏览器")
        operation = str(config.get("operation") or "start")
        pattern = _text(config, "urlPattern", context)
        if not pattern:
            return ModuleResult(False, error="需要填写要拦截的网址规则")
        try:
            if operation == "stop":
                await session.stop_intercept(pattern)
                return ModuleResult(True, message=f"已停止拦截 {pattern}")
            action = str(config.get("action") or "block")
            if action == "mock":
                status = int(context.resolve_value(config.get("mockStatus", 200)) or 200)
                rule: dict[str, Any] = {
                    "action": "mock", "status": status, "body": _text(config, "mockBody", context),
                    "contentType": _text(config, "mockContentType", context) or "application/json",
                }
            elif action == "headers":
                headers = context.resolve_value(config.get("headers") or {})
                if not isinstance(headers, dict):
                    return ModuleResult(False, error="请求头必须是键值对")
                rule = {"action": "headers", "headers": {str(k): str(v) for k, v in headers.items()}}
            elif action == "block":
                rule = {"action": "block"}
            else:
                return ModuleResult(False, error=f"不支持的拦截方式: {action}")
            await session.start_intercept(pattern, rule)
            return ModuleResult(True, message=f"已开始拦截 {pattern}")
        except Exception as error:  # noqa: BLE001 -- the reason becomes the node error.
            return ModuleResult(False, error=f"请求拦截失败: {error}")


WEB_STATE_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    WebCookieExecutor,
    WebStorageExecutor,
    WebInterceptExecutor,
)
