from __future__ import annotations

import hashlib
import io
import json
import os
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread

import pytest
from autoflow.providers.browser.workflow_worker import _run


@pytest.mark.asyncio
async def test_real_cloakbrowser_externalizes_one_mib_web_artifacts(
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
    artifact_root = tmp_path / "artifacts"
    output = io.StringIO()

    with _large_web_site() as (url, download):
        document = {
            "nodes": [
                _node("open", "open_page", {"url": url, "openMode": "current_tab"}),
                _node(
                    "extract",
                    "get_element_info",
                    {
                        "selector": "#large-text",
                        "attribute": "text",
                        "variableName": "large_text",
                    },
                ),
                _node(
                    "download",
                    "download_file",
                    {"downloadMode": "click", "triggerSelector": "#download"},
                ),
                _node(
                    "screenshot",
                    "screenshot",
                    {"screenshotType": "element", "selector": "#noise"},
                ),
            ],
            "edges": [
                {"id": "e1", "source": "open", "target": "extract"},
                {"id": "e2", "source": "extract", "target": "download"},
                {"id": "e3", "source": "download", "target": "screenshot"},
            ],
            "variables": [],
        }
        command = {
            "runId": "run-large-web",
            "workflowId": "workflow-large-web",
            "profileId": "profile-large-web",
            "artifactRoot": str(artifact_root),
            "document": document,
            "fingerprintSeed": 24680,
            "expertArgs": [],
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "colorScheme": "light",
            "geoip": False,
            "humanize": False,
            "humanPreset": "default",
            "extensionPaths": [],
            "licenseKey": None,
            "browserVersion": "145.0.7632.109.2",
            "releaseChannel": "stable",
            "headless": True,
        }
        result = await _run(command, Event(), output)

    assert result == 0
    lines = output.getvalue().splitlines()
    assert max(len(line.encode()) for line in lines) < 256 * 1024
    events = [json.loads(line) for line in lines]
    artifacts = [event for event in events if event["type"] == "artifact:registered"]
    by_node = {event["nodeId"]: event for event in artifacts}
    assert set(by_node) == {"extract", "download", "screenshot"}
    assert all(event["size"] > 1024 * 1024 for event in by_node.values())
    for event in by_node.values():
        content = (artifact_root / event["relativePath"]).read_bytes()
        assert len(content) == event["size"]
        assert hashlib.sha256(content).hexdigest() == event["sha256"]
    assert (artifact_root / by_node["download"]["relativePath"]).read_bytes() == download
    completed = {
        event["nodeId"]: event
        for event in events
        if event["type"] == "execution:node_complete"
    }
    assert completed["extract"]["data"]["externalized"] is True
    assert completed["extract"]["artifactIds"] == [by_node["extract"]["artifactId"]]


def _node(node_id: str, module_type: str, config: dict[str, object]) -> dict[str, object]:
    return {
        "id": node_id,
        "type": "moduleNode",
        "data": {"moduleType": module_type, "config": config},
    }


@contextmanager
def _large_web_site():
    large_text = "中" * 400_000
    download = bytes(range(256)) * 4097

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/download.bin":
                body = download
                content_type = "application/octet-stream"
                disposition = 'attachment; filename="large.bin"'
            else:
                body = (
                    "<a id='download' href='/download.bin' download>download</a>"
                    f"<div id='large-text'>{large_text}</div>"
                    "<canvas id='noise' width='1200' height='1200'></canvas>"
                    "<script>const c=document.querySelector('#noise'),x=c.getContext('2d'),"
                    "d=x.createImageData(c.width,c.height);let s=123456789;"
                    "for(let i=0;i<d.data.length;i+=4){s=(s*1664525+1013904223)>>>0;"
                    "d.data[i]=s&255;d.data[i+1]=(s>>>8)&255;d.data[i+2]=(s>>>16)&255;d.data[i+3]=255;}"
                    "x.putImageData(d,0,0)</script>"
                ).encode()
                content_type = "text/html; charset=utf-8"
                disposition = None
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if disposition:
                self.send_header("Content-Disposition", disposition)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/", download
    finally:
        server.shutdown()
        server.server_close()
