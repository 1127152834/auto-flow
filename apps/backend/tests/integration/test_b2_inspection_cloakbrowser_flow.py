from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.inspection import WorkflowInspectionService
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.infrastructure.process.inspection_worker import inspection_worker_command
from autoflow.infrastructure.process.workflow_worker import (
    WorkflowResourceCoordinator,
    WorkflowWorkerManager,
)
from autoflow.providers.browser.inspection_worker import InspectionController
from autoflow.providers.browser.workflow_session import launch_workflow_session


@pytest.mark.asyncio
async def test_real_cloakbrowser_tests_and_picks_a_selector(
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
    fixture = Path(__file__).parents[1] / "fixtures" / "workflow-page.html"
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
        "browserVersion": "145.0.7632.109.2",
        "releaseChannel": "stable",
        "headless": True,
    }

    async with launch_workflow_session(command) as browser:
        controller = InspectionController(browser)
        await controller.navigate(fixture.as_uri())
        tested = await controller.test_selector(
            {"selector": ".workflow-action", "highlight": False}
        )
        assert tested["matched"] is True
        assert tested["count"] == 2
        assert tested["element"]["tag"] == "button"

        await controller.start_picker()
        raw_page = browser.current_page()._raw
        # macOS translates Control+click to a context click; the migrated picker
        # accepts Command as the platform-equivalent single-selection modifier.
        await raw_page.locator("#workflow-submit").click(modifiers=["Meta"])
        picked = await controller.picker_result("__elementPickerResult")
        assert picked["selected"] is True
        assert picked["value"]["selector"] == "#workflow-submit"
        assert picked["value"]["tagName"] == "button"
        assert await raw_page.locator("#click-count").text_content() == "0"

        await controller.stop_picker()
        assert await raw_page.evaluate(
            "() => window.__elementPickerDisabled === true && !document.getElementById('__picker_box')"
        )


@pytest.mark.asyncio
async def test_real_inspection_handles_selector_and_page_change_edges(
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
    command = {
        "fingerprintSeed": 54321,
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

    async with launch_workflow_session(command) as browser:
        controller = InspectionController(browser)
        page = browser.current_page()._raw
        await page.evaluate(
            "html => { document.body.innerHTML = html; }",
            "<button class='many'>一</button><button class='many' hidden>二</button>",
        )
        multiple = await controller.test_selector(
            {"selector": ".many", "highlight": True}
        )
        assert multiple["count"] == 2
        assert multiple["matched"] is True
        assert multiple["element"]["text"] == "一"
        missing = await controller.test_selector(
            {"selector": ".absent", "highlight": False}
        )
        assert missing == {
            "success": True,
            "matched": False,
            "count": 0,
            "tried": [{"selector": ".absent", "count": 0}],
        }
        invalid = await controller.test_selector(
            {"selector": "css=[", "highlight": False}
        )
        assert invalid["success"] is True
        assert invalid["matched"] is False
        assert invalid["count"] == 0
        assert invalid["tried"][0]["selector"] == "css=["
        assert "error" in invalid["tried"][0]
        xpath = await controller.test_selector(
            {"selector": "xpath=//button[1]", "highlight": False}
        )
        assert xpath["matched"] is True and xpath["count"] == 1
        await page.evaluate(
            """() => {
              const host=document.createElement('div'); host.id='shadow-host';
              host.attachShadow({mode:'open'}).innerHTML='<button id="shadow-target">shadow</button>';
              document.body.appendChild(host);
            }"""
        )
        shadow = await controller.test_selector(
            {"selector": "#shadow-target", "highlight": False}
        )
        assert shadow["matched"] is True and shadow["count"] == 1
        await controller.start_picker()
        await page.locator("#shadow-target").click(modifiers=["Meta"])
        shadow_pick = await controller.picker_result("__elementPickerResult")
        assert shadow_pick["selected"] is True
        assert shadow_pick["value"]["selector"] == "#shadow-target"

        pages = await controller.pages()
        await page.context.new_page()
        changed = await controller.pages()
        assert changed["revision"] > pages["revision"]
        with pytest.raises(ValueError, match="stale page revision"):
            await controller.page_command(
                {
                    "expectedRevision": pages["revision"],
                    "pageId": pages["targetPageId"],
                    "action": "focus",
                }
            )

        browser.select_page(pages["targetPageId"])
        await page.evaluate(
            "html => { document.body.innerHTML = html; }",
            "<iframe src=\"data:text/html,<button id='frame-target'>frame</button>\"></iframe>",
        )
        await controller.start_picker()
        frame = next(item for item in page.frames if item.url.startswith("data:text/html"))
        await frame.locator("#frame-target").click(modifiers=["Meta"])
        picked = await controller.picker_result("__elementPickerResult")
        assert picked["selected"] is True
        assert picked["value"]["selector"] == "#frame-target"

        await page.goto("about:blank")
        assert (await controller.picker_result("__elementPickerResult"))["selected"] is False
        assert await page.evaluate("() => window.__elementPickerActive === true")

        extra = next(item for item in browser.pages() if item.id != pages["targetPageId"])
        browser.select_page(extra.id)
        await extra.close()
        after_close = await controller.pages()
        assert after_close["targetPageId"] is None
        assert {item["pageId"] for item in after_close["pages"]} == {pages["targetPageId"]}


@pytest.mark.asyncio
async def test_real_picker_and_runtime_share_nested_cross_origin_frame_target(
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
    command = {
        "fingerprintSeed": 98765,
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

    with _nested_frame_site() as url:
        async with launch_workflow_session(command) as browser:
            controller = InspectionController(browser)
            await controller.navigate(url)
            page = browser.current_page()._raw
            await page.frame_locator("#same").frame_locator("#cross").locator(
                "#deep-target"
            ).wait_for()
            deep = next(frame for frame in page.frames if frame.url.endswith("/deep"))
            await controller.start_picker()
            await deep.locator("#deep-target").click(modifiers=["Meta"])
            picked = await controller.picker_result("__elementPickerResult")
            assert picked["value"]["selector"] == "#deep-target"
            await controller.stop_picker()

            document = {
                "nodes": [
                    {
                        "id": "same",
                        "type": "moduleNode",
                        "data": {
                            "moduleType": "switch_iframe",
                            "config": {
                                "locateBy": "selector",
                                "iframeSelector": "#same",
                            },
                        },
                    },
                    {
                        "id": "cross",
                        "type": "moduleNode",
                        "data": {
                            "moduleType": "switch_iframe",
                            "config": {
                                "locateBy": "selector",
                                "iframeSelector": "#cross",
                            },
                        },
                    },
                    {
                        "id": "click",
                        "type": "moduleNode",
                        "data": {
                            "moduleType": "click_element",
                            "config": {"selector": "#deep-target"},
                        },
                    },
                ],
                "edges": [
                    {"id": "same-cross", "source": "same", "target": "cross"},
                    {"id": "cross-click", "source": "cross", "target": "click"},
                ],
                "variables": [],
            }
            result = await WorkflowRuntime(
                build_production_executor_registry()
            ).execute(document, ExecutionContext(browser=browser))

            assert result.success is True
            assert await deep.evaluate("() => window.deepClicks") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("node_mode", [False, True])
async def test_real_inspection_worker_owns_profile_and_cleans_process_tree(
    tmp_path: Path, node_mode: bool,
) -> None:
    configured = os.environ.get("AUTOFLOW_B1_CLOAK_EXECUTABLE")
    if not configured:
        pytest.skip("set AUTOFLOW_B1_CLOAK_EXECUTABLE for the real CloakBrowser test")
    executable = Path(configured)
    if not executable.is_file():
        pytest.fail("AUTOFLOW_B1_CLOAK_EXECUTABLE does not point to a file")
    now = datetime.now(UTC)
    profile = Profile(
        "profile-inspection",
        ProfileSpec.from_values(
            {
                "name": "真实拾取",
                "start_url": "about:blank",
                "browser_version": "145.0.7632.109.2",
                "browser_edition": "public",
                "release_channel": "stable",
                "geoip": False,
                "headless": True,
                "humanize": False,
                "human_preset": "default",
                "extension_paths": [],
                "expert_args": [],
                "proxy_mode": "none",
            }
        ),
        12345,
        now,
        now,
    )

    class Profiles:
        def get(self, profile_id: str) -> Profile:
            assert profile_id == profile.id
            return profile

    class Usage:
        @contextmanager
        def guard(self, profile_id: str):
            assert profile_id == profile.id
            yield

    holder: dict[str, WorkflowInspectionService] = {}

    async def on_event(event: dict[str, object]) -> None:
        await holder["service"].on_worker_event(event)

    async def on_exit(session_id: str, return_code: int) -> None:
        await holder["service"].on_worker_exit(session_id, return_code)

    workers = WorkflowWorkerManager(
        tmp_path,
        command=inspection_worker_command(),
        on_event=on_event,
        on_exit=on_exit,
    )
    resources = WorkflowResourceCoordinator(Usage(), tmp_path / "kernels")
    service = WorkflowInspectionService(
        profiles=Profiles(),  # type: ignore[arg-type]
        installed_kernels=lambda: [
            InstalledKernel("public", "145.0.7632.109.2", executable, 1)
        ],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=resources,
        workers=workers,
    )
    holder["service"] = service
    fixture = Path(__file__).parents[1] / "fixtures" / "workflow-page.html"

    if node_mode:
        from autoflow.application.workflows.browser_resources import WorkflowBrowserResources
        from contextlib import nullcontext
        browser = WorkflowBrowserResources(Profiles(), service._installed, service._resolve_proxy, lambda: None, Usage(), lambda _: nullcontext())
        service.configure_node_browser_environments(browser, None)
        opened = await service.open(profile_id=None, url=fixture.as_uri(), browser_environment={'source':'newFromProfile','profileId':profile.id,'proxy':{'mode':'none'},'kernel':{'edition':'public','version':profile.spec.browser_version}})
    else:
        opened = await service.open(profile_id=profile.id, url=fixture.as_uri())
    assert opened["isOpen"] is True
    assert workers.active_processes()
    pages = await service.pages()
    assert pages["pages"][0]["url"] == fixture.as_uri()
    tested = await service.test_selector(
        {"selector": "#workflow-submit", "highlight": False}
    )
    assert tested["matched"] is True and tested["count"] == 1
    await service.start_picker(
        session_id="picker-worker", profile_id=profile.id, url=None
    )
    assert service.picker_status("picker-worker")["active"] is True

    await service.close(opened["sessionId"])
    assert workers.active_processes() == []
    assert resources.owner_id is None


async def _none():
    return None


@contextmanager
def _nested_frame_site():
    class DeepHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = (
                b"<button id='deep-target' onclick='window.deepClicks += 1'>deep</button>"
                b"<script>window.deepClicks=0</script>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    deep_server = ThreadingHTTPServer(("127.0.0.1", 0), DeepHandler)
    Thread(target=deep_server.serve_forever, daemon=True).start()
    deep_url = f"http://localhost:{deep_server.server_port}/deep"

    class OuterHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            html = (
                f"<iframe id='cross' src='{deep_url}'></iframe>"
                if self.path == "/same"
                else "<iframe id='same' src='/same'></iframe>"
            )
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    outer_server = ThreadingHTTPServer(("127.0.0.1", 0), OuterHandler)
    Thread(target=outer_server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{outer_server.server_port}/"
    finally:
        outer_server.shutdown()
        outer_server.server_close()
        deep_server.shutdown()
        deep_server.server_close()
