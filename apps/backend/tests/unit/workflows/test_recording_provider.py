from __future__ import annotations

import pytest
from autoflow.providers.browser.inspection_worker import InspectionController


class Frame:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.scripts: list[str] = []

    async def evaluate(self, script):
        self.scripts.append(script)
        if "JSON.parse(sessionStorage.getItem" in script:
            events, self.events = self.events, []
            return events
        return None


class Page:
    def __init__(self) -> None:
        self.main_frame = Frame()
        self.frames = [self.main_frame]


class Context:
    def __init__(self, page: Page) -> None:
        self.pages = [page]
        self.init_scripts: list[str] = []
        self.binding = None

    async def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)

    async def expose_binding(self, _name: str, callback) -> None:
        self.binding = callback


class Browser:
    def __init__(self) -> None:
        self.page = Page()
        self._context = Context(self.page)


@pytest.mark.asyncio
async def test_recording_controller_injects_current_and_future_documents_and_drains_once():
    browser = Browser()
    controller = InspectionController(browser)  # type: ignore[arg-type]

    started = await controller.execute({"command": "recorder_start"})
    assert started == {"recording": True, "events": []}
    assert any("__webrpa_rec" in script for script in browser._context.init_scripts)
    assert any("__webrpa_rec" in script for script in browser.page.main_frame.scripts)

    assert browser._context.binding is not None
    source = {"page": browser.page, "frame": browser.page.main_frame}
    await browser._context.binding(
        source,
        {
            "type": "input",
            "selector": "#name",
            "value": "中",
            "ts": 1,
            "__autoflowRecordId": "input-old",
        },
    )
    await browser._context.binding(
        source,
        {
            "type": "input",
            "selector": "#name",
            "value": "中文",
            "ts": 2,
            "__autoflowRecordId": "input-final",
        },
    )
    await browser._context.binding(
        source,
        {
            "type": "click",
            "selector": "#submit",
            "ts": 3,
            "__autoflowRecordId": "click",
        },
    )
    browser.page.main_frame.events = [
        {
            "type": "input",
            "selector": "#name",
            "value": "中文",
            "ts": 2,
            "__autoflowRecordId": "input-final",
        },
        {
            "type": "click",
            "selector": "#submit",
            "ts": 3,
            "__autoflowRecordId": "click",
        },
    ]
    first = await controller.execute({"command": "recorder_events"})
    second = await controller.execute({"command": "recorder_events"})
    assert first == {
        "recording": True,
        "events": [
            {
                "type": "input",
                "selector": "#name",
                "value": "中文",
                "ts": 2,
                "_frame": {"main": True},
            },
            {
                "type": "click",
                "selector": "#submit",
                "ts": 3,
                "_frame": {"main": True},
            },
        ],
    }
    assert second == {"recording": True, "events": []}
    assert await controller.execute({"command": "recorder_stop"}) == {
        "recording": False,
        "events": [],
    }


@pytest.mark.asyncio
async def test_recording_controller_accepts_cdp_events_and_ignores_invalid_payloads():
    browser = Browser()
    controller = InspectionController(browser)  # type: ignore[arg-type]
    await controller.execute({"command": "recorder_start"})
    recorder = controller.recorder
    page = browser.page
    recorder._cdp_main_frames[id(page)] = "main-frame"
    recorder._cdp_contexts[(id(page), 7)] = {"frameId": "main-frame"}

    recorder._capture_cdp_event(
        page,
        {
            "name": "__autoflowRecordCdp",
            "payload": '{"type":"input","selector":"#tail","value":"尾部","ts":4}',
            "executionContextId": 7,
        },
    )
    recorder._capture_cdp_event(
        page,
        {
            "name": "__autoflowRecordCdp",
            "payload": "not-json",
            "executionContextId": 7,
        },
    )

    result = await controller.execute({"command": "recorder_events"})
    assert result["events"] == [
        {
            "type": "input",
            "selector": "#tail",
            "value": "尾部",
            "ts": 4,
            "_frame": {"main": True},
        }
    ]
