from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.basic import (
    ClickElementExecutor,
    GetElementInfoExecutor,
    InputTextExecutor,
    OpenPageExecutor,
    ScreenshotExecutor,
)
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext, WorkflowClock

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b1_harness.py")


def frozen_result(case: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS), case],
        check=True,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout.splitlines()[-1])


class FakeLocator:
    def __init__(
        self,
        *,
        tag: str = "div",
        text: str | None = "文本",
        html: str = "<b>文本</b>",
        value: str = "值",
        attributes: dict[str, str] | None = None,
        contenteditable: bool = False,
        count: int = 1,
        fail_wait_states: set[str] | None = None,
    ) -> None:
        self.tag = tag
        self.text = text
        self.html = html
        self.value = value
        self.attributes = attributes or {
            "href": "/raw",
            "src": "image.png",
            "data-id": "7",
        }
        self.contenteditable = contenteditable
        self.match_count = count
        self.fail_wait_states = fail_wait_states or set()
        self.calls: list[tuple[str, Any]] = []
        self.children: dict[str, FakeLocator] = {}

    def locator(self, selector: str) -> FakeLocator:
        return self.children.setdefault(selector, FakeLocator(count=0))

    async def count(self) -> int:
        return self.match_count

    async def evaluate(self, expression: str) -> Any:
        if "tagName" in expression:
            return self.tag
        if "isContentEditable" in expression:
            return self.contenteditable
        if "element.attributes" in expression:
            return dict(self.attributes)
        raise AssertionError(expression)

    async def is_visible(self) -> bool:
        return self.match_count > 0

    async def wait_for(self, **options: Any) -> None:
        self.calls.append(("wait_for", options))
        if options.get("state") in self.fail_wait_states:
            raise TimeoutError(f"{options['state']} failed")
        if self.match_count == 0:
            raise TimeoutError("not found")

    async def click(self, **options: Any) -> None:
        self.calls.append(("click", options))

    async def double_click(self, **options: Any) -> None:
        self.calls.append(("double_click", options))

    async def clear(self) -> None:
        self.calls.append(("clear", None))
        self.value = ""

    async def fill(self, value: str) -> None:
        self.calls.append(("fill", value))
        self.value = value

    async def press_sequentially(self, value: str, *, delay_ms: float = 0) -> None:
        self.calls.append(("press_sequentially", (value, delay_ms)))

    async def type_text(self, value: str, *, delay_ms: float = 0) -> None:
        self.calls.append(("type_text", (value, delay_ms)))

    async def text_content(self) -> str | None:
        self.calls.append(("text_content", None))
        return self.text

    async def inner_html(self) -> str:
        return self.html

    async def input_value(self) -> str:
        return self.value

    async def get_attribute(self, name: str) -> str | None:
        return self.attributes.get(name)

    async def screenshot(self, *, path: str | None = None) -> bytes:
        self.calls.append(("screenshot", path))
        return b"\x89PNG\r\n\x1a\nELEMENT"


class FakePage:
    def __init__(self, page_id: str = "page-1") -> None:
        self.id = page_id
        self.url = "about:blank"
        self.closed = False
        self.locators: dict[str, FakeLocator] = {}
        self.calls: list[tuple[str, Any]] = []

    async def goto(self, url: str, *, wait_until: str, timeout_ms: float) -> None:
        self.url = url
        self.calls.append(("goto", (url, wait_until, timeout_ms)))

    async def wait_for_load_state(self, state: str, *, timeout_ms: float) -> None:
        self.calls.append(("load", (state, timeout_ms)))

    async def bring_to_front(self) -> None:
        self.calls.append(("front", None))

    async def keyboard_press(self, key: str) -> None:
        self.calls.append(("keyboard_press", key))

    async def keyboard_type(self, value: str) -> None:
        self.calls.append(("keyboard_type", value))

    def locator(self, selector: str) -> FakeLocator:
        return self.locators.setdefault(selector, FakeLocator())

    async def screenshot(
        self, *, full_page: bool = False, path: str | None = None
    ) -> bytes:
        self.calls.append(("screenshot", (full_page, path)))
        return b"\x89PNG\r\n\x1a\nPAGE"

    async def capture_download(self, action: Any) -> Any:
        raise AssertionError("not used")


class FakeSession:
    def __init__(self) -> None:
        self.items = [FakePage()]
        self.current = self.items[0]
        self.watch = object()
        self.followed: bool | None = None

    def current_page(self) -> FakePage:
        return self.current

    def pages(self) -> tuple[FakePage, ...]:
        return tuple(self.items)

    async def new_page(self) -> FakePage:
        self.current = FakePage(f"page-{len(self.items) + 1}")
        self.items.append(self.current)
        return self.current

    def select_page(self, page_id: str) -> FakePage:
        self.current = next(page for page in self.items if page.id == page_id)
        return self.current

    def begin_new_page_watch(self) -> object:
        return self.watch

    async def settle_new_page_watch(
        self, watch: object, *, follow: bool, wait_ms: int = 3000
    ) -> FakePage | None:
        assert watch is self.watch
        self.followed = follow
        return None

    async def close(self) -> None:
        return None


class FakeArtifacts:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.writes: list[tuple[str, bytes, str]] = []

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        self.writes.append((name, content, mime_type))
        return str(self.root / name)


class RunWasCancelled(Exception):
    pass


class MutableCancellation:
    def __init__(self) -> None:
        self.cancelled = False

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise RunWasCancelled


@pytest.mark.asyncio
async def test_open_page_preserves_mode_defaults_and_variable_resolution() -> None:
    session = FakeSession()
    context = ExecutionContext(variables={"url": "https://example.test"}, browser=session)

    result = await OpenPageExecutor().execute(
        {"url": "{url}", "openMode": "current_tab", "waitUntil": "load"}, context
    )

    assert result.success is True
    assert len(session.items) == 1
    assert session.current.calls == [
        ("goto", ("https://example.test", "load", 30_000)),
        ("front", None),
    ]
    assert result.message == "已打开网页: https://example.test"


@pytest.mark.asyncio
@pytest.mark.parametrize("wait_until", ["load", "domcontentloaded", "networkidle"])
async def test_open_page_new_tab_preserves_wait_modes(wait_until: str) -> None:
    session = FakeSession()

    result = await OpenPageExecutor().execute(
        {"url": "https://example.test", "waitUntil": wait_until},
        ExecutionContext(browser=session),
    )

    assert result.success is True
    assert len(session.items) == 2
    assert session.current.calls[0] == (
        "goto",
        ("https://example.test", wait_until, 30_000),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "click_type,expected_call",
    [("single", "click"), ("double", "double_click"), ("right", "click")],
)
async def test_click_element_preserves_click_modes_and_tab_follow(
    click_type: str, expected_call: str
) -> None:
    session = FakeSession()
    locator = session.current.locator("#button")
    context = ExecutionContext(browser=session)

    result = await ClickElementExecutor().execute(
        {
            "selector": "#button",
            "clickType": click_type,
            "followNewTab": "true",
            "timeout": 2,
        },
        context,
    )

    assert result.success is True
    assert locator.calls[0] == ("wait_for", {"state": "attached", "timeout_ms": 2000})
    assert locator.calls[1][0] == expected_call
    if click_type == "right":
        assert locator.calls[1][1]["button"] == "right"
    assert session.followed is True


@pytest.mark.asyncio
async def test_click_element_can_skip_wait_and_keep_unlimited_timeout() -> None:
    session = FakeSession()
    locator = session.current.locator("#button")

    result = await ClickElementExecutor().execute(
        {"selector": "#button", "waitForSelector": False, "timeout": 0},
        ExecutionContext(browser=session),
    )

    assert result.success is True
    assert locator.calls == [("click", {"timeout": None})]


@pytest.mark.asyncio
async def test_input_text_preserves_clear_and_sequential_typing() -> None:
    session = FakeSession()
    locator = FakeLocator(tag="input")
    session.current.locators["#input"] = locator
    context = ExecutionContext(variables={"text": "中文"}, browser=session)

    result = await InputTextExecutor().execute(
        {
            "selector": "#input",
            "text": "{text}",
            "clearBefore": True,
            "typeSequential": True,
        },
        context,
    )

    assert result.success is True
    assert ("clear", None) in locator.calls
    assert ("press_sequentially", ("中文", 20)) in locator.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attribute,expected",
    [
        ("text", "文本"),
        ("innerHTML", "<b>文本</b>"),
        ("value", "值"),
        ("href", "/raw"),
        ("src", "image.png"),
        ("data-id", "7"),
        (
            "attributes",
            {"href": "/raw", "src": "image.png", "data-id": "7"},
        ),
    ],
)
async def test_get_element_info_preserves_attribute_modes_and_outputs(
    attribute: str, expected: Any
) -> None:
    session = FakeSession()
    context = ExecutionContext(browser=session)

    result = await GetElementInfoExecutor().execute(
        {
            "selector": "#value",
            "attribute": attribute,
            "variableName": "result",
            "columnName": "结果",
        },
        context,
    )

    assert result.success is True
    assert result.data == expected
    assert context.variables["result"] == expected
    assert context.current_row["结果"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "screenshot_type,expected_full_page",
    [("fullpage", True), ("viewport", False)],
)
async def test_screenshot_preserves_page_modes_and_registers_png(
    tmp_path: Path, screenshot_type: str, expected_full_page: bool
) -> None:
    session = FakeSession()
    artifacts = FakeArtifacts(tmp_path)
    context = ExecutionContext(browser=session, artifacts=artifacts)

    result = await ScreenshotExecutor().execute(
        {
            "screenshotType": screenshot_type,
            "fileNamePattern": "核验_{时间戳}",
            "variableName": "shot",
        },
        context,
    )

    assert result.success is True
    assert session.current.calls[-1] == ("screenshot", (expected_full_page, None))
    assert artifacts.writes[0][0].startswith("核验_")
    assert artifacts.writes[0][0].endswith(".png")
    assert artifacts.writes[0][1].startswith(b"\x89PNG")
    assert context.variables["shot"] == result.data["path"]


@pytest.mark.asyncio
async def test_screenshot_element_mode_and_custom_path_use_artifact_boundary(
    tmp_path: Path,
) -> None:
    session = FakeSession()
    artifacts = FakeArtifacts(tmp_path)
    context = ExecutionContext(browser=session, artifacts=artifacts)

    result = await ScreenshotExecutor().execute(
        {
            "screenshotType": "element",
            "selector": "#target",
            "savePath": "subdirectory",
            "fileNamePattern": "元素_{时间戳}",
        },
        context,
    )

    assert result.success is True
    assert artifacts.writes[0][0].startswith("subdirectory/元素_")
    assert ("screenshot", None) in session.current.locator("#target").calls


@pytest.mark.asyncio
async def test_get_element_info_reports_zero_match_without_outputs() -> None:
    session = FakeSession()
    session.current.locators["#missing"] = FakeLocator(count=0)
    context = ExecutionContext(browser=session)

    result = await GetElementInfoExecutor().execute(
        {
            "selector": "#missing",
            "attribute": "text",
            "variableName": "result",
        },
        context,
    )

    assert result.success is False
    assert result.error == "未找到元素: #missing"
    assert "result" not in context.variables


@pytest.mark.asyncio
async def test_missing_required_values_fail_before_browser_side_effects() -> None:
    session = FakeSession()
    context = ExecutionContext(browser=session)

    results = [
        await OpenPageExecutor().execute({"url": ""}, context),
        await ClickElementExecutor().execute({"selector": ""}, context),
        await InputTextExecutor().execute({"selector": ""}, context),
        await GetElementInfoExecutor().execute({"selector": ""}, context),
    ]

    assert [result.error for result in results] == [
        "URL不能为空",
        "选择器不能为空",
        "选择器不能为空",
        "选择器不能为空",
    ]
    assert session.current.calls == []
    assert frozen_result("missing") == {
        "errors": [
            "URL不能为空",
            "选择器不能为空",
            "选择器不能为空",
            "选择器不能为空",
        ],
        "pageCalls": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("node_type", ["click_element", "get_element_info"])
async def test_attached_timeout_preserves_frozen_visible_fallback(node_type: str) -> None:
    session = FakeSession()
    locator = FakeLocator(fail_wait_states={"attached"})
    session.current.locators["#target"] = locator
    context = ExecutionContext(browser=session)

    if node_type == "click_element":
        result = await ClickElementExecutor().execute({"selector": "#target"}, context)
    else:
        result = await GetElementInfoExecutor().execute(
            {"selector": "#target", "attribute": "text"}, context
        )

    assert result.success is True
    assert [call for call in locator.calls if call[0] == "wait_for"] == [
        ("wait_for", {"state": "attached", "timeout_ms": 30_000}),
        ("wait_for", {"state": "visible", "timeout_ms": 30_000}),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["open", "click", "input", "extract", "screenshot"])
async def test_five_node_behavior_matches_frozen_webrpa(case: str, tmp_path: Path) -> None:
    source = frozen_result(case)
    session = FakeSession()
    context = ExecutionContext(
        variables={"url": "https://example.test", "text": "中文"},
        browser=session,
        artifacts=FakeArtifacts(tmp_path),
        clock=WorkflowClock(lambda: datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)),
    )

    if case == "open":
        result = await OpenPageExecutor().execute(
            {"url": "{url}", "openMode": "current_tab", "waitUntil": "load"}, context
        )
        target = {
            "success": result.success,
            "message": result.message,
            "pageCount": len(session.items),
            "calls": [
                ["goto", [session.current.calls[0][1][0], session.current.calls[0][1][1]]],
                ["front", None],
            ],
        }
    elif case == "click":
        locator = session.current.locator("#button")
        result = await ClickElementExecutor().execute(
            {
                "selector": "#button",
                "clickType": "right",
                "followNewTab": False,
                "timeout": 2,
            },
            context,
        )
        target = {
            "success": result.success,
            "message": result.message,
            "calls": [
                [name, {"state": value["state"], "timeout": value["timeout_ms"]}]
                if name == "wait_for"
                else [name, value]
                for name, value in locator.calls
            ],
        }
    elif case == "input":
        locator = FakeLocator(tag="input")
        session.current.locators["#input"] = locator
        result = await InputTextExecutor().execute(
            {
                "selector": "#input",
                "text": "{text}",
                "clearBefore": True,
                "typeSequential": True,
            },
            context,
        )
        target = {
            "success": result.success,
            "message": result.message,
            "calls": [
                [name, {"state": value["state"], "timeout": value["timeout_ms"]}]
                if name == "wait_for"
                else [name, list(value) if isinstance(value, tuple) else value]
                for name, value in locator.calls
            ],
        }
    elif case == "extract":
        result = await GetElementInfoExecutor().execute(
            {
                "selector": "#value",
                "attribute": "attributes",
                "variableName": "result",
                "columnName": "结果",
            },
            context,
        )
        target = {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "variable": context.variables["result"],
            "column": context.current_row["结果"],
        }
    else:
        result = await ScreenshotExecutor().execute(
            {
                "screenshotType": "viewport",
                "fileNamePattern": "核验_{时间戳}",
                "variableName": "shot",
            },
            context,
        )
        target = {
            "success": result.success,
            "messagePrefix": result.message.split(":", 1)[0],
            "variableMatches": context.variables["shot"] == result.data["path"],
            "fullPage": session.current.calls[-1][1][0],
            "suffix": Path(result.data["path"]).suffix,
        }

    assert target == source


@pytest.mark.asyncio
@pytest.mark.parametrize("node_type", ["open_page", "input_text", "screenshot"])
async def test_runtime_cancels_browser_action_before_following_node(
    node_type: str, tmp_path: Path
) -> None:
    entered = asyncio.Event()
    never = asyncio.Event()
    session = FakeSession()
    original_locator = session.current.locator("#input")
    original_locator.tag = "input"

    async def hang(*_args: Any, **_kwargs: Any) -> Any:
        entered.set()
        await never.wait()

    config: dict[str, Any]
    first: Any
    if node_type == "open_page":
        session.current.goto = hang  # type: ignore[method-assign]
        config = {"url": "https://slow.test", "openMode": "current_tab"}
        first = OpenPageExecutor()
    elif node_type == "input_text":
        original_locator.fill = hang  # type: ignore[method-assign]
        config = {"selector": "#input", "text": "不会完成"}
        first = InputTextExecutor()
    else:
        session.current.screenshot = hang  # type: ignore[method-assign]
        config = {"screenshotType": "viewport"}
        first = ScreenshotExecutor()

    registry = ExecutorRegistry()
    registry.register(type(first))
    registry.register(ClickElementExecutor)
    runtime = WorkflowRuntime(registry)
    token = MutableCancellation()
    task = asyncio.create_task(
        runtime.execute(
            {
                "nodes": [
                    {
                        "id": "first",
                        "type": "moduleNode",
                        "data": {"moduleType": node_type, "config": config},
                    },
                    {
                        "id": "after",
                        "type": "moduleNode",
                        "data": {
                            "moduleType": "click_element",
                            "config": {"selector": "#after"},
                        },
                    },
                ],
                "edges": [{"id": "next", "source": "first", "target": "after"}],
            },
            ExecutionContext(
                browser=session,
                artifacts=FakeArtifacts(tmp_path),
                cancellation=token,
            ),
        )
    )
    await asyncio.wait_for(entered.wait(), timeout=1)
    token.cancelled = True

    with pytest.raises(RunWasCancelled):
        await asyncio.wait_for(task, timeout=1)
    assert session.current.locator("#after").calls == []
