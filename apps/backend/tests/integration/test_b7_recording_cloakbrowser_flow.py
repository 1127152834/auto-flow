from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from autoflow.providers.browser.inspection_worker import InspectionController
from autoflow.providers.browser.workflow_session import launch_workflow_session


@pytest.mark.asyncio
async def test_real_cloakbrowser_records_chinese_form_and_future_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured = os.environ.get("AUTOFLOW_B1_CLOAK_EXECUTABLE")
    if not configured:
        pytest.skip("set AUTOFLOW_B1_CLOAK_EXECUTABLE for the real CloakBrowser test")
    executable = Path(configured)
    if not executable.is_file():
        pytest.fail("AUTOFLOW_B1_CLOAK_EXECUTABLE does not point to a file")
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    cache_dir = tmp_path / "cloak-cache"
    cache_dir.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache_dir))
    license_file = Path.home() / ".cloakbrowser" / "license.key"
    license_cache = Path.home() / ".cloakbrowser" / ".license_cache"
    license_key = os.environ.get("AUTOFLOW_B1_CLOAK_LICENSE")
    if license_key is None and "-pro" in str(executable) and license_file.is_file():
        license_key = license_file.read_text().strip()
    if "-pro" in str(executable) and license_cache.is_file():
        shutil.copy2(license_cache, cache_dir / ".license_cache")
    command = {
        "fingerprintSeed": 24680,
        "expertArgs": [],
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "colorScheme": "light",
        "geoip": False,
        "humanize": False,
        "humanPreset": "default",
        "extensionPaths": [],
        "licenseKey": license_key,
        "browserVersion": "145.0.7632.109.2",
        "releaseChannel": "stable",
        "headless": True,
    }
    fixture = Path(__file__).parents[1] / "fixtures" / "workflow-page.html"
    future_fixture = tmp_path / "future.html"
    future_fixture.write_text('<button id="future">新页</button>', encoding="utf-8")

    async with launch_workflow_session(command) as browser:
        controller = InspectionController(browser)
        page = browser.current_page()._raw
        await page.goto(fixture.as_uri(), wait_until="domcontentloaded")
        await controller.execute({"command": "recorder_start"})
        await page.locator("#workflow-input").fill("暂停前")
        paused = await controller.execute({"command": "recorder_pause"})
        await page.locator("#workflow-input").fill("暂停期间")
        extra = await page.context.new_page()
        await extra.goto(future_fixture.as_uri(), wait_until="domcontentloaded")
        await extra.locator("#future").click()
        while_paused = await controller.execute({"command": "recorder_events"})
        resumed = await controller.execute({"command": "recorder_resume"})
        await page.locator("#workflow-input").fill("中文输入")
        await page.locator("#workflow-submit").click()
        frame = page.frame_locator("#workflow-frame")
        await frame.locator("#frame-value").click()

        await extra.locator("#future").click()
        drained = await controller.execute({"command": "recorder_events"})
        with _cross_origin_navigation_site() as (start_url, end_url):
            await page.goto(start_url, wait_until="domcontentloaded")
            await page.locator("#tail").fill("跨域导航尾部")
            await page.locator("#next").click()
            await page.wait_for_url(end_url)
            tail = await controller.execute({"command": "recorder_events"})
        stopped = await controller.execute({"command": "recorder_stop"})

    events = [*drained["events"], *tail["events"], *stopped["events"]]
    assert paused["paused"] is True
    assert any(event.get("value") == "暂停前" for event in paused["events"])
    assert while_paused == {"recording": True, "paused": True, "events": []}
    assert resumed == {"recording": True, "paused": False, "events": []}
    assert not any(event.get("value") == "暂停期间" for event in events)
    assert any(
        event["type"] == "input"
        and event["selector"] == "#workflow-input"
        and event["value"] == "中文输入"
        for event in events
    )
    assert any(
        event["type"] == "input"
        and event["selector"] == "#tail"
        and event["value"] == "跨域导航尾部"
        for event in events
    )
    assert sum(
        event["type"] == "click" and event["selector"] == "#workflow-submit"
        for event in events
    ) == 1
    assert any(
        event["type"] == "click" and event["selector"] == "#future"
        for event in events
    )
    assert sum(
        event["type"] == "click" and event["selector"] == "#future"
        for event in events
    ) == 1
    assert any(
        event["type"] == "click"
        and event["selector"] == "#frame-value"
        and event["_frame"]["selector"] == "iframe#workflow-frame"
        for event in events
    )


@contextmanager
def _cross_origin_navigation_site():
    class Destination(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = b"<p id='arrived'>arrived</p>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    destination = ThreadingHTTPServer(("127.0.0.1", 0), Destination)
    Thread(target=destination.serve_forever, daemon=True).start()
    end_url = f"http://localhost:{destination.server_port}/done"

    class Source(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = (
                f'<input id="tail"><a id="next" href="{end_url}">next</a>'
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    source = ThreadingHTTPServer(("127.0.0.1", 0), Source)
    Thread(target=source.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{source.server_port}/start", end_url
    finally:
        source.shutdown()
        source.server_close()
        destination.shutdown()
        destination.server_close()
