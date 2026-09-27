from __future__ import annotations

import base64
import io
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from PIL import Image, ImageDraw, ImageFont

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import launch_workflow_session


def _captcha_png() -> bytes:
    small = Image.new("RGB", (40, 15), "white")
    ImageDraw.Draw(small).text(
        (2, 1), "1234", font=ImageFont.load_default(), fill="black"
    )
    image = small.resize((160, 60), Image.Resampling.NEAREST)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.asyncio
async def test_real_cloakbrowser_runs_captcha_family(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured = os.environ.get("AUTOFLOW_B1_CLOAK_EXECUTABLE")
    if not configured:
        pytest.skip("set AUTOFLOW_B1_CLOAK_EXECUTABLE for the real CloakBrowser test")
    executable = Path(configured)
    if not executable.is_file():
        pytest.fail("AUTOFLOW_B1_CLOAK_EXECUTABLE does not point to a file")
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(tmp_path / "cloak-cache"))
    image = base64.b64encode(_captcha_png()).decode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = f"""<!doctype html><html><body>
              <img id="captcha" src="data:image/png;base64,{image}">
              <input id="code"><button id="submit" type="button"
                onclick="document.body.dataset.submitted=this.previousElementSibling.value">提交</button>
              <div id="slider" style="margin-top:30px;width:30px;height:30px;background:#666"></div>
              <script>
                let start = 0;
                slider.addEventListener('pointerdown', event => start = event.clientX);
                document.addEventListener('pointerup', event => document.body.dataset.distance = Math.round(event.clientX - start));
              </script>
            </body></html>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    document = {
        "nodes": [
            {
                "id": "open",
                "type": "moduleNode",
                "data": {
                    "moduleType": "open_page",
                    "config": {"url": url, "openMode": "new_tab"},
                },
            },
            {
                "id": "ocr",
                "type": "moduleNode",
                "data": {
                    "moduleType": "ocr_captcha",
                    "config": {
                        "imageSelector": "#captcha",
                        "inputSelector": "#code",
                        "variableName": "code",
                        "autoSubmit": True,
                        "submitSelector": "#submit",
                    },
                },
            },
            {
                "id": "slider",
                "type": "moduleNode",
                "data": {
                    "moduleType": "slider_captcha",
                    "config": {"sliderSelector": "#slider", "targetDistance": 35},
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "open", "target": "ocr"},
            {"id": "e2", "source": "ocr", "target": "slider"},
        ],
    }
    command = {
        "fingerprintSeed": 12345,
        "expertArgs": [],
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "colorScheme": "light",
        "geoip": False,
        "humanize": False,
        "humanPreset": "default",
        "extensionPaths": [],
        "licenseKey": None,
        "browserVersion": "151.0.7922.108.3",
        "releaseChannel": "stable",
        "headless": True,
    }
    try:
        async with launch_workflow_session(command) as browser:
            context = ExecutionContext(browser=browser)
            result = await WorkflowRuntime(
                build_production_executor_registry()
            ).execute(document, context)
            page_state = await browser.current_page().evaluate(
                "({value: code.value, submitted: document.body.dataset.submitted, distance: document.body.dataset.distance})"
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.success is True
    assert context.variables["code"] == "1234"
    assert page_state == {"value": "1234", "submitted": "1234", "distance": "35"}
