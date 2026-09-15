from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.browser import (
    BrowserDownloadPort,
    BrowserLocatorPort,
    BrowserPagePort,
    BrowserRequestWatchPort,
    CurrentPageClosed,
    UnknownPage,
)
from autoflow.providers.browser.proxy_relay import BrowserProxyRelay
from autoflow.providers.browser.worker import browser_launch_options


def format_selector(selector: str) -> str:
    stripped = selector.strip()
    if stripped.startswith(("/", "(")) and not stripped.startswith("xpath="):
        return f"xpath={stripped}"
    return selector


class CloakBrowserWorkflowLocator(BrowserLocatorPort):
    def __init__(self, raw: Any) -> None:
        self._raw = raw.first

    def locator(self, selector: str) -> CloakBrowserWorkflowLocator:
        return CloakBrowserWorkflowLocator(self._raw.locator(selector))

    async def count(self) -> int:
        return int(await self._raw.count())

    async def evaluate(self, expression: str) -> Any:
        return await self._raw.evaluate(expression)

    async def is_visible(self) -> bool:
        return bool(await self._raw.is_visible())

    async def wait_for(
        self, *, state: str = "visible", timeout_ms: float | None = None
    ) -> None:
        options: dict[str, Any] = {"state": state}
        if timeout_ms is not None:
            options["timeout"] = timeout_ms
        await self._raw.wait_for(**options)

    async def click(self, **options: Any) -> None:
        await self._raw.click(**options)

    async def double_click(self, **options: Any) -> None:
        await self._raw.dblclick(**options)

    async def clear(self) -> None:
        await self._raw.clear()

    async def fill(self, value: str) -> None:
        await self._raw.fill(value)

    async def press_sequentially(self, value: str, *, delay_ms: float = 0) -> None:
        await self._raw.press_sequentially(value, delay=delay_ms)

    async def type_text(self, value: str, *, delay_ms: float = 0) -> None:
        await self._raw.type(value, delay=delay_ms)

    async def text_content(self) -> str | None:
        return await self._raw.text_content()

    async def inner_html(self) -> str:
        return await self._raw.inner_html()

    async def input_value(self) -> str:
        return await self._raw.input_value()

    async def get_attribute(self, name: str) -> str | None:
        return await self._raw.get_attribute(name)

    async def screenshot(self, *, path: str | None = None) -> bytes:
        options = {"path": path} if path is not None else {}
        return await self._raw.screenshot(**options)


class CloakBrowserWorkflowDownload(BrowserDownloadPort):
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    @property
    def suggested_filename(self) -> str:
        value = self._raw.suggested_filename
        return value if isinstance(value, str) else "download"

    async def save_as(self, path: Path) -> None:
        await self._raw.save_as(str(path))


_SENSITIVE_REQUEST_HEADERS = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}
)
_MAX_CAPTURED_REQUESTS = 10_000
_MAX_CAPTURED_REQUEST_BYTES = 8 * 1024 * 1024


class CloakBrowserWorkflowRequestWatch(BrowserRequestWatchPort):
    def __init__(self, raw_page: Any, *, filter_type: str, url_pattern: str) -> None:
        self._raw_page = raw_page
        self._filter_type = filter_type
        self._url_pattern = url_pattern.lower()
        self._captured: list[dict[str, Any]] = []
        self._captured_bytes = 0
        self._active = True
        self._overflowed = False
        self._raw_page.on("request", self._on_request)

    @property
    def active(self) -> bool:
        return self._active

    @property
    def overflowed(self) -> bool:
        return self._overflowed

    def _on_request(self, request: Any) -> None:
        if not self._active or self._overflowed:
            return
        try:
            url = str(request.url)
            resource_type = str(request.resource_type)
            if self._filter_type == "api" and resource_type not in {"fetch", "xhr"}:
                return
            if self._filter_type == "img" and resource_type != "image":
                return
            if self._filter_type == "media" and resource_type not in {
                "media",
                "video",
                "audio",
            }:
                return
            if self._filter_type == "m3u8" and ".m3u8" not in url.lower():
                return
            if self._url_pattern and self._url_pattern not in url.lower():
                return

            raw_headers = request.headers if hasattr(request, "headers") else {}
            headers = {
                str(key): (
                    "[已隐藏]"
                    if str(key).lower() in _SENSITIVE_REQUEST_HEADERS
                    else str(value)
                )
                for key, value in dict(raw_headers).items()
            }
            captured = {
                "url": url,
                "method": str(request.method),
                "resource_type": resource_type,
                "timestamp": time.time(),
                "headers": headers,
            }
            size = len(
                json.dumps(captured, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
            if (
                len(self._captured) >= _MAX_CAPTURED_REQUESTS
                or self._captured_bytes + size > _MAX_CAPTURED_REQUEST_BYTES
            ):
                self._overflowed = True
                return
            self._captured.append(captured)
            self._captured_bytes += size
        except Exception:  # noqa: BLE001 -- request callbacks cannot fail page work.
            return

    def captured_requests(self) -> list[dict[str, Any]]:
        return [
            {**request, "headers": dict(request.get("headers", {}))}
            for request in self._captured
        ]

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        try:
            self._raw_page.remove_listener("request", self._on_request)
        except Exception:  # noqa: BLE001,S110 -- page may already be closed.
            pass


class CloakBrowserWorkflowPage(BrowserPagePort):
    def __init__(self, page_id: str, raw: Any) -> None:
        self._id = page_id
        self._raw = raw

    @property
    def id(self) -> str:
        return self._id

    @property
    def url(self) -> str:
        value = self._raw.url
        return value if isinstance(value, str) else ""

    @property
    def closed(self) -> bool:
        return bool(self._raw.is_closed())

    async def goto(
        self, url: str, *, wait_until: str, timeout_ms: float
    ) -> None:
        await self._raw.goto(url, wait_until=wait_until, timeout=timeout_ms)

    async def wait_for_load_state(self, state: str, *, timeout_ms: float) -> None:
        await self._raw.wait_for_load_state(state, timeout=timeout_ms)

    async def bring_to_front(self) -> None:
        await self._raw.bring_to_front()

    async def keyboard_press(self, key: str) -> None:
        await self._raw.keyboard.press(key)

    async def keyboard_type(self, value: str) -> None:
        await self._raw.keyboard.type(value)

    def locator(self, selector: str) -> CloakBrowserWorkflowLocator:
        return CloakBrowserWorkflowLocator(self._raw.locator(format_selector(selector)))

    async def screenshot(
        self, *, full_page: bool = False, path: str | None = None
    ) -> bytes:
        options: dict[str, Any] = {"full_page": full_page}
        if path is not None:
            options["path"] = path
        return await self._raw.screenshot(**options)

    async def capture_download(
        self, action: Callable[[], Awaitable[None]]
    ) -> CloakBrowserWorkflowDownload:
        async with self._raw.expect_download() as download_info:
            await action()
        return CloakBrowserWorkflowDownload(await download_info.value)

    def begin_request_watch(
        self, *, filter_type: str, url_pattern: str
    ) -> CloakBrowserWorkflowRequestWatch:
        return CloakBrowserWorkflowRequestWatch(
            self._raw, filter_type=filter_type, url_pattern=url_pattern
        )


class CloakBrowserWorkflowSession:
    def __init__(self, context: Any) -> None:
        self._context = context
        self._pages: dict[int, CloakBrowserWorkflowPage] = {}
        self._current_id: str | None = None
        self._closed = False
        existing = self._synchronize_pages()
        if existing:
            self._current_id = existing[0].id

    @classmethod
    def from_context(cls, context: Any) -> CloakBrowserWorkflowSession:
        return cls(context)

    def _synchronize_pages(self) -> list[CloakBrowserWorkflowPage]:
        result: list[CloakBrowserWorkflowPage] = []
        for raw in self._context.pages:
            identity = id(raw)
            page = self._pages.get(identity)
            if page is None:
                page = CloakBrowserWorkflowPage(f"page-{uuid4()}", raw)
                self._pages[identity] = page
            result.append(page)
        return result

    def current_page(self) -> CloakBrowserWorkflowPage:
        self._synchronize_pages()
        current = next(
            (page for page in self._pages.values() if page.id == self._current_id),
            None,
        )
        if current is None:
            raise UnknownPage("当前页面不存在")
        if current.closed:
            raise CurrentPageClosed("当前页面已经关闭")
        return current

    def pages(self) -> tuple[CloakBrowserWorkflowPage, ...]:
        return tuple(self._synchronize_pages())

    async def new_page(self) -> CloakBrowserWorkflowPage:
        raw = await self._context.new_page()
        pages = self._synchronize_pages()
        page = next(page for page in pages if page._raw is raw)
        self._current_id = page.id
        return page

    def select_page(self, page_id: str) -> CloakBrowserWorkflowPage:
        page = next((item for item in self._synchronize_pages() if item.id == page_id), None)
        if page is None:
            raise UnknownPage(f"页面 {page_id} 不存在")
        if page.closed:
            raise CurrentPageClosed(f"页面 {page_id} 已经关闭")
        self._current_id = page.id
        return page

    def begin_new_page_watch(self) -> _NewPageWatch:
        watch = _NewPageWatch()

        def on_page(raw: Any) -> None:
            watch.pages.append(raw)

        self._context.on("page", on_page)
        watch.listener = on_page
        return watch

    async def settle_new_page_watch(
        self, watch: object, *, follow: bool, wait_ms: int = 3000
    ) -> CloakBrowserWorkflowPage | None:
        if not isinstance(watch, _NewPageWatch):
            return None
        try:
            if follow and not watch.pages:
                waited = 0
                while waited < wait_ms and not watch.pages:
                    await asyncio.sleep(0.1)
                    waited += 100
            if not watch.pages or not follow:
                return None
            raw = watch.pages[-1]
            pages = self._synchronize_pages()
            page = next((item for item in pages if item._raw is raw), None)
            if page is None:
                raise UnknownPage("新页面不存在")
            try:
                await page.wait_for_load_state("domcontentloaded", timeout_ms=10_000)
            except Exception:  # noqa: BLE001,S110 -- follow does not require load success.
                pass
            self._current_id = page.id
            return page
        finally:
            if watch.listener is not None:
                self._context.remove_listener("page", watch.listener)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._context.close()


@asynccontextmanager
async def launch_workflow_session(
    command: dict[str, Any],
) -> AsyncIterator[CloakBrowserWorkflowSession]:
    from cloakbrowser import launch_context_async  # type: ignore[import-untyped]

    upstream_proxy = command.get("proxy")
    relay = BrowserProxyRelay(upstream_proxy) if isinstance(upstream_proxy, dict) else None
    relay_value = relay.__enter__() if relay is not None else None
    context = None
    session = None
    try:
        options = browser_launch_options(
            command, headless=bool(command.get("headless", False))
        )
        options["proxy"] = {"server": relay_value.url} if relay_value else None
        context = await launch_context_async(**options)
        if not context.pages:
            await context.new_page()
        session = CloakBrowserWorkflowSession.from_context(context)
        yield session
    finally:
        try:
            if session is not None:
                await session.close()
            elif context is not None:
                await context.close()
        finally:
            if relay is not None:
                relay.__exit__(None, None, None)


@dataclass(slots=True)
class _NewPageWatch:
    pages: list[Any] = field(default_factory=list)
    listener: Any = None
