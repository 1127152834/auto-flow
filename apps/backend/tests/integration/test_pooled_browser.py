"""Remediation M3 R3-07: a pooled browser gives every run a context that sees nothing of the last.

Real CloakBrowser: one run stores a cookie, local/session storage, an IndexedDB record, a Service
Worker registration and a permission grant; the next run on the same browser process sees none.
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path

import pytest

from autoflow.providers.browser.pooled_browser import SUPPORTED_CLOAKBROWSER, PooledBrowser

PAGE = b"""<!doctype html><title>pool</title><script>
window.leave = async () => {
  document.cookie = 'run=one; max-age=3600';
  localStorage.setItem('run', 'one');
  sessionStorage.setItem('run', 'one');
  await new Promise((done, fail) => {
    const open = indexedDB.open('pool', 1);
    open.onupgradeneeded = () => open.result.createObjectStore('rows');
    open.onsuccess = () => { const tx = open.result.transaction('rows', 'readwrite'); tx.objectStore('rows').put('one', 'run'); tx.oncomplete = done; tx.onerror = fail; };
    open.onerror = fail;
  });
  await navigator.serviceWorker.register('/sw.js');
  await navigator.serviceWorker.ready;
};
window.look = async () => ({
  cookie: document.cookie,
  local: localStorage.getItem('run'),
  session: sessionStorage.getItem('run'),
  databases: (await indexedDB.databases()).map(item => item.name),
  workers: (await navigator.serviceWorker.getRegistrations()).length,
  permission: (await navigator.permissions.query({ name: 'geolocation' })).state,
});
</script>"""


@pytest.fixture
def site():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            content, kind = (b"self.addEventListener('fetch', () => {});", "text/javascript") if self.path == "/sw.js" else (PAGE, "text/html")
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


def test_the_mirrored_launch_matches_the_pinned_cloakbrowser():
    assert version("cloakbrowser") == SUPPORTED_CLOAKBROWSER


@pytest.mark.asyncio
async def test_a_reused_browser_isolates_every_run(site, tmp_path, monkeypatch):
    configured = os.environ.get("AUTOFLOW_TEST_CLOAKBROWSER")
    if not configured:
        pytest.skip("set AUTOFLOW_TEST_CLOAKBROWSER to an installed real CloakBrowser executable")
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(Path(configured).resolve(strict=True)))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(tmp_path))
    launch = {"headless": True, "args": ["--fingerprint=24680"], "stealth_args": True, "locale": "zh-CN"}
    pool = PooledBrowser()
    try:
        first = await pool.new_context(launch)
        await first.grant_permissions(["geolocation"], origin=site.rstrip("/"))
        page = await first.new_page()
        await page.goto(site)
        await page.evaluate("leave()")
        seen = await page.evaluate("look()")
        assert seen["local"] == "one" and seen["workers"] == 1 and seen["permission"] == "granted"
        browser = pool.browser
        assert await pool.release(first) is True

        second = await pool.new_context(launch)
        assert pool.browser is browser  # same process, new context
        page = await second.new_page()
        await page.goto(site)
        assert await page.evaluate("look()") == {
            "cookie": "", "local": None, "session": None, "databases": [], "workers": 0, "permission": "prompt",
        }
        assert await pool.release(second) is True

        third = await pool.new_context({**launch, "locale": "en-US"})  # process-wide flag changed
        assert pool.browser is not browser and not browser.is_connected()
        await pool.release(third)
    finally:
        await pool.close()
