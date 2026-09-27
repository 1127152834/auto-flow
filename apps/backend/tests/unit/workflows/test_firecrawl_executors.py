from __future__ import annotations

from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

HTML = """<html lang="zh"><head><title>示例</title>
<meta name="description" content="页面说明"></head><body>
<nav>导航</nav><main><h1>正文</h1><a href="/docs/a">文档 A</a>
<a href="https://sub.example.test/docs/b">文档 B</a></main>
<script>ignored()</script></body></html>"""


class Page:
    def __init__(self, page_id: str, pages: dict[str, str]) -> None:
        self.id = page_id
        self.url = "about:blank"
        self.closed = False
        self.pages = pages
        self.waited: list[str] = []

    async def goto(self, url: str, *, wait_until: str, timeout_ms: float) -> None:
        del wait_until, timeout_ms
        self.url = url

    async def content(self) -> str:
        return self.pages.get(self.url, HTML)

    async def evaluate(self, expression: str) -> Any:
        assert "querySelectorAll('a[href]')" in expression
        if self.url.endswith("/docs/a"):
            return ["https://example.test/docs/b", "https://other.test/out"]
        return [
            "https://example.test/docs/a",
            "https://sub.example.test/docs/b",
            "mailto:test@example.test",
        ]

    async def wait_for_selector(self, selector: str, **options: Any) -> object:
        del options
        self.waited.append(selector)
        return object()

    async def screenshot(self, *, full_page: bool = False) -> bytes:
        assert full_page is True
        return b"PNG"

    async def close(self) -> None:
        self.closed = True


class Browser:
    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.page_map = pages or {}
        self.original = Page("original", self.page_map)
        self.original.url = "https://example.test/original"
        self.selected = self.original
        self.created: list[Page] = []

    def current_page(self) -> Page:
        return self.selected

    async def new_page(self) -> Page:
        page = Page(f"page-{len(self.created)}", self.page_map)
        self.created.append(page)
        self.selected = page
        return page

    def select_page(self, page_id: str) -> Page:
        assert page_id == self.original.id
        self.selected = self.original
        return self.original


class Artifacts:
    def __init__(self) -> None:
        self.writes: list[tuple[str, bytes, str]] = []

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        self.writes.append((name, content, mime_type))
        return f"artifacts/{name}"


@pytest.mark.asyncio
async def test_firecrawl_scrape_preserves_source_content_and_frontend_screenshot():
    browser = Browser()
    artifacts = Artifacts()
    context = ExecutionContext(browser=browser, artifacts=artifacts)
    executor = build_production_executor_registry().get("firecrawl_scrape")

    result = await executor.execute(
        {
            "url": "https://example.test/page",
            "variableName": "out",
            "formats": ["markdown", "html", "text", "screenshot"],
            "onlyMainContent": True,
            "excludeTags": "nav",
            "waitFor": "#ready",
        },
        context,
    )

    assert result.success is True
    assert context.variables["out"]["url"] == "https://example.test/page"
    assert "正文" in context.variables["out"]["markdown"]
    assert "ignored" not in context.variables["out"]["html"]
    assert context.variables["out"]["screenshot"] == "artifacts/firecrawl-page.png"
    assert artifacts.writes == [("firecrawl-page.png", b"PNG", "image/png")]
    assert browser.created[0].waited == ["#ready"]
    assert browser.created[0].closed is True
    assert browser.current_page() is browser.original


@pytest.mark.asyncio
async def test_firecrawl_map_filters_links_and_reads_sitemap_in_cloakbrowser():
    browser = Browser(
        {
            "https://example.test/sitemap.xml": (
                "<urlset><url><loc>https://example.test/docs/from-map</loc></url>"
                "<url><loc>https://other.test/no</loc></url></urlset>"
            )
        }
    )
    context = ExecutionContext(browser=browser)
    result = await build_production_executor_registry().get("firecrawl_map").execute(
        {
            "url": "https://example.test",
            "variableName": "links",
            "search": "docs",
            "limit": 10,
            "ignoreSitemap": False,
        },
        context,
    )

    assert result.success is True
    assert context.variables["links"] == [
        "https://example.test/docs/a",
        "https://example.test/docs/from-map",
    ]
    assert all(page.closed for page in browser.created)
    assert browser.current_page() is browser.original


@pytest.mark.asyncio
async def test_firecrawl_crawl_uses_breadth_first_limits_and_cancellation_points():
    browser = Browser()
    context = ExecutionContext(browser=browser)
    result = await build_production_executor_registry().get("firecrawl_crawl").execute(
        {
            "url": "https://example.test/docs/start",
            "variableName": "pages",
            "maxDepth": 1,
            "limit": 2,
            "formats": ["text"],
            "onlyMainContent": True,
            "ignoreSitemap": True,
            "allowBackwardLinks": True,
        },
        context,
    )

    assert result.success is True
    assert [page["url"] for page in context.variables["pages"]] == [
        "https://example.test/docs/start",
        "https://example.test/docs/a",
    ]
    assert all(page.closed for page in browser.created)
    assert browser.current_page() is browser.original


@pytest.mark.asyncio
async def test_firecrawl_crawl_filters_sitemap_before_visiting_pages():
    browser = Browser(
        {
            "https://example.test/sitemap.xml": (
                "<urlset><url><loc>https://example.test/docs/a</loc></url>"
                "<url><loc>https://other.test/no</loc></url></urlset>"
            )
        }
    )
    context = ExecutionContext(browser=browser)
    result = await build_production_executor_registry().get("firecrawl_crawl").execute(
        {
            "url": "https://example.test/docs/start",
            "variableName": "pages",
            "maxDepth": 1,
            "limit": 5,
            "formats": ["text"],
            "ignoreSitemap": False,
            "allowBackwardLinks": True,
            "allowExternalLinks": False,
        },
        context,
    )

    assert result.success is True
    assert all(page["url"].startswith("https://example.test/") for page in result.data)
    assert "https://example.test/docs/a" in [page["url"] for page in result.data]


@pytest.mark.parametrize(
    "module_type", ["firecrawl_scrape", "firecrawl_map", "firecrawl_crawl"]
)
def test_firecrawl_family_is_registered_and_requires_cloakbrowser(module_type: str):
    executor = build_production_executor_registry().get(module_type)
    assert executor.requires_browser_for({}) is True
