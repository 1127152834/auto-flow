from __future__ import annotations

import asyncio
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from app.executors.base import ExecutionContext
from app.executors.basic import (
    ClickElementExecutor,
    GetElementInfoExecutor,
    InputTextExecutor,
    OpenPageExecutor,
    ScreenshotExecutor,
)


class Locator:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.calls: list[list[Any]] = []

    @property
    def first(self) -> Locator:
        return self

    def locator(self, _selector: str) -> Locator:
        return self

    async def count(self) -> int:
        return 1

    async def evaluate(self, expression: str) -> Any:
        if "tagName" in expression:
            return "input"
        if "isContentEditable" in expression:
            return False
        if "element.attributes" in expression:
            return {"href": "/raw", "src": "image.png", "data-id": "7"}
        raise AssertionError(expression)

    async def is_visible(self) -> bool:
        return True

    async def wait_for(self, **options: Any) -> None:
        self.calls.append(["wait_for", options])

    async def click(self, **options: Any) -> None:
        self.calls.append(["click", options])

    async def dblclick(self, **options: Any) -> None:
        self.calls.append(["double_click", options])

    async def clear(self) -> None:
        self.calls.append(["clear", None])

    async def fill(self, value: str) -> None:
        self.calls.append(["fill", value])

    async def press_sequentially(self, value: str, *, delay: float = 0) -> None:
        self.calls.append(["press_sequentially", [value, delay]])

    async def type(self, value: str, *, delay: float = 0) -> None:
        self.calls.append(["type_text", [value, delay]])

    async def text_content(self) -> str:
        return "文本"

    async def inner_html(self) -> str:
        return "<b>文本</b>"

    async def input_value(self) -> str:
        return "值"

    async def get_attribute(self, name: str) -> str | None:
        return {"href": "/raw", "src": "image.png", "data-id": "7"}.get(name)

    async def screenshot(self, *, path: str) -> None:
        self.calls.append(["screenshot", Path(path).name])


class Keyboard:
    def __init__(self, page: Page) -> None:
        self.page = page

    async def press(self, key: str) -> None:
        self.page.calls.append(["keyboard_press", key])

    async def type(self, value: str) -> None:
        self.page.calls.append(["keyboard_type", value])


class Page:
    def __init__(self, context: BrowserContext) -> None:
        self.context = context
        self.url = "about:blank"
        self.calls: list[list[Any]] = []
        self.element = Locator(self)
        self.keyboard = Keyboard(self)

    def locator(self, _selector: str) -> Locator:
        return self.element

    async def goto(self, url: str, *, wait_until: str) -> None:
        self.url = url
        self.calls.append(["goto", [url, wait_until]])

    async def bring_to_front(self) -> None:
        self.calls.append(["front", None])

    async def wait_for_load_state(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def screenshot(self, *, path: str, full_page: bool) -> None:
        self.calls.append(["screenshot", [full_page, Path(path).name]])

    def on(self, *_args: Any) -> None:
        return None


class BrowserContext:
    def __init__(self) -> None:
        self.pages: list[Page] = []
        self.listeners: list[Any] = []

    async def new_page(self) -> Page:
        page = Page(self)
        self.pages.append(page)
        for listener in list(self.listeners):
            listener(page)
        return page

    async def new_cdp_session(self, _page: Page) -> Any:
        raise RuntimeError("CDP deliberately unavailable in differential harness")

    def on(self, event: str, listener: Any) -> None:
        if event == "page":
            self.listeners.append(listener)

    def remove_listener(self, event: str, listener: Any) -> None:
        if event == "page" and listener in self.listeners:
            self.listeners.remove(listener)


async def run(case: str) -> dict[str, Any]:
    browser = BrowserContext()
    page = await browser.new_page()
    context = ExecutionContext(browser_context=browser, page=page)

    if case == "missing":
        results = [
            await OpenPageExecutor().execute({"url": ""}, context),
            await ClickElementExecutor().execute({"selector": ""}, context),
            await InputTextExecutor().execute({"selector": ""}, context),
            await GetElementInfoExecutor().execute({"selector": ""}, context),
        ]
        return {"errors": [result.error for result in results], "pageCalls": page.calls}

    if case == "open":
        context.variables["url"] = "https://example.test"
        result = await OpenPageExecutor().execute(
            {"url": "{url}", "openMode": "current_tab", "waitUntil": "load"},
            context,
        )
        return {
            "success": result.success,
            "message": result.message,
            "pageCount": len(browser.pages),
            "calls": page.calls,
        }
    if case == "click":
        result = await ClickElementExecutor().execute(
            {
                "selector": "#button",
                "clickType": "right",
                "followNewTab": False,
                "timeout": 2,
            },
            context,
        )
        return {
            "success": result.success,
            "message": result.message,
            "calls": page.element.calls,
        }
    if case == "input":
        context.variables["text"] = "中文"
        result = await InputTextExecutor().execute(
            {
                "selector": "#input",
                "text": "{text}",
                "clearBefore": True,
                "typeSequential": True,
            },
            context,
        )
        return {
            "success": result.success,
            "message": result.message,
            "calls": page.element.calls,
        }
    if case == "extract":
        result = await GetElementInfoExecutor().execute(
            {
                "selector": "#value",
                "attribute": "attributes",
                "variableName": "result",
                "columnName": "结果",
            },
            context,
        )
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "variable": context.variables["result"],
            "column": context.current_row["结果"],
        }
    if case == "screenshot":
        with tempfile.TemporaryDirectory() as directory:
            result = await ScreenshotExecutor().execute(
                {
                    "screenshotType": "viewport",
                    "savePath": directory,
                    "fileNamePattern": "核验_{时间戳}",
                    "variableName": "shot",
                },
                context,
            )
            return {
                "success": result.success,
                "messagePrefix": result.message.split(":", 1)[0],
                "variableMatches": context.variables["shot"] == result.data["path"],
                "fullPage": page.calls[-1][1][0],
                "suffix": Path(result.data["path"]).suffix,
            }
    raise ValueError(case)


if __name__ == "__main__":
    output = io.StringIO()
    with redirect_stdout(output):
        result = asyncio.run(run(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
