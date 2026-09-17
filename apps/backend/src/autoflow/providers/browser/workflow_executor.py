from __future__ import annotations

import asyncio
import json
import math
import re
from collections.abc import Awaitable, Callable, Mapping
from time import monotonic
from typing import Any
from uuid import uuid4

_VARIABLE = re.compile(r"\{([^{}]+)\}")


class ExecutionFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _scalar_text(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class WorkflowExecutor:
    def __init__(
        self,
        context: Any,
        variables: Mapping[str, object],
        emit: Callable[[str, str, str, dict[str, object]], Awaitable[None]],
        should_stop: Callable[[], bool],
        capture_failure: Callable[[Any, str, str], Awaitable[dict[str, object]]] | None = None,
    ) -> None:
        self.context = context
        self.variables = dict(variables)
        self.emit = emit
        self.should_stop = should_stop
        self.capture_failure = capture_failure
        self.page: Any = None

    async def run(self, plan: Mapping[str, Any]) -> dict[str, object]:
        nodes = {node["nodeId"]: node for node in plan["nodes"]}
        for node_id in plan["orderedNodeIds"]:
            if self.should_stop():
                return {"status": "cancelled", "error": None}
            visit = uuid4().hex
            started = monotonic()
            await self.emit("nodeAttempt", node_id, visit, {"status": "started"})
            if self.should_stop():
                return {"status": "cancelled", "error": None}
            await self.emit("log", node_id, visit, {"level": "info", "message": "开始执行节点"})
            if self.should_stop():
                return {"status": "cancelled", "error": None}
            try:
                node = nodes[node_id]
                data = dict(node["data"])
                timeout_seconds = self._timeout(data)
                if timeout_seconds == 0:
                    output = await self._execute(node["moduleType"], data)
                else:
                    async with asyncio.timeout(timeout_seconds):
                        output = await self._execute(node["moduleType"], data)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- browser errors must be redacted.
                error = self._safe_error(exc)
                await self.emit("log", node_id, visit, {"level": "error", "message": str(error["message"])})
                await self.emit(
                    "nodeAttempt", node_id, visit,
                    {"status": "failed", "durationMs": round((monotonic() - started) * 1000), "error": error},
                )
                if self.capture_failure is not None:
                    await self.emit(
                        "artifact", node_id, visit,
                        await self.capture_failure(self.page, node_id, visit),
                    )
                return {"status": "failed", "error": error}
            if output is not None:
                name, value = output
                self.variables[name] = value
                await self.emit("output", node_id, visit, {"name": name, "value": value})
            await self.emit("log", node_id, visit, {"level": "info", "message": "节点执行完成"})
            await self.emit(
                "nodeAttempt", node_id, visit,
                {"status": "succeeded", "durationMs": round((monotonic() - started) * 1000)},
            )
        return {"status": "succeeded", "error": None}

    def _timeout(self, data: Mapping[str, Any]) -> float:
        value = data.get("timeout", 0)
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value < 0
        ):
            raise ExecutionFailure("WORKFLOW_NODE_INVALID", "节点超时配置无效")
        return float(value)

    def _text(self, value: object) -> str:
        if not isinstance(value, str):
            raise ExecutionFailure("WORKFLOW_NODE_INVALID", "节点文本配置无效")

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in self.variables:
                raise ExecutionFailure("WORKFLOW_VARIABLE_UNKNOWN", "工作流变量不存在")
            return _scalar_text(self.variables[name])

        return _VARIABLE.sub(replace, value)

    def _current(self) -> Any:
        if self.page is None or self.page.is_closed():
            raise ExecutionFailure("WORKFLOW_PAGE_CLOSED", "当前网页已关闭")
        return self.page

    async def _execute(
        self, module_type: str, data: Mapping[str, Any]
    ) -> tuple[str, object] | None:
        if module_type == "open_page":
            mode = data.get("openMode", "new_tab")
            if mode == "new_tab" or self.page is None:
                self.page = await self.context.new_page()
            elif mode != "current_tab":
                raise ExecutionFailure("WORKFLOW_NODE_INVALID", "打开方式无效")
            await self._current().goto(
                self._text(data.get("url")),
                wait_until=data.get("waitUntil", "load"),
            )
            return None
        if self.page is None:
            self.page = await self.context.new_page()
        page = self._current()
        selector = self._text(data.get("selector"))
        locator = page.locator(selector).first
        if module_type == "input_text":
            text = self._text(data.get("text"))
            if data.get("clearBefore", True):
                await locator.fill(text)
            else:
                current = await locator.input_value()
                await locator.fill(current + text)
            return None
        if module_type == "click_element":
            await self._click(page, locator, data)
            return None
        if module_type == "get_element_info":
            attribute = data.get("attribute", "text")
            if not isinstance(attribute, str) or not attribute:
                raise ExecutionFailure("WORKFLOW_NODE_INVALID", "读取属性无效")
            if attribute == "value":
                value = await locator.input_value()
            else:
                value = await locator.evaluate(
                    """(element, attribute) => {
                      if (attribute === 'text') return element.textContent;
                      if (attribute === 'innerHTML') return element.innerHTML;
                      if (attribute === 'attributes') return Object.fromEntries(
                        [...element.attributes].map(item => [item.name, item.value]));
                      return element.getAttribute(attribute);
                    }""",
                    attribute,
                )
            name = data.get("variableName", "element_value")
            if not isinstance(name, str) or not name:
                raise ExecutionFailure("WORKFLOW_NODE_INVALID", "输出变量名无效")
            return name, value
        raise ExecutionFailure("WORKFLOW_NODE_UNSUPPORTED", "不支持的节点类型")

    async def _click(self, page: Any, locator: Any, data: Mapping[str, Any]) -> None:
        click_type = data.get("clickType", "single")
        follow = data.get("followNewTab", False)
        popup: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

        def opened(new_page: Any) -> None:
            if not popup.done():
                popup.set_result(new_page)

        if follow:
            page.on("popup", opened)
        try:
            if click_type == "double":
                await locator.dblclick()
            elif click_type in {"single", "right"}:
                await locator.click(button="right" if click_type == "right" else "left")
            else:
                raise ExecutionFailure("WORKFLOW_NODE_INVALID", "点击类型无效")
            if follow:
                done, _ = await asyncio.wait({popup}, timeout=3)
                if done:
                    self.page = popup.result()
        finally:
            if follow:
                page.remove_listener("popup", opened)
            if not popup.done():
                popup.cancel()

    @staticmethod
    def _safe_error(exc: Exception) -> dict[str, str]:
        if isinstance(exc, ExecutionFailure):
            return {"code": exc.code, "message": exc.message}
        if isinstance(exc, TimeoutError) or type(exc).__name__ == "TimeoutError":
            return {"code": "WORKFLOW_NODE_TIMEOUT", "message": "节点执行超时"}
        return {"code": "WORKFLOW_NODE_FAILED", "message": "节点执行失败"}
