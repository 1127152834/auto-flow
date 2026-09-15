from __future__ import annotations

import asyncio
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Self

import pytest

from autoflow.domain.workflows.browser import BrowserLocatorPort, BrowserPagePort
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b2_advanced_browser_harness.py")


def frozen_result(case: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS), case],
        check=True,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout)


def executors() -> Any:
    return importlib.import_module(
        "autoflow.application.workflows.executors.advanced_browser"
    )


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

    async def evaluate(self, expression: str) -> Any:
        self.page.calls.append(["evaluate", self.selector, None])
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

    async def screenshot(self, *, path: str | None = None) -> bytes:
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


class Download:
    suggested_filename = "report.csv"

    async def save_as(self, path: Path) -> None:
        path.write_bytes(b"download")


class FileChooser:
    def __init__(self, page: Page) -> None:
        self.page = page

    async def set_files(self, path: str) -> None:
        self.page.calls.append(["set_files", Path(path).name])


class Page:
    def __init__(self) -> None:
        self.id = "page-1"
        self.url = "about:blank"
        self.closed = False
        self.calls: list[list[Any]] = []
        self.mouse = Mouse(self)
        self.viewport_size = {"width": 1200, "height": 800}
        self.evaluate_result: Any = []
        self.image_src: str | None = "data:image/png;base64,UE5H"

    def locator(self, selector: str) -> Locator:
        return Locator(self, selector)

    async def wait_for_load_state(self, state: str, *, timeout_ms: float) -> None:
        self.calls.append(["load", state, {"timeout": timeout_ms}])

    async def capture_download(self, action: Any) -> Download:
        await action()
        return Download()

    async def choose_file(self, action: Any, path: str, *, timeout_ms: float) -> None:
        await action()
        await FileChooser(self).set_files(path)


class Session:
    def __init__(self) -> None:
        self.page = Page()

    def current_page(self) -> Page:
        return self.page


class Artifacts:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.writes: list[tuple[str, bytes, str]] = []

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        target = self.root / Path(name).name
        target.write_bytes(content)
        self.writes.append((name, content, mime_type))
        return str(target)


def payload(result: Any) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "branch": result.branch,
        "data": result.data,
    }


def semantic_calls(calls: list[list[Any]]) -> list[list[Any]]:
    result: list[list[Any]] = []
    for call in calls:
        if call[0] == "evaluate" and call[1] == "html":
            result.append(["page_evaluate", None])
        elif call[0] in {
            "select_option",
            "check",
            "uncheck",
            "drag_to",
            "page_evaluate",
            "mouse_wheel",
            "set_input_files",
            "set_files",
        }:
            result.append(call)
    return result


@pytest.mark.asyncio
async def test_validation_errors_match_frozen_source() -> None:
    module = executors()
    context = ExecutionContext(browser=Session())
    pairs = [
        (module.SelectDropdownExecutor(), {}),
        (module.SetCheckboxExecutor(), {}),
        (module.DragElementExecutor(), {}),
        (module.UploadFileExecutor(), {}),
        (module.GetChildElementsExecutor(), {}),
        (module.GetSiblingElementsExecutor(), {}),
        (module.ElementExistsExecutor(), {}),
        (module.ElementVisibleExecutor(), {}),
        (module.SaveImageExecutor(), {}),
        (module.DownloadFileExecutor(), {}),
    ]

    errors = [
        (await executor.execute(config, context)).error for executor, config in pairs
    ]

    assert errors == frozen_result("validation")["errors"]


@pytest.mark.asyncio
async def test_native_actions_and_scroll_match_frozen_source() -> None:
    module = executors()
    session = Session()
    context = ExecutionContext(browser=session)
    results = [
        await module.SelectDropdownExecutor().execute(
            {"selector": "#choice", "selectBy": "label", "value": "二", "timeout": 2},
            context,
        ),
        await module.SetCheckboxExecutor().execute(
            {"selector": "#check", "checked": "false"}, context
        ),
        await module.DragElementExecutor().execute(
            {"sourceSelector": "#source", "targetSelector": "#target"}, context
        ),
        await module.ScrollPageExecutor().execute(
            {"direction": "left", "distance": 25, "scrollMode": "script"}, context
        ),
    ]

    actual = {
        "results": [payload(item) for item in results],
        "calls": semantic_calls(session.page.calls),
    }

    assert actual == frozen_result("select_checkbox_drag_scroll")


@pytest.mark.asyncio
async def test_upload_direct_file_matches_frozen_source(tmp_path: Path) -> None:
    module = executors()
    session = Session()
    file_path = tmp_path / "fixture.txt"
    file_path.write_text("fixture", encoding="utf-8")

    result = await module.UploadFileExecutor().execute(
        {"selector": "#upload", "filePath": str(file_path)},
        ExecutionContext(browser=session),
    )

    frozen = frozen_result("upload")
    actual = payload(result)
    actual["message"] = actual["message"].split(":", 1)[0]
    assert actual == frozen["result"]
    assert semantic_calls(session.page.calls) == frozen["calls"]


@pytest.mark.asyncio
async def test_upload_file_chooser_matches_frozen_source(tmp_path: Path) -> None:
    module = executors()
    session = Session()
    file_path = tmp_path / "fixture.txt"
    file_path.write_text("fixture", encoding="utf-8")

    result = await module.UploadFileExecutor().execute(
        {"selector": "#upload-button", "filePath": str(file_path)},
        ExecutionContext(browser=session),
    )

    frozen = frozen_result("upload_chooser")
    actual = payload(result)
    actual["message"] = actual["message"].split(":", 1)[0]
    assert actual == frozen["result"]
    assert semantic_calls(session.page.calls) == frozen["calls"]


@pytest.mark.asyncio
async def test_relation_queries_match_frozen_results_and_variables() -> None:
    module = executors()
    session = Session()
    session.page.evaluate_result = ["#first", "#second"]
    context = ExecutionContext(browser=session)

    child = await module.GetChildElementsExecutor().execute(
        {
            "parentSelector": "#parent",
            "childSelector": ".row",
            "variableName": "children",
        },
        context,
    )
    sibling = await module.GetSiblingElementsExecutor().execute(
        {
            "elementSelector": "#current",
            "siblingType": "next",
            "includeSelf": True,
            "variableName": "siblings",
        },
        context,
    )

    assert {
        "results": [payload(child), payload(sibling)],
        "variables": context.variables,
    } == frozen_result("relations")


@pytest.mark.asyncio
async def test_predicate_branches_match_frozen_source() -> None:
    module = executors()
    context = ExecutionContext(browser=Session())
    results = [
        await module.ElementExistsExecutor().execute({"selector": "#many"}, context),
        await module.ElementExistsExecutor().execute({"selector": "#missing"}, context),
        await module.ElementVisibleExecutor().execute({"selector": "#hidden"}, context),
        await module.ElementVisibleExecutor().execute({"selector": "#boom"}, context),
    ]

    assert {"results": [payload(item) for item in results]} == frozen_result(
        "predicates"
    )


@pytest.mark.asyncio
async def test_save_image_preserves_bytes_and_uses_artifact_boundary(
    tmp_path: Path,
) -> None:
    module = executors()
    context = ExecutionContext(browser=Session(), artifacts=Artifacts(tmp_path))

    result = await module.SaveImageExecutor().execute(
        {"selector": "#image", "savePath": "images/image.png", "variableName": "image"},
        context,
    )

    frozen = frozen_result("save_image")
    assert {
        "success": result.success,
        "messagePrefix": result.message.split(":", 1)[0],
        "dataSuffix": Path(result.data).suffix,
        "variableMatches": context.variables["image"] == result.data,
        "bytes": Path(result.data).read_bytes().decode("ascii"),
    } == frozen


@pytest.mark.asyncio
async def test_click_download_preserves_name_and_uses_artifact_boundary(
    tmp_path: Path,
) -> None:
    module = executors()
    context = ExecutionContext(browser=Session(), artifacts=Artifacts(tmp_path))

    result = await module.DownloadFileExecutor().execute(
        {
            "triggerSelector": "#download",
            "savePath": "downloads",
            "variableName": "file",
        },
        context,
    )

    frozen = frozen_result("download_click")
    assert {
        "success": result.success,
        "messagePrefix": result.message.split(":", 1)[0],
        "dataName": Path(result.data).name,
        "variableMatches": context.variables["file"] == result.data,
    } == frozen


@pytest.mark.asyncio
async def test_url_download_stops_stream_before_artifact_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = executors()

    class Response:
        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self) -> Any:
            yield b"123"
            yield b"45"

    class Stream:
        async def __aenter__(self) -> Response:
            return Response()

        async def __aexit__(self, *_args: object) -> None:
            return None

    class Client:
        def __init__(self, **_options: Any) -> None:
            return None

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def stream(self, _method: str, _url: str) -> Stream:
            return Stream()

    artifacts = Artifacts(tmp_path)
    monkeypatch.setattr(module.httpx, "AsyncClient", Client)
    monkeypatch.setattr(module, "_MAX_DOWNLOAD_BYTES", 4)

    result = await module.DownloadFileExecutor().execute(
        {"downloadMode": "url", "downloadUrl": "https://example.test/archive.bin"},
        ExecutionContext(artifacts=artifacts),
    )

    assert result.success is False
    assert result.error == "下载文件失败: 下载文件超过 64 MiB 限制"
    assert artifacts.writes == []


@pytest.mark.asyncio
async def test_url_download_observes_cancellation_between_chunks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = executors()

    class Response:
        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self) -> Any:
            yield b"first"
            yield b"second"

    class Stream:
        async def __aenter__(self) -> Response:
            return Response()

        async def __aexit__(self, *_args: object) -> None:
            return None

    class Client:
        def __init__(self, **_options: Any) -> None:
            return None

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def stream(self, _method: str, _url: str) -> Stream:
            return Stream()

    class Cancellation:
        checks = 0

        @property
        def cancelled(self) -> bool:
            return self.checks >= 3

        def raise_if_cancelled(self) -> None:
            self.checks += 1
            if self.cancelled:
                raise asyncio.CancelledError

    artifacts = Artifacts(tmp_path)
    monkeypatch.setattr(module.httpx, "AsyncClient", Client)
    context = ExecutionContext(artifacts=artifacts, cancellation=Cancellation())

    with pytest.raises(asyncio.CancelledError):
        await module.DownloadFileExecutor().execute(
            {
                "downloadMode": "url",
                "downloadUrl": "https://example.test/archive.bin",
            },
            context,
        )

    assert artifacts.writes == []


@pytest.mark.asyncio
async def test_save_image_rejects_oversized_data_before_artifact_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = executors()
    session = Session()
    session.page.image_src = "data:image/png;base64,MTIzNDU="
    artifacts = Artifacts(tmp_path)
    monkeypatch.setattr(module, "_MAX_IMAGE_BYTES", 4)

    result = await module.SaveImageExecutor().execute(
        {"selector": "#image"},
        ExecutionContext(browser=session, artifacts=artifacts),
    )

    assert result.success is False
    assert result.error == "保存图片失败: 图片超过 64 MiB 限制"
    assert artifacts.writes == []


@pytest.mark.asyncio
async def test_missing_extended_browser_capability_fails_explicitly() -> None:
    module = executors()
    session = Session()

    class LimitedLocator:
        async def wait_for(self, **_options: Any) -> None:
            return None

    session.page.locator = lambda selector: LimitedLocator()  # type: ignore[method-assign]

    result = await module.SetCheckboxExecutor().execute(
        {"selector": "#check", "checked": True}, ExecutionContext(browser=session)
    )

    assert result.success is False
    assert result.error == "设置复选框失败: 浏览器定位器不支持 check"


def test_extended_action_ports_are_available_to_the_real_provider() -> None:
    assert {
        "select_option",
        "check",
        "uncheck",
        "drag_to",
        "bounding_box",
        "set_input_files",
        "nth",
        "inner_text",
    }.issubset(BrowserLocatorPort.__dict__)
    assert {"mouse", "viewport_size", "choose_file"}.issubset(
        BrowserPagePort.__dict__
    )
