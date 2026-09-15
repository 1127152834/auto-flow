from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class WorkflowBrowserError(Exception):
    pass


class WorkflowBrowserBusy(WorkflowBrowserError):
    pass


class UnknownPage(WorkflowBrowserError):
    pass


class CurrentPageClosed(WorkflowBrowserError):
    pass


class BrowserLocatorPort(Protocol):
    def locator(self, selector: str) -> BrowserLocatorPort: ...

    async def count(self) -> int: ...

    async def evaluate(self, expression: str) -> Any: ...

    async def is_visible(self) -> bool: ...

    async def wait_for(
        self, *, state: str = "visible", timeout_ms: float | None = None
    ) -> None: ...

    async def click(self, **options: Any) -> None: ...

    async def double_click(self, **options: Any) -> None: ...

    async def clear(self) -> None: ...

    async def fill(self, value: str) -> None: ...

    async def press_sequentially(self, value: str, *, delay_ms: float = 0) -> None: ...

    async def type_text(self, value: str, *, delay_ms: float = 0) -> None: ...

    async def text_content(self) -> str | None: ...

    async def inner_html(self) -> str: ...

    async def input_value(self) -> str: ...

    async def get_attribute(self, name: str) -> str | None: ...

    async def screenshot(self, *, path: str | None = None) -> bytes: ...


class BrowserDownloadPort(Protocol):
    @property
    def suggested_filename(self) -> str: ...

    async def save_as(self, path: Path) -> None: ...


class BrowserRequestWatchPort(Protocol):
    @property
    def active(self) -> bool: ...

    @property
    def overflowed(self) -> bool: ...

    def captured_requests(self) -> list[dict[str, Any]]: ...

    def matching_requests(self, url_pattern: str) -> list[dict[str, Any]]: ...

    def stop(self) -> None: ...


class BrowserPagePort(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def url(self) -> str: ...

    @property
    def closed(self) -> bool: ...

    async def goto(
        self, url: str, *, wait_until: str, timeout_ms: float
    ) -> None: ...

    async def wait_for_load_state(self, state: str, *, timeout_ms: float) -> None: ...

    async def bring_to_front(self) -> None: ...

    async def keyboard_press(self, key: str) -> None: ...

    async def keyboard_type(self, value: str) -> None: ...

    def locator(self, selector: str) -> BrowserLocatorPort: ...

    async def screenshot(
        self, *, full_page: bool = False, path: str | None = None
    ) -> bytes: ...

    async def capture_download(
        self, action: Callable[[], Awaitable[None]]
    ) -> BrowserDownloadPort: ...

    def begin_request_watch(
        self, *, filter_type: str, url_pattern: str
    ) -> BrowserRequestWatchPort: ...


class BrowserSessionPort(Protocol):
    def current_page(self) -> BrowserPagePort: ...

    def pages(self) -> tuple[BrowserPagePort, ...]: ...

    async def new_page(self) -> BrowserPagePort: ...

    def select_page(self, page_id: str) -> BrowserPagePort: ...

    def begin_new_page_watch(self) -> object: ...

    async def settle_new_page_watch(
        self, watch: object, *, follow: bool, wait_ms: int = 3000
    ) -> BrowserPagePort | None: ...

    async def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class WorkflowWorkerSession:
    run_id: str
    profile_id: str
    pid: int
    child_pid: int | None = None
