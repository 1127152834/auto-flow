# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
import types
from typing import Any

HTML = """<html><head><title>示例</title></head><body><main><h1>正文</h1>
<a href="https://example.test/docs/a">A</a>
<a href="https://example.test/outside">外部路径</a>
<a href="https://other.test/no">外站</a></main><script>ignored()</script></body></html>"""


class Page:
    def __init__(self):
        self.url = "about:blank"

    async def goto(self, url, **_options):
        self.url = url

    async def content(self):
        return HTML

    async def wait_for_selector(self, _selector, **_options):
        return object()

    async def eval_on_selector_all(self, _selector, _expression):
        if self.url.endswith("/docs/a"):
            return []
        return [
            "https://example.test/docs/a",
            "https://example.test/outside",
            "https://other.test/no",
        ]

    async def close(self):
        return None


class Browser:
    async def new_page(self):
        return Page()

    async def close(self):
        return None


class Launcher:
    async def __aenter__(self):
        return Browser()

    async def __aexit__(self, *_args):
        return None


service = types.ModuleType("app.services.headless_browser")
service.launch_headless_chromium = lambda: Launcher()
sys.modules["app.services.headless_browser"] = service

from app.executors.ai_firecrawl import (
    FirecrawlCrawlExecutor,
    FirecrawlMapExecutor,
    FirecrawlScrapeExecutor,
)
from app.executors.base import ExecutionContext


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    executor = {
        "firecrawl_scrape": FirecrawlScrapeExecutor,
        "firecrawl_map": FirecrawlMapExecutor,
        "firecrawl_crawl": FirecrawlCrawlExecutor,
    }[payload["type"]]()
    context = ExecutionContext(variables={})
    result = await executor.execute(payload["config"], context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(json.load(sys.stdin))), ensure_ascii=False))
