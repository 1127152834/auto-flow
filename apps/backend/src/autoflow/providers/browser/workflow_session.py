from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from autoflow.domain.workflows.browser import (
    BrowserDownloadPort,
    BrowserElementHandlePort,
    BrowserLocatorPort,
    BrowserMousePort,
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
        self._collection = raw
        self._raw = raw.first

    @property
    def first(self) -> CloakBrowserWorkflowLocator:
        return CloakBrowserWorkflowLocator(self._collection.first)

    def locator(self, selector: str) -> CloakBrowserWorkflowLocator:
        return CloakBrowserWorkflowLocator(self._raw.locator(selector))

    def nth(self, index: int) -> CloakBrowserWorkflowLocator:
        return CloakBrowserWorkflowLocator(self._collection.nth(index))

    async def count(self) -> int:
        return int(await self._collection.count())

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

    async def inner_text(self) -> str:
        return str(await self._raw.inner_text())

    async def select_option(self, **options: Any) -> None:
        await self._raw.select_option(**options)

    async def check(self) -> None:
        await self._raw.check()

    async def uncheck(self) -> None:
        await self._raw.uncheck()

    async def drag_to(self, target: BrowserLocatorPort) -> None:
        if not isinstance(target, CloakBrowserWorkflowLocator):
            raise TypeError("拖拽目标不属于当前浏览器会话")
        await self._raw.drag_to(target._raw)

    async def bounding_box(self) -> dict[str, float] | None:
        value = await self._raw.bounding_box()
        return dict(value) if value is not None else None

    async def set_input_files(self, path: str) -> None:
        await self._raw.set_input_files(path)

    async def hover(self, **options: Any) -> None:
        playwright_options = dict(options)
        if "timeout_ms" in playwright_options:
            playwright_options["timeout"] = playwright_options.pop("timeout_ms")
        await self._raw.hover(**playwright_options)


class CloakBrowserWorkflowMouse(BrowserMousePort):
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    async def move(self, x: float, y: float, **options: Any) -> None:
        await self._raw.move(x, y, **options)

    async def down(self) -> None:
        await self._raw.down()

    async def up(self) -> None:
        await self._raw.up()

    async def wheel(self, delta_x: float, delta_y: float) -> None:
        await self._raw.wheel(delta_x, delta_y)

    async def click(
        self,
        x: float,
        y: float,
        *,
        button: str = "left",
        click_count: int = 1,
    ) -> None:
        await self._raw.click(x, y, button=button, click_count=click_count)


class CloakBrowserWorkflowElementHandle(BrowserElementHandlePort):
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    async def content_frame(self) -> CloakBrowserWorkflowPage | None:
        raw_frame = await self._raw.content_frame()
        return (
            CloakBrowserWorkflowPage(f"frame-{id(raw_frame)}", raw_frame)
            if raw_frame is not None
            else None
        )


class CloakBrowserWorkflowDownload(BrowserDownloadPort):
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    @property
    def suggested_filename(self) -> str:
        value = self._raw.suggested_filename
        return value if isinstance(value, str) else "download"

    async def save_as(self, path: Path) -> None:
        await self._raw.save_as(str(path))


_SAFE_REQUEST_HEADERS = frozenset(
    {
        "accept",
        "accept-encoding",
        "accept-language",
        "cache-control",
        "content-length",
        "content-type",
        "origin",
        "pragma",
        "range",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "user-agent",
        "x-requested-with",
    }
)
_SENSITIVE_QUERY_MARKERS = (
    "api_key",
    "apikey",
    "auth",
    "code",
    "credential",
    "jwt",
    "key",
    "license",
    "password",
    "pwd",
    "secret",
    "session",
    "sig",
    "token",
)
_MAX_CAPTURED_REQUESTS = 10_000
_MAX_CAPTURED_REQUEST_BYTES = 8 * 1024 * 1024


def browser_url_is_sensitive(raw_url: str) -> bool:
    try:
        parts = urlsplit(raw_url)
        return bool(parts.username or parts.password) or any(
            any(marker in key.lower() for marker in _SENSITIVE_QUERY_MARKERS)
            for key, _value in parse_qsl(parts.query, keep_blank_values=True)
        )
    except (TypeError, ValueError):
        return False


def redact_browser_url(raw_url: str) -> str:
    try:
        parts = urlsplit(raw_url)
        hostname = parts.hostname
        if not hostname:
            return "[已隐藏的URL]"
        safe_hostname = f"[{hostname}]" if ":" in hostname else hostname
        netloc = safe_hostname
        if parts.port is not None:
            netloc = f"{netloc}:{parts.port}"
        query = urlencode(
            [
                (
                    key,
                    "[已隐藏]"
                    if any(marker in key.lower() for marker in _SENSITIVE_QUERY_MARKERS)
                    else value,
                )
                for key, value in parse_qsl(parts.query, keep_blank_values=True)
            ],
            doseq=True,
        )
        return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))
    except (TypeError, ValueError):
        return "[已隐藏的URL]"


def redact_browser_error(error: object, *raw_urls: str) -> str:
    message = str(error)
    for raw_url in sorted(set(raw_urls), key=len, reverse=True):
        if raw_url:
            message = message.replace(raw_url, redact_browser_url(raw_url))
    return message


class CloakBrowserWorkflowRequestWatch(BrowserRequestWatchPort):
    def __init__(self, raw_page: Any, *, filter_type: str, url_pattern: str) -> None:
        self._raw_page = raw_page
        self._filter_type = filter_type
        self._url_pattern = url_pattern.lower()
        self._captured: list[dict[str, Any]] = []
        self._match_urls: list[str] = []
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
                    str(value)
                    if str(key).lower() in _SAFE_REQUEST_HEADERS
                    else "[已隐藏]"
                )
                for key, value in dict(raw_headers).items()
            }
            captured = {
                "url": redact_browser_url(url),
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
            self._match_urls.append(url)
            self._captured_bytes += size
        except Exception:  # noqa: BLE001 -- request callbacks cannot fail page work.
            return

    def captured_requests(self) -> list[dict[str, Any]]:
        return [
            {**request, "headers": dict(request.get("headers", {}))}
            for request in self._captured
        ]

    def matching_requests(self, url_pattern: str) -> list[dict[str, Any]]:
        normalized = url_pattern.lower()
        return [
            {**request, "headers": dict(request.get("headers", {}))}
            for raw_url, request in zip(self._match_urls, self._captured, strict=True)
            if normalized in raw_url.lower()
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
        if hasattr(self._raw, "is_closed"):
            return bool(self._raw.is_closed())
        raw_page = getattr(self._raw, "page", None)
        return bool(raw_page.is_closed()) if raw_page is not None else False

    def _top_level_page(self) -> Any:
        return self._raw if not hasattr(self._raw, "page") else self._raw.page

    @property
    def mouse(self) -> CloakBrowserWorkflowMouse:
        raw_page = self._top_level_page()
        return CloakBrowserWorkflowMouse(raw_page.mouse)

    @property
    def viewport_size(self) -> dict[str, int] | None:
        raw_page = self._top_level_page()
        value = raw_page.viewport_size
        return dict(value) if value is not None else None

    @property
    def frames(self) -> list[CloakBrowserWorkflowPage]:
        raw_frames = getattr(self._raw, "frames", None)
        if raw_frames is None:
            raw_frames = [self._raw, *getattr(self._raw, "child_frames", [])]
        return [
            CloakBrowserWorkflowPage(f"frame-{id(raw_frame)}", raw_frame)
            for raw_frame in raw_frames
        ]

    @property
    def main_frame(self) -> CloakBrowserWorkflowPage:
        raw_frame = getattr(self._top_level_page(), "main_frame", self._raw)
        return CloakBrowserWorkflowPage(f"frame-{id(raw_frame)}", raw_frame)

    async def goto(
        self, url: str, *, wait_until: str, timeout_ms: float
    ) -> object | None:
        return await self._top_level_page().goto(
            url, wait_until=wait_until, timeout=timeout_ms
        )

    async def title(self) -> str:
        return str(await self._top_level_page().title())

    async def close(self) -> None:
        await self._top_level_page().close()

    async def reload(self, **options: Any) -> object | None:
        return await self._top_level_page().reload(**_playwright_timeout(options))

    async def go_back(self, **options: Any) -> object | None:
        return await self._top_level_page().go_back(**_playwright_timeout(options))

    async def go_forward(self, **options: Any) -> object | None:
        return await self._top_level_page().go_forward(
            **_playwright_timeout(options)
        )

    async def wait_for_load_state(self, state: str, *, timeout_ms: float) -> None:
        await self._raw.wait_for_load_state(state, timeout=timeout_ms)

    async def bring_to_front(self) -> None:
        await self._top_level_page().bring_to_front()

    async def keyboard_press(self, key: str) -> None:
        await self._top_level_page().keyboard.press(key)

    async def keyboard_type(self, value: str) -> None:
        await self._top_level_page().keyboard.type(value)

    async def evaluate(self, expression: str) -> Any:
        return await self._raw.evaluate(expression)

    async def content(self) -> str:
        return str(await self._top_level_page().content())

    def frame(self, *, name: str) -> CloakBrowserWorkflowPage | None:
        raw_frame_method = getattr(self._raw, "frame", None)
        raw_frame = (
            raw_frame_method(name=name)
            if raw_frame_method is not None
            else next(
                (
                    item
                    for item in getattr(self._raw, "child_frames", [])
                    if getattr(item, "name", "") == name
                ),
                None,
            )
        )
        return (
            CloakBrowserWorkflowPage(f"frame-{id(raw_frame)}", raw_frame)
            if raw_frame is not None
            else None
        )

    async def wait_for_selector(
        self, selector: str, **options: Any
    ) -> CloakBrowserWorkflowElementHandle | None:
        raw = await self._raw.wait_for_selector(
            format_selector(selector), **_playwright_timeout(options)
        )
        return CloakBrowserWorkflowElementHandle(raw) if raw is not None else None

    async def query_selector_all(
        self, selector: str
    ) -> list[CloakBrowserWorkflowElementHandle]:
        return [
            CloakBrowserWorkflowElementHandle(raw)
            for raw in await self._raw.query_selector_all(format_selector(selector))
        ]

    def on(self, event: str, callback: Any) -> None:
        self._top_level_page().on(event, callback)

    def remove_listener(self, event: str, callback: Any) -> None:
        self._top_level_page().remove_listener(event, callback)

    def locator(self, selector: str) -> CloakBrowserWorkflowLocator:
        return CloakBrowserWorkflowLocator(self._raw.locator(format_selector(selector)))

    async def screenshot(
        self, *, full_page: bool = False, path: str | None = None
    ) -> bytes:
        options: dict[str, Any] = {"full_page": full_page}
        if path is not None:
            options["path"] = path
        return await self._top_level_page().screenshot(**options)

    async def capture_download(
        self, action: Callable[[], Awaitable[None]]
    ) -> CloakBrowserWorkflowDownload:
        raw_page = self._top_level_page()
        async with raw_page.expect_download() as download_info:
            await action()
        return CloakBrowserWorkflowDownload(await download_info.value)

    async def choose_file(
        self,
        action: Callable[[], Awaitable[None]],
        path: str,
        *,
        timeout_ms: float,
    ) -> None:
        raw_page = self._top_level_page()
        async with raw_page.expect_file_chooser(
            timeout=timeout_ms
        ) as chooser_info:
            await action()
        chooser = await chooser_info.value
        await chooser.set_files(path)

    def begin_request_watch(
        self, *, filter_type: str, url_pattern: str
    ) -> CloakBrowserWorkflowRequestWatch:
        return CloakBrowserWorkflowRequestWatch(
            self._raw, filter_type=filter_type, url_pattern=url_pattern
        )


def _playwright_timeout(options: dict[str, Any]) -> dict[str, Any]:
    translated = dict(options)
    if "timeout_ms" in translated:
        translated["timeout"] = translated.pop("timeout_ms")
    return translated


class CloakBrowserWorkflowSession:
    def __init__(self, context: Any, *, browser_pid: int | None = None) -> None:
        self._context = context
        self.browser_pid = browser_pid
        self._pages: dict[int, CloakBrowserWorkflowPage] = {}
        self._current_id: str | None = None
        self._active_frame: CloakBrowserWorkflowPage | None = None
        self._closed = False
        self.proxy_relay: BrowserProxyRelay | None = None
        existing = self._synchronize_pages()
        if existing:
            self._current_id = existing[0].id

    @classmethod
    def from_context(
        cls, context: Any, *, browser_pid: int | None = None
    ) -> CloakBrowserWorkflowSession:
        return cls(context, browser_pid=browser_pid)

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

    def active_page(self) -> CloakBrowserWorkflowPage:
        if self._active_frame is not None:
            if self._active_frame.closed:
                self._active_frame = None
            else:
                return self._active_frame
        return self.current_page()

    def pages(self) -> tuple[CloakBrowserWorkflowPage, ...]:
        return tuple(self._synchronize_pages())

    async def new_page(self) -> CloakBrowserWorkflowPage:
        raw = await self._context.new_page()
        pages = self._synchronize_pages()
        page = next(page for page in pages if page._raw is raw)
        self._current_id = page.id
        self._active_frame = None
        return page

    def select_page(self, page_id: str) -> CloakBrowserWorkflowPage:
        page = next((item for item in self._synchronize_pages() if item.id == page_id), None)
        if page is None:
            raise UnknownPage(f"页面 {page_id} 不存在")
        if page.closed:
            raise CurrentPageClosed(f"页面 {page_id} 已经关闭")
        self._current_id = page.id
        self._active_frame = None
        return page

    def select_frame(self, frame: BrowserPagePort) -> None:
        if not isinstance(frame, CloakBrowserWorkflowPage):
            raise TypeError("iframe 不属于当前浏览器会话")
        self._active_frame = frame

    def clear_frame(self) -> None:
        self._active_frame = None

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

    async def probe_proxy(self, reset: bool = False) -> dict[str, Any]:
        if self.proxy_relay is None:
            return {"exitIp": None, "error": {"code": "PROXY_NOT_BOUND", "message": "会话未绑定代理"}}
        return await self.proxy_relay.probe(reset)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._context.close()


async def _browser_process_id(context: Any) -> int | None:
    """Read Chromium's primary OS process id through its supported CDP domain."""

    browser = getattr(context, "browser", None)
    if browser is None:
        return None
    session = None
    try:
        session = await browser.new_browser_cdp_session()
        response = await session.send("SystemInfo.getProcessInfo")
        processes = response.get("processInfo", []) if isinstance(response, dict) else []
        for item in processes:
            if not isinstance(item, dict) or item.get("type") != "browser":
                continue
            process_id = item.get("id")
            if isinstance(process_id, int) and process_id > 0:
                return process_id
    except Exception:  # noqa: BLE001 -- worker ownership still has the process group.
        return None
    finally:
        if session is not None:
            try:
                await session.detach()
            except Exception:  # noqa: BLE001,S110 -- best-effort diagnostic session.
                pass
    return None


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
        session = CloakBrowserWorkflowSession.from_context(
            context, browser_pid=await _browser_process_id(context)
        )
        session.proxy_relay = relay_value
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
