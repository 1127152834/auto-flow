"""Remediation M2 R2-28 / AC2-20: cookie, storage and interception nodes in a real CloakBrowser."""

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import pytest_asyncio

from autoflow.application.workflows.executors.web_state import (
    WebCookieExecutor,
    WebInterceptExecutor,
    WebStorageExecutor,
)
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import CloakBrowserWorkflowSession

PAGE = b"<html><body><output id=out></output></body></html>"


@pytest.fixture
def site():
    seen: list[tuple[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.path, self.headers.get("Cookie", "") + "|" + self.headers.get("X-Trace", "")))
            body = b'{"source":"server"}' if self.path.startswith("/api") else PAGE
            self.send_response(200)
            self.send_header("Content-Type", "application/json" if self.path.startswith("/api") else "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", seen
    server.shutdown()


@pytest_asyncio.fixture
async def browser(tmp_path, monkeypatch):
    configured = os.environ.get("AUTOFLOW_TEST_CLOAKBROWSER")
    if not configured:
        pytest.skip("set AUTOFLOW_TEST_CLOAKBROWSER to an installed real CloakBrowser executable")
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(Path(configured).resolve(strict=True)))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(tmp_path / "cache"))
    from cloakbrowser import launch_context_async  # type: ignore[import-untyped]

    context = await launch_context_async(headless=True)
    try:
        yield context
    finally:
        await context.close()


@pytest.mark.asyncio
async def test_cookies_storage_and_interception_change_real_browser_state(browser, site):
    base, seen = site
    page = browser.pages[0] if browser.pages else await browser.new_page()
    await page.goto(base + "/")
    context = ExecutionContext(browser=CloakBrowserWorkflowSession(browser))

    written = await WebCookieExecutor().execute({"operation": "set", "name": "token", "value": "abc"}, context)
    assert written.success, written.error
    read = await WebCookieExecutor().execute({"operation": "get", "name": "token", "variableName": "tok"}, context)
    assert read.success and context.variables["tok"] == "abc"
    assert "tok" in context.sensitive_variables
    await page.goto(base + "/after")
    assert "token=abc" in seen[-1][1]

    for config in ({"operation": "set", "area": "local", "key": "k", "value": "v"},
                   {"operation": "get", "area": "local", "key": "k", "variableName": "stored"}):
        result = await WebStorageExecutor().execute(config, context)
        assert result.success, result.error
    assert context.variables["stored"] == "v"
    cleared = await WebStorageExecutor().execute({"operation": "clear", "area": "local"}, context)
    assert cleared.success and await page.evaluate("localStorage.length") == 0

    mocked = await WebInterceptExecutor().execute({"operation": "start", "urlPattern": "**/api/**", "action": "mock", "mockBody": '{"source":"mock"}'}, context)
    assert mocked.success, mocked.error
    calls_before = len(seen)
    body = await page.evaluate(f"fetch('{base}/api/x').then(r => r.text())")
    assert body == '{"source":"mock"}' and len(seen) == calls_before, "the mocked request never reached the server"
    stopped = await WebInterceptExecutor().execute({"operation": "stop", "urlPattern": "**/api/**"}, context)
    assert stopped.success
    assert await page.evaluate(f"fetch('{base}/api/x').then(r => r.text())") == '{"source":"server"}'

    headers = await WebInterceptExecutor().execute({"operation": "start", "urlPattern": "**/api/**", "action": "headers", "headers": {"X-Trace": "t1"}}, context)
    assert headers.success
    await page.evaluate(f"fetch('{base}/api/y').then(r => r.text())")
    assert seen[-1][0] == "/api/y" and seen[-1][1].endswith("|t1")

    deleted = await WebCookieExecutor().execute({"operation": "delete", "name": "token"}, context)
    assert deleted.success
    gone = await WebCookieExecutor().execute({"operation": "get", "name": "token", "variableName": "tok"}, context)
    assert gone.success and context.variables["tok"] is None


@pytest.mark.asyncio
async def test_invalid_settings_fail_with_a_reason(browser, site):
    base, _seen = site
    page = browser.pages[0] if browser.pages else await browser.new_page()
    await page.goto(base + "/")
    context = ExecutionContext(browser=CloakBrowserWorkflowSession(browser))
    assert (await WebCookieExecutor().execute({"operation": "set"}, context)).error == "Cookie 名称不能为空"
    assert (await WebStorageExecutor().execute({"operation": "get", "area": "disk", "key": "k"}, context)).error.startswith("存储类型")
    assert (await WebInterceptExecutor().execute({"operation": "start"}, context)).error == "需要填写要拦截的网址规则"
