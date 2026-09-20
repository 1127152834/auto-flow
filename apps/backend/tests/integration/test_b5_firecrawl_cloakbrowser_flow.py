from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import launch_workflow_session


class Artifacts:
    def __init__(self, root: Path) -> None:
        self.root = root

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        assert mime_type == "image/png"
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)


@pytest.mark.asyncio
async def test_real_cloakbrowser_runs_firecrawl_family(
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

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if self.path == "/sitemap.xml":
                body = (
                    f"<urlset><url><loc>{origin}/docs/from-map</loc></url></urlset>"
                ).encode()
                content_type = "application/xml"
            elif self.path == "/docs/a":
                body = b"<html><body><main><h1>Page A</h1></main></body></html>"
                content_type = "text/html; charset=utf-8"
            else:
                body = (
                    "<html lang='zh'><head><title>Firecrawl Fixture</title>"
                    "<meta name='description' content='fixture'></head><body>"
                    f"<main><h1>Controlled page</h1><a href='{origin}/docs/a'>A</a>"
                    f"<a href='{origin}/outside'>Outside</a></main>"
                    "<script>window.fixtureSecret='not-content'</script></body></html>"
                ).encode()
                content_type = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    nodes = [
        (
            "firecrawl_scrape",
            {
                "url": f"{origin}/docs/start",
                "variableName": "scrape",
                "formats": ["markdown", "html", "screenshot"],
                "onlyMainContent": True,
            },
        ),
        (
            "firecrawl_map",
            {
                "url": f"{origin}/docs/start",
                "variableName": "links",
                "search": "docs",
                "ignoreSitemap": False,
                "limit": 10,
            },
        ),
        (
            "firecrawl_crawl",
            {
                "url": f"{origin}/docs/start",
                "variableName": "pages",
                "maxDepth": 1,
                "limit": 2,
                "formats": ["text"],
                "onlyMainContent": True,
                "ignoreSitemap": True,
                "allowBackwardLinks": True,
            },
        ),
    ]
    document = {
        "nodes": [
            {
                "id": f"node-{index}",
                "type": "moduleNode",
                "data": {"moduleType": module_type, "config": config},
            }
            for index, (module_type, config) in enumerate(nodes)
        ],
        "edges": [
            {
                "id": f"edge-{index}",
                "source": f"node-{index}",
                "target": f"node-{index + 1}",
            }
            for index in range(len(nodes) - 1)
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
            context = ExecutionContext(
                browser=browser,
                artifacts=Artifacts(tmp_path / "artifacts"),  # type: ignore[arg-type]
            )
            result = await WorkflowRuntime(
                build_production_executor_registry()
            ).execute(document, context)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.success is True
    assert "Controlled page" in context.variables["scrape"]["markdown"]
    assert "fixtureSecret" not in context.variables["scrape"]["html"]
    assert Path(context.variables["scrape"]["screenshot"]).read_bytes().startswith(
        b"\x89PNG"
    )
    assert context.variables["links"] == [
        f"{origin}/docs/a",
        f"{origin}/docs/from-map",
    ]
    assert [page["url"] for page in context.variables["pages"]] == [
        f"{origin}/docs/start",
        f"{origin}/docs/a",
    ]
