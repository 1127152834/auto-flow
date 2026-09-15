from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class Page:
    def __init__(
        self,
        page_id: str,
        title: str,
        url: str,
        *,
        title_error: str | None = None,
    ) -> None:
        self.id = page_id
        self._title = title
        self.url = url
        self.title_error = title_error
        self.calls: list[Any] = []

    async def title(self) -> str:
        self.calls.append(["title"])
        if self.title_error:
            raise RuntimeError(self.title_error)
        return self._title

    async def bring_to_front(self) -> None:
        self.calls.append(["front"])


class BrowserContext:
    def __init__(self, pages: list[Page]) -> None:
        self.pages = pages


class Session:
    def __init__(self, pages: list[Page], current: Page | None) -> None:
        self._pages = pages
        self._current = current
        self._active = current
        self._manual_tab_switch = False

    def pages(self) -> tuple[Page, ...]:
        return tuple(self._pages)

    def current_page(self) -> Page:
        if self._current is None:
            raise RuntimeError("fixture current page missing")
        return self._current

    def active_page(self) -> Page:
        if self._active is None:
            raise RuntimeError("fixture active page missing")
        return self._active

    def select_page(self, page_id: str) -> Page:
        self._current = next(page for page in self._pages if page.id == page_id)
        self._active = self._current
        return self._current


class Context:
    def __init__(
        self,
        pages: list[Page],
        *,
        current: Page | None,
        variables: dict[str, Any] | None = None,
        with_browser: bool = True,
    ) -> None:
        self.variables = variables or {}
        self.browser_context = BrowserContext(pages) if with_browser else None
        self.browser = Session(pages, current) if with_browser else None
        self.page = current
        self._manual_tab_switch = False

    async def get_current_frame(self) -> Page | None:
        return self.page

    def resolve_value(self, value: Any) -> Any:
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            return self.variables.get(value[1:-1], value)
        return value

    def set_variable(self, name: str, value: Any, **_options: Any) -> None:
        self.variables[name] = value


@dataclass
class Scenario:
    config: dict[str, Any]
    context: Context


def scenario(case: str) -> Scenario:
    first = Page("p1", "Alpha Home", "https://one.test/home")
    second = Page("p2", "Beta Console", "https://two.test/console")
    third = Page("p3", "Gamma Report", "https://three.test/report")
    pages = [first, second, third]
    current: Page | None = second
    config: dict[str, Any] = {}

    if case == "missing_browser":
        return Scenario(config, Context([], current=None, with_browser=False))
    if case == "empty_pages":
        return Scenario(config, Context([], current=None))
    if case == "index_variables":
        config = {
            "switchMode": "{mode}",
            "tabIndex": "{index}",
            "saveIndexVariable": "chosen_index",
            "saveTitleVariable": "chosen_title",
            "saveUrlVariable": "chosen_url",
        }
        return Scenario(
            config,
            Context(
                pages,
                current=current,
                variables={"mode": "index", "index": "2"},
            ),
        )
    if case == "index_bad":
        config = {"switchMode": "index", "tabIndex": "bad"}
    elif case == "index_range":
        config = {"switchMode": "index", "tabIndex": -1}
    elif case == "title_empty":
        config = {"switchMode": "title", "tabTitle": ""}
    elif case == "title_error":
        first.title_error = "fixture title failed"
        config = {"switchMode": "title", "tabTitle": "Beta Console"}
    elif case.startswith("title_"):
        match_mode = case.removeprefix("title_")
        patterns = {
            "exact": "Beta Console",
            "contains": "Console",
            "startswith": "Beta",
            "endswith": "Console",
            "regex": r"^Beta\s+Con.*$",
            "invalid_regex": "[",
            "missing": "Absent",
        }
        config = {
            "switchMode": "title",
            "matchMode": "regex" if match_mode == "invalid_regex" else match_mode,
            "tabTitle": patterns[match_mode],
        }
    elif case == "url_empty":
        config = {"switchMode": "url", "tabUrl": ""}
    elif case.startswith("url_"):
        match_mode = case.removeprefix("url_")
        patterns = {
            "exact": "https://two.test/console",
            "contains": "two.test",
            "startswith": "https://two",
            "endswith": "/console",
            "regex": r"two\.test/.+",
            "invalid_regex": "[",
            "missing": "absent.test",
        }
        config = {
            "switchMode": "url",
            "matchMode": "regex" if match_mode == "invalid_regex" else match_mode,
            "tabUrl": patterns[match_mode],
        }
    elif case in {"next", "prev", "first", "last"}:
        config = {"switchMode": case}
    elif case == "next_unknown_current":
        current = Page("frame", "Frame", "https://frame.test")
        config = {"switchMode": "next"}
    elif case == "prev_unknown_current":
        current = Page("frame", "Frame", "https://frame.test")
        config = {"switchMode": "prev"}
    elif case == "unsupported":
        config = {"switchMode": "middle"}
    else:
        raise ValueError(case)
    return Scenario(config, Context(pages, current=current))


async def run_case(case: str, executor_type: type[Any]) -> dict[str, Any]:
    item = scenario(case)
    result = await executor_type().execute(item.config, item.context)
    pages = item.context.browser_context.pages if item.context.browser_context else []
    active_id = item.context.page.id if item.context.page is not None else None
    session_manual = (
        item.context.browser._manual_tab_switch
        if item.context.browser is not None
        else False
    )
    return {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
        "variables": item.context.variables,
        "active_id": active_id,
        "manual": item.context._manual_tab_switch or session_manual,
        "calls": {page.id: page.calls for page in pages},
    }
