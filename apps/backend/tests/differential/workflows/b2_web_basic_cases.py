from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


def _canonical_options(options: dict[str, Any]) -> dict[str, Any]:
    result = dict(options)
    if "timeout_ms" in result:
        result["timeout"] = result.pop("timeout_ms")
    return result


class Locator:
    @property
    def first(self) -> Locator:
        return self

    def __init__(self, calls: list[Any], *, fail: bool = False) -> None:
        self.calls = calls
        self.fail = fail

    async def wait_for(self, **options: Any) -> None:
        self.calls.append(["wait_for", _canonical_options(options)])
        if self.fail:
            raise TimeoutError("Timeout fixture")

    async def hover(self, **options: Any) -> None:
        self.calls.append(["hover", _canonical_options(options)])
        if self.fail:
            raise RuntimeError("fixture hover failed")


class ElementHandle:
    def __init__(self, frame: Page | None) -> None:
        self._frame = frame

    async def content_frame(self) -> Page | None:
        return self._frame


class Dialog:
    def __init__(self, dialog_type: str = "prompt", message: str = "请输入") -> None:
        self.type = dialog_type
        self.message = message
        self.calls: list[Any] = []

    async def accept(self, prompt_text: str | None = None) -> None:
        self.calls.append(["accept", prompt_text])

    async def dismiss(self) -> None:
        self.calls.append(["dismiss"])


class Page:
    def __init__(
        self,
        page_id: str,
        url: str,
        title: str,
        *,
        fail: str | None = None,
        result: Any = 7,
    ) -> None:
        self.id = page_id
        self.name = ""
        self.url = url
        self._title = title
        self.fail = fail
        self.result = result
        self.closed = False
        self.calls: list[Any] = []
        self.main_frame: Page = self
        self.frames: list[Page] = [self]
        self.named_frames: dict[str, Page] = {}
        self.selector_frames: dict[str, Page | None] = {}
        self.fail_selectors: set[str] = set()
        self.dialog: Dialog | None = None
        self._dialog_tasks: list[asyncio.Task[Any]] = []

    async def title(self) -> str:
        if self.fail == "title":
            raise RuntimeError("fixture title failed")
        return self._title

    def locator(self, selector: str) -> Locator:
        return Locator(
            self.calls,
            fail=self.fail == "locator" or selector in self.fail_selectors,
        )

    async def close(self) -> None:
        self.calls.append(["close"])
        if self.fail == "close":
            raise RuntimeError("fixture close failed")
        self.closed = True

    async def reload(self, **options: Any) -> object | None:
        self.calls.append(["reload", _canonical_options(options)])
        if self.fail == "reload":
            raise RuntimeError("fixture reload failed")
        return None if self.fail == "reload_none" else object()

    async def go_back(self, **options: Any) -> object | None:
        self.calls.append(["go_back", _canonical_options(options)])
        if self.fail == "go_back":
            raise RuntimeError("fixture back failed")
        return None if self.fail == "back_none" else object()

    async def go_forward(self, **options: Any) -> object | None:
        self.calls.append(["go_forward", _canonical_options(options)])
        if self.fail == "go_forward":
            raise RuntimeError("fixture forward failed")
        return None if self.fail == "forward_none" else object()

    async def goto(self, url: str, **options: Any) -> object | None:
        self.calls.append(["goto", url, _canonical_options(options)])
        if self.fail == "goto":
            raise RuntimeError("fixture goto failed")
        if self.fail != "goto_none":
            self.url = url
            return object()
        return None

    async def evaluate(self, code: str) -> Any:
        self.calls.append(["evaluate", code])
        if self.fail == "evaluate":
            raise RuntimeError("fixture evaluate failed")
        if code == "document.body.innerHTML":
            return "<p>frame</p>"
        return self.result

    async def wait_for_load_state(self, state: str, **options: Any) -> None:
        self.calls.append(["load", state, _canonical_options(options)])
        if self.fail == "load":
            raise TimeoutError("fixture load timeout")

    def frame(self, *, name: str) -> Page | None:
        return self.named_frames.get(name)

    async def wait_for_selector(self, selector: str, **options: Any) -> ElementHandle:
        self.calls.append(["wait_for_selector", selector, _canonical_options(options)])
        if self.fail == "selector":
            raise TimeoutError("fixture selector timeout")
        return ElementHandle(self.selector_frames.get(selector))

    async def query_selector_all(self, selector: str) -> list[ElementHandle]:
        self.calls.append(["query_selector_all", selector])
        return []

    def on(self, event: str, callback: Any) -> None:
        self.calls.append(["on", event])
        if event == "dialog" and self.dialog is not None:
            self._dialog_tasks.append(asyncio.create_task(callback(self.dialog)))

    def remove_listener(self, event: str, _callback: Any) -> None:
        self.calls.append(["remove_listener", event])


class BrowserContext:
    def __init__(self, pages: list[Page]) -> None:
        self.pages = pages


class Session:
    def __init__(self, pages: list[Page], current: Page | None = None) -> None:
        self._pages = pages
        self._current = current or (pages[-1] if pages else None)

    def current_page(self) -> Page:
        if self._current is None or self._current.closed:
            raise RuntimeError("fixture current page unavailable")
        return self._current

    def pages(self) -> tuple[Page, ...]:
        return tuple(self._pages)

    def select_page(self, page_id: str) -> Page:
        self._current = next(page for page in self._pages if page.id == page_id)
        return self._current


class Context:
    def __init__(
        self, pages: list[Page], *, variables: dict[str, Any] | None = None
    ) -> None:
        self.variables = variables or {}
        self.browser_context = BrowserContext(pages) if pages else None
        self.page = pages[-1] if pages else None
        self.browser = Session(pages, self.page) if pages else None
        self._in_iframe = False
        self._main_page: Page | None = None
        self._iframe_locator: dict[str, Any] | None = None
        self._current_frame: Page | None = None

    def resolve_value(self, value: Any) -> Any:
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            return self.variables.get(value[1:-1], value)
        return value

    def set_variable(self, name: str, value: Any, **_options: Any) -> None:
        self.variables[name] = value

    async def switch_to_latest_page(self) -> bool:
        if self._in_iframe:
            return False
        if self.page is None and self.browser_context and self.browser_context.pages:
            self.page = self.browser_context.pages[-1]
            if self.browser:
                self.browser.select_page(self.page.id)
            return True
        return False

    async def get_current_frame(self) -> Page | None:
        return self._current_frame if self._in_iframe else self.page


@dataclass
class Scenario:
    executor: str
    config: dict[str, Any]
    context: Context


def _scenario(case: str) -> Scenario:
    first = Page("p1", "https://one.test/start", "First")
    second = Page("p2", "https://two.test/app", "Second App")
    pages = [first, second]
    config: dict[str, Any] = {}
    executor, _, branch = case.partition(":")

    if branch == "missing":
        pages = []
    elif executor == "close_page" and branch == "error":
        second.fail = "close"
    elif executor == "refresh_page":
        config = {"waitUntil": "{state}"}
        variables = {"state": "networkidle"}
        if branch == "error":
            second.fail = "reload"
        return Scenario(executor, config, Context(pages, variables=variables))
    elif executor == "go_back":
        config = {"waitUntil": "domcontentloaded"}
        if branch == "none":
            second.fail = "back_none"
        elif branch == "error":
            second.fail = "go_back"
    elif executor == "go_forward":
        if branch == "none":
            second.fail = "forward_none"
        elif branch == "error":
            second.fail = "go_forward"
    elif executor == "hover_element":
        config = {
            "selector": "{selector}",
            "hoverDuration": 0,
            "force": "true",
            "timeout": 2,
        }
        if branch == "empty":
            config["selector"] = ""
        if branch == "error":
            second.fail = "locator"
        if branch == "hints":
            config.update({"selector": "#old", "selectorHints": {"id": "stable"}})
            second.fail_selectors.add("#old")
        return Scenario(
            executor, config, Context(pages, variables={"selector": "#target"})
        )
    elif executor == "wait_element":
        config = {
            "selector": "#target",
            "waitCondition": branch or "visible",
            "waitTimeout": 2,
        }
        if branch == "error":
            second.fail = "locator"
            config["waitCondition"] = "visible"
        if branch == "empty":
            config["selector"] = ""
        if branch == "hints":
            config.update(
                {
                    "selector": "#old",
                    "waitCondition": "visible",
                    "selectorHints": {"id": "stable"},
                }
            )
            second.fail_selectors.add("#old")
    elif executor == "handle_dialog":
        if branch in {"accept", "dismiss", "other"}:
            second.dialog = Dialog()
            config = {
                "dialogAction": branch if branch != "other" else "later",
                "promptText": "答案",
                "saveMessage": "dialog_message",
            }
    elif executor == "inject_javascript":
        config = {
            "javascriptCode": "return vars.value + 1",
            "saveResult": "js_result",
            "injectMode": branch or "current",
        }
        variables = {"value": 6, "opaque": {1, 2}}
        if branch == "partial":
            config["injectMode"] = "all"
            second.fail = "evaluate"
        elif branch == "url":
            config.update({"injectMode": "url_match", "targetUrl": "two.*app"})
        elif branch == "invalid_url":
            config.update({"injectMode": "url_match", "targetUrl": "["})
        elif branch == "index_error":
            config.update({"injectMode": "index", "targetIndex": "9"})
        elif branch == "index":
            config.update({"injectMode": "index", "targetIndex": "0"})
        elif branch == "url_empty":
            config.update({"injectMode": "url_match", "targetUrl": ""})
        elif branch == "unsupported":
            config["injectMode"] = "other"
        elif branch == "empty":
            config["javascriptCode"] = ""
        return Scenario(executor, config, Context(pages, variables=variables))
    elif executor == "switch_iframe":
        child = Page("frame-1", "https://frame.test", "Frame")
        child.name = "checkout"
        first.frames.append(child)
        first.named_frames["checkout"] = child
        first.selector_frames["#checkout"] = child
        pages = [first]
        if branch == "index":
            config = {"locateBy": "index", "iframeIndex": 0}
        elif branch == "range":
            config = {"locateBy": "index", "iframeIndex": 3}
        elif branch == "name":
            config = {"locateBy": "name", "iframeName": "checkout"}
        elif branch == "name_id":
            first.named_frames.clear()
            first.selector_frames['iframe[id="checkout"]'] = child
            config = {"locateBy": "name", "iframeName": "checkout"}
        elif branch == "name_empty":
            config = {"locateBy": "name", "iframeName": ""}
        elif branch == "selector":
            config = {"locateBy": "selector", "iframeSelector": "#checkout"}
        elif branch == "selector_not_iframe":
            first.selector_frames["#other"] = None
            config = {"locateBy": "selector", "iframeSelector": "#other"}
        elif branch == "selector_error":
            first.fail = "selector"
            config = {"locateBy": "selector", "iframeSelector": "#absent"}
        else:
            config = {"locateBy": "other"}
    elif executor == "switch_to_main" and branch == "after_frame":
        child = Page("frame-1", "https://frame.test", "Frame")
        first.frames.append(child)
        pages = [first]
        context = Context(pages)
        context._in_iframe = True
        context._main_page = first
        context._current_frame = child
        context.page = child
        assert context.browser is not None
        context.browser._autoflow_frame_state = {
            "in_iframe": True,
            "main_page": first,
            "current_frame": child,
            "locator": None,
        }
        return Scenario(executor, config, context)
    elif executor == "use_opened_page":
        if branch == "title":
            config = {"pageIdentifier": "first", "matchMode": "title"}
        elif branch == "url":
            config = {"pageIdentifier": "one.test", "matchMode": "url"}
        elif branch == "navigate_empty":
            config = {"action": "navigate", "url": ""}
        elif branch == "navigate":
            config = {
                "action": "navigate",
                "url": "https://target.test",
                "waitUntil": "networkidle",
            }
        elif branch == "navigate_none":
            config = {"action": "navigate", "url": "https://target.test"}
            second.fail = "goto_none"
        elif branch == "refresh_none":
            config = {"action": "refresh"}
            second.fail = "reload_none"
        elif branch == "refresh":
            config = {"action": "refresh", "waitUntil": "domcontentloaded"}
        elif branch == "skip_bad_title":
            first.fail = "title"
            config = {"pageIdentifier": "second", "matchMode": "title"}
        elif branch == "unknown":
            config = {"action": "other"}
        elif branch == "no_match":
            config = {"pageIdentifier": "absent", "matchMode": "title"}

    return Scenario(executor, config, Context(pages))


def _clean_calls(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_calls(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_calls(item) for item in value]
    if isinstance(value, set):
        return str(value)
    if type(value) is object:
        return "<response>"
    return value


async def run_case(case: str, executors: dict[str, type[Any]]) -> dict[str, Any]:
    scenario = _scenario(case)
    result = await executors[scenario.executor]().execute(
        scenario.config, scenario.context
    )
    pages = (
        scenario.context.browser_context.pages
        if scenario.context.browser_context
        else []
    )
    for page in pages:
        if page._dialog_tasks:
            await asyncio.gather(*page._dialog_tasks)
    payload = {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
        "variables": scenario.context.variables,
        "config": scenario.config,
        "pages": [
            {"id": page.id, "url": page.url, "closed": page.closed, "calls": page.calls}
            for page in pages
        ],
    }
    return _clean_calls(payload)
