from __future__ import annotations

import asyncio
from collections.abc import Callable
from time import monotonic
from typing import Any

from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import resolve_node_config
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifacts
from autoflow.providers.browser.workflow_locator import NodeFailure, locate_element


class WorkflowExecutor:
    def __init__(
        self, context: Any, artifacts: WorkflowArtifacts,
        variables: dict[str, Any], emit: Callable[[dict[str, Any]], None],
    ) -> None:
        self.context, self.artifacts = context, artifacts
        self.variables, self.emit = variables, emit
        self.page: Any = None
        self.deadline = 0.0

    async def run(self, document: dict[str, Any], node_ids: list[str]) -> dict[str, Any]:
        nodes = {node["id"]: node for node in document["nodes"]}
        self.emit({"type": "ready", "message": "浏览器已启动"})
        for node_id in node_ids:
            node = nodes[node_id]
            started = monotonic()
            self.emit({"type": "node_started", "nodeId": node_id, "message": "节点开始执行"})
            try:
                config = resolve_node_config(node, self.variables)
                self.deadline = asyncio.get_running_loop().time() + config["timeoutSeconds"]
                async with asyncio.timeout_at(self.deadline):
                    artifact = await self._execute(node["type"], node_id, config)
                    self._timeout()
            except asyncio.CancelledError:
                raise
            except Exception as exception:  # noqa: BLE001 -- convert browser failures to safe node errors.
                error = self._error(exception, node_id)
                self.emit({
                    "type": "node_failed", "nodeId": node_id, "level": "error",
                    "message": error["message"], "error": error,
                    "durationMs": round((monotonic() - started) * 1000),
                })
                return {"state": "failed", "error": error}
            event = {
                "type": "node_succeeded", "nodeId": node_id, "message": "节点执行成功",
                "durationMs": round((monotonic() - started) * 1000),
            }
            if artifact is not None:
                event["artifact"] = artifact
            self.emit(event)
        return {"state": "succeeded", "error": None}

    def _timeout(self) -> float:
        remaining = (self.deadline - asyncio.get_running_loop().time()) * 1000
        if remaining <= 0:
            raise TimeoutError
        return remaining

    def _current(self) -> Any:
        if self.page is None or self.page.is_closed():
            raise NodeFailure("workflow_page_closed", "当前网页已关闭")
        return self.page

    async def _execute(
        self, node_type: str, node_id: str, config: dict[str, Any]
    ) -> dict[str, Any] | None:
        if node_type == "open_page":
            if config["openMode"] == "new_tab" or self.page is None:
                self.page = await self.context.new_page()
            page = self._current()
            await page.goto(config["url"], wait_until=config["waitUntil"], timeout=self._timeout())
            return None
        if self.page is None:
            self.page = await self.context.new_page()
        page = self._current()
        if node_type == "screenshot":
            if config["screenshotType"] == "element":
                locator = await locate_element(page, config, self._timeout)
                data = await locator.screenshot(
                    type="png", timeout=self._timeout(),
                )
            else:
                data = await page.screenshot(
                    type="png", full_page=config["screenshotType"] == "fullpage",
                    timeout=self._timeout(),
                )
            # Writes finish before cancellation/terminal state; no background file writer survives a run.
            artifact = self.artifacts.save_png(node_id, data, config["savePath"])
            self._timeout()
            self.variables[config["variableName"]] = artifact["outputPath"]
            return artifact
        locator = await locate_element(page, config, self._timeout)
        if node_type == "click_element":
            await self._click(page, locator, config)
        elif node_type == "input_text":
            await self._input(locator, config)
        elif node_type == "wait_element":
            await locator.wait_for(state=config["waitCondition"], timeout=self._timeout())
        elif node_type == "get_element_info":
            await locator.wait_for(state="attached", timeout=self._timeout())
            if config["attribute"] == "value":
                value = await locator.input_value(timeout=self._timeout())
            else:
                value = await locator.evaluate(
                    """(element, attribute) => {
                        if (attribute === 'text') return element.textContent;
                        if (attribute === 'innerHTML') return element.innerHTML;
                        if (attribute === 'attributes')
                            return Object.fromEntries([...element.attributes].map(a => [a.name, a.value]));
                        return element.getAttribute(attribute);
                    }""", config["attribute"], timeout=self._timeout(),
                )
            artifact = self.artifacts.save_json(node_id, value)
            self._timeout()
            self.variables[config["variableName"]] = value
            return artifact
        else:
            raise NodeFailure("workflow_node_unsupported", "不支持的节点类型")
        return None

    async def _click(self, page: Any, locator: Any, config: dict[str, Any]) -> None:
        popup: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

        def on_popup(new_page: Any) -> None:
            if not popup.done():
                popup.set_result(new_page)

        if config["followNewTab"]:
            page.on("popup", on_popup)
        try:
            if config["clickType"] == "double":
                await locator.dblclick(timeout=self._timeout())
            else:
                await locator.click(
                    button="right" if config["clickType"] == "right" else "left",
                    timeout=self._timeout(),
                )
            if config["followNewTab"]:
                # Missing popup is success; leave a small margin so the optional wait cannot
                # consume the outer deadline after the required click already completed.
                wait = max(0.0, min(3.0, self._timeout() / 1000 - 0.01))
                if not popup.done() and wait:
                    await asyncio.wait({popup}, timeout=wait)
                if popup.done():
                    self.page = popup.result()
        finally:
            if config["followNewTab"]:
                page.remove_listener("popup", on_popup)
            if not popup.done():
                popup.cancel()

    async def _input(self, locator: Any, config: dict[str, Any]) -> None:
        await locator.wait_for(state="visible", timeout=self._timeout())
        editable = "input:not([type=hidden]), textarea, [contenteditable]:not([contenteditable=false])"
        direct = await locator.evaluate(
            "el => el.matches('input, textarea') || el.isContentEditable",
            timeout=self._timeout(),
        )
        if not direct:
            locator = locator.locator(editable).first
        await locator.wait_for(state="visible", timeout=self._timeout())
        if config["clearBefore"]:
            await locator.fill(config["text"], timeout=self._timeout())
            return
        # Read and fill the verified target itself; this also supports number/email
        # inputs whose native selection APIs reject setSelectionRange.
        current = await locator.evaluate(
            "el => 'value' in el ? el.value : el.isContentEditable ? el.textContent : null",
            timeout=self._timeout(),
        )
        if current is None:
            raise NodeFailure("workflow_input_not_editable", "目标元素不可编辑", ["config", "selector"])
        await locator.fill(current + config["text"], timeout=self._timeout())

    def _error(self, exception: Exception, node_id: str) -> dict[str, Any]:
        if isinstance(exception, NodeFailure):
            code, message, path = exception.code, exception.message, exception.path
        elif isinstance(exception, WorkflowError):
            issue = exception.issues[0] if exception.issues else None
            code, message = exception.code, exception.message
            path = issue.path if issue else []
        elif isinstance(exception, TimeoutError) or type(exception).__name__ == "TimeoutError":
            code, message, path = "workflow_node_timeout", "节点执行超时", ["config", "timeoutSeconds"]
        elif self.page is not None and self.page.is_closed():
            code, message, path = "workflow_page_closed", "当前网页已关闭", []
        elif isinstance(exception, FileExistsError):
            code, message, path = "workflow_artifact_exists", "截图文件已存在", ["config", "savePath"]
        elif isinstance(exception, (OSError, ValueError)):
            code, message, path = "workflow_artifact_failed", "产物文件保存失败或路径无效", []
        else:
            # Playwright exceptions contain selectors, URLs and page data; never emit them.
            code, message, path = "workflow_node_failed", "节点执行失败，请检查网页与节点配置", []
        return {"code": code, "message": message, "nodeId": node_id, "path": path}
