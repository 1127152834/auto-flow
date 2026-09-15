from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.browser import (
    BrowserDownloadPort,
    BrowserLocatorPort,
    BrowserPagePort,
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

    async def wait_for(
        self, *, state: str = "visible", timeout_ms: float | None = None
    ) -> None:
        options: dict[str, Any] = {"state": state}
        if timeout_ms is not None:
            options["timeout"] = timeout_ms
        await self._raw.wait_for(**options)

    async def click(self, **options: Any) -> None:
        await self._raw.click(**options)

    async def fill(self, value: str) -> None:
        await self._raw.fill(value)

    async def press_sequentially(self, value: str) -> None:
        await self._raw.press_sequentially(value)

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
