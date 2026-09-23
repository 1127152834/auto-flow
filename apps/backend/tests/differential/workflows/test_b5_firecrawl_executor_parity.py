from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_firecrawl_harness.py")

HTML = """<html><head><title>示例</title></head><body><main><h1>正文</h1>
<a href="https://example.test/docs/a">A</a>
<a href="https://example.test/outside">外部路径</a>
<a href="https://other.test/no">外站</a></main><script>ignored()</script></body></html>"""

CASES = (
    (
        "firecrawl_scrape",
        {
            "url": "https://example.test/docs/start",
            "variableName": "out",
            "formats": ["markdown", "html", "text"],
            "onlyMainContent": True,
            "waitFor": "#ready",
        },
    ),
    (
        "firecrawl_map",
        {
            "url": "https://example.test/docs/start",
            "variableName": "out",
            "search": "docs",
            "limit": 5,
            "ignoreSitemap": True,
            "includeSubdomains": False,
        },
    ),
    (
        "firecrawl_crawl",
        {
            "url": "https://example.test/docs/start",
            "variableName": "out",
            "maxDepth": 1,
            "limit": 5,
            "formats": ["markdown", "html", "text"],
            "onlyMainContent": True,
            "ignoreSitemap": True,
            "allowBackwardLinks": False,
            "allowExternalLinks": False,
        },
    ),
)


class Page:
    def __init__(self, page_id: str) -> None:
        self.id = page_id
        self.url = "about:blank"
        self.closed = False

    async def goto(self, url: str, *, wait_until: str, timeout_ms: float) -> None:
        del wait_until, timeout_ms
        self.url = url

    async def content(self) -> str:
        return HTML

    async def wait_for_selector(self, _selector: str, **_options: Any) -> object:
        return object()

    async def evaluate(self, expression: str) -> list[str]:
        assert "querySelectorAll('a[href]')" in expression
        if self.url.endswith("/docs/a"):
            return []
        return [
            "https://example.test/docs/a",
            "https://example.test/outside",
            "https://other.test/no",
        ]

    async def close(self) -> None:
        self.closed = True


class Browser:
    def __init__(self) -> None:
        self.original = Page("original")
        self.original.url = "https://example.test/original"
        self.selected = self.original
        self.created = 0

    def current_page(self) -> Page:
        return self.selected

    async def new_page(self) -> Page:
        page = Page(f"page-{self.created}")
        self.created += 1
        self.selected = page
        return page

    def select_page(self, page_id: str) -> Page:
        assert page_id == "original"
        self.selected = self.original
        return self.original


def _source(payload: dict[str, Any]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        check=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.parametrize(("module_type", "config"), CASES)
def test_firecrawl_output_and_variable_changes_match_frozen_source(
    module_type: str, config: dict[str, Any]
) -> None:
    source = _source({"type": module_type, "config": config})
    context = ExecutionContext(browser=Browser())
    result = asyncio.run(
        build_production_executor_registry().get(module_type).execute(config, context)
    )
    target = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }
    assert target == source
