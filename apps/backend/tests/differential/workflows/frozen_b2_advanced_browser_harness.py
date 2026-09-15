from __future__ import annotations

import asyncio
import io
import json
import sys
import tempfile
from contextlib import AbstractAsyncContextManager, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.executors.advanced_browser import (
    DownloadFileExecutor,
    DragElementExecutor,
    ElementExistsExecutor,
    ElementVisibleExecutor,
    GetChildElementsExecutor,
    GetSiblingElementsExecutor,
    SaveImageExecutor,
    ScrollPageExecutor,
    SelectDropdownExecutor,
    SetCheckboxExecutor,
    UploadFileExecutor,
)
from app.executors.base import ExecutionContext


class Locator:
    def __init__(self, page: Page, selector: str) -> None:
        self.page = page
        self.selector = selector

    @property
    def first(self) -> Locator:
        return self

    def locator(self, selector: str) -> Locator:
        return Locator(self.page, f"{self.selector} {selector}")

    def nth(self, index: int) -> Locator:
        return Locator(self.page, f"{self.selector}:nth({index})")

    async def wait_for(self, **options: Any) -> None:
        self.page.calls.append(["wait", self.selector, options])

    async def count(self) -> int:
        if self.selector == "#missing":
            return 0
        if self.selector == "#many":
            return 3
        return 1

    async def is_visible(self) -> bool:
        if self.selector == "#hidden":
            return False
        if self.selector == "#boom":
            raise RuntimeError("visibility failed")
        return await self.count() > 0

    async def inner_text(self) -> str:
        return "目标项"

    async def click(self, **options: Any) -> None:
        self.page.calls.append(["click", self.selector, options])

    async def evaluate(self, expression: str, argument: Any = None) -> Any:
        self.page.calls.append(["evaluate", self.selector, argument])
        if expression.strip() == "el => el.tagName.toLowerCase()":
            return "div" if self.selector == "#upload-button" else "input"
        if "el.type" in expression:
            return "file"
        return self.page.evaluate_result

    async def select_option(self, **options: Any) -> None:
        self.page.calls.append(["select_option", self.selector, options])

    async def check(self) -> None:
        self.page.calls.append(["check", self.selector])

    async def uncheck(self) -> None:
        self.page.calls.append(["uncheck", self.selector])

    async def drag_to(self, target: Locator) -> None:
        self.page.calls.append(["drag_to", self.selector, target.selector])

    async def bounding_box(self) -> dict[str, float]:
        return {"x": 10, "y": 20, "width": 30, "height": 40}

    async def set_input_files(self, path: str) -> None:
        self.page.calls.append(["set_input_files", self.selector, Path(path).name])

    async def get_attribute(self, name: str) -> str | None:
        return self.page.image_src if name == "src" else None

    async def screenshot(self) -> bytes:
        return b"PNG"


class Mouse:
    def __init__(self, page: Page) -> None:
        self.page = page

    async def move(self, x: float, y: float, **options: Any) -> None:
        self.page.calls.append(["mouse_move", x, y, options])

    async def down(self) -> None:
        self.page.calls.append(["mouse_down"])

    async def up(self) -> None:
        self.page.calls.append(["mouse_up"])

    async def wheel(self, x: float, y: float) -> None:
        self.page.calls.append(["mouse_wheel", x, y])


class DownloadContext(AbstractAsyncContextManager[Any]):
    async def __aenter__(self) -> Any:
        async def value() -> Any:
            return Download()

        return SimpleNamespace(value=value())

    async def __aexit__(self, *_args: object) -> None:
        return None


class FileChooserContext(AbstractAsyncContextManager[Any]):
    def __init__(self, page: Page) -> None:
        self.page = page

    async def __aenter__(self) -> Any:
        async def value() -> Any:
            page = self.page

            class FileChooser:
                async def set_files(self, path: str) -> None:
                    page.calls.append(["set_files", Path(path).name])

            return FileChooser()

        return SimpleNamespace(value=value())

    async def __aexit__(self, *_args: object) -> None:
        return None


class Download:
    suggested_filename = "report.csv"

    async def save_as(self, path: str) -> None:
        Path(path).write_bytes(b"download")

    async def path(self) -> str:
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            raw_path = handle.name
        Path(raw_path).write_bytes(b"download")
        return raw_path


class Page:
    def __init__(self) -> None:
        self.calls: list[list[Any]] = []
        self.mouse = Mouse(self)
        self.viewport_size = {"width": 1200, "height": 800}
        self.evaluate_result: Any = []
        self.image_src: str | None = "data:image/png;base64,UE5H"

    def locator(self, selector: str) -> Locator:
        return Locator(self, selector)

    async def wait_for_selector(self, selector: str, **options: Any) -> None:
        self.calls.append(["wait_for_selector", selector, options])

    async def wait_for_load_state(self, state: str, **options: Any) -> None:
        self.calls.append(["load", state, options])

    async def wait_for_timeout(self, delay: int) -> None:
        self.calls.append(["timeout", delay])

    async def evaluate(self, expression: str, argument: Any = None) -> Any:
        self.calls.append(["page_evaluate", argument])
        return self.evaluate_result

    async def click(self, selector: str) -> None:
        self.calls.append(["page_click", selector])

    def expect_download(self) -> DownloadContext:
        return DownloadContext()

    def expect_file_chooser(self, **_options: Any) -> FileChooserContext:
        return FileChooserContext(self)


def result_payload(result: Any) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "branch": result.branch,
        "data": result.data,
    }


def semantic_calls(calls: list[list[Any]]) -> list[list[Any]]:
    return [
        call
        for call in calls
        if call[0]
        in {
            "select_option",
            "check",
            "uncheck",
            "drag_to",
            "page_evaluate",
            "mouse_wheel",
            "set_input_files",
            "set_files",
        }
    ]


async def run(case: str) -> dict[str, Any]:
    page = Page()
    context = ExecutionContext(page=page)
    if case == "validation":
        pairs = [
            (SelectDropdownExecutor(), {}),
            (SetCheckboxExecutor(), {}),
            (DragElementExecutor(), {}),
            (UploadFileExecutor(), {}),
            (GetChildElementsExecutor(), {}),
            (GetSiblingElementsExecutor(), {}),
            (ElementExistsExecutor(), {}),
            (ElementVisibleExecutor(), {}),
            (SaveImageExecutor(), {}),
            (DownloadFileExecutor(), {}),
        ]
        return {
            "errors": [
                (await item.execute(config, context)).error for item, config in pairs
            ]
        }
    if case == "select_checkbox_drag_scroll":
        results = [
            await SelectDropdownExecutor().execute(
                {
                    "selector": "#choice",
                    "selectBy": "label",
                    "value": "二",
                    "timeout": 2,
                },
                context,
            ),
            await SetCheckboxExecutor().execute(
                {"selector": "#check", "checked": "false"}, context
            ),
            await DragElementExecutor().execute(
                {"sourceSelector": "#source", "targetSelector": "#target"}, context
            ),
            await ScrollPageExecutor().execute(
                {"direction": "left", "distance": 25, "scrollMode": "script"}, context
            ),
        ]
        return {
            "results": [result_payload(item) for item in results],
            "calls": semantic_calls(page.calls),
        }
    if case == "upload":
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "fixture.txt"
            file_path.write_text("fixture", encoding="utf-8")
            result = await UploadFileExecutor().execute(
                {"selector": "#upload", "filePath": str(file_path)}, context
            )
        item = result_payload(result)
        item["message"] = item["message"].split(":", 1)[0]
        return {"result": item, "calls": semantic_calls(page.calls)}
    if case == "upload_chooser":
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "fixture.txt"
            file_path.write_text("fixture", encoding="utf-8")
            result = await UploadFileExecutor().execute(
                {"selector": "#upload-button", "filePath": str(file_path)}, context
            )
        item = result_payload(result)
        item["message"] = item["message"].split(":", 1)[0]
        return {"result": item, "calls": semantic_calls(page.calls)}
    if case == "relations":
        page.evaluate_result = ["#first", "#second"]
        child = await GetChildElementsExecutor().execute(
            {
                "parentSelector": "#parent",
                "childSelector": ".row",
                "variableName": "children",
            },
            context,
        )
        sibling = await GetSiblingElementsExecutor().execute(
            {
                "elementSelector": "#current",
                "siblingType": "next",
                "includeSelf": True,
                "variableName": "siblings",
            },
            context,
        )
        return {
            "results": [result_payload(child), result_payload(sibling)],
            "variables": context.variables,
        }
    if case == "predicates":
        results = [
            await ElementExistsExecutor().execute({"selector": "#many"}, context),
            await ElementExistsExecutor().execute({"selector": "#missing"}, context),
            await ElementVisibleExecutor().execute({"selector": "#hidden"}, context),
            await ElementVisibleExecutor().execute({"selector": "#boom"}, context),
        ]
        return {"results": [result_payload(item) for item in results]}
    if case == "save_image":
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "image.png"
            result = await SaveImageExecutor().execute(
                {
                    "selector": "#image",
                    "savePath": str(target),
                    "variableName": "image",
                },
                context,
            )
            return {
                "success": result.success,
                "messagePrefix": result.message.split(":", 1)[0],
                "dataSuffix": Path(result.data).suffix,
                "variableMatches": context.variables["image"] == result.data,
                "bytes": target.read_bytes().decode("ascii"),
            }
    if case == "download_click":
        with tempfile.TemporaryDirectory() as directory:
            result = await DownloadFileExecutor().execute(
                {
                    "triggerSelector": "#download",
                    "savePath": directory,
                    "variableName": "file",
                },
                context,
            )
            return {
                "success": result.success,
                "messagePrefix": result.message.split(":", 1)[0],
                "dataName": Path(result.data).name,
                "variableMatches": context.variables["file"] == result.data,
            }
    raise ValueError(case)


if __name__ == "__main__":
    captured = io.StringIO()
    with redirect_stdout(captured):
        payload = asyncio.run(run(sys.argv[1]))
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
