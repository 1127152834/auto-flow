from __future__ import annotations

import asyncio
import json
import sys
from contextlib import suppress
from threading import Event
from typing import Any, TextIO

from autoflow.providers.browser.workflow_actions import fallback_selectors
from autoflow.providers.browser.workflow_session import (
    CloakBrowserWorkflowSession,
    format_selector,
    launch_workflow_session,
)

from .element_picker_script import PICKER_SCRIPT

_OVERLAY_JS = """
(boxes) => {
  const id = '__autoflow_selector_test_overlay__';
  document.getElementById(id)?.remove();
  const layer = document.createElement('div');
  layer.id = id;
  layer.style.cssText = 'position:fixed;inset:0;z-index:2147483647;pointer-events:none;';
  boxes.forEach((b, i) => {
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;border:2px solid #ef4444;background:rgba(239,68,68,.15);pointer-events:none;';
    d.style.left=b.x+'px'; d.style.top=b.y+'px'; d.style.width=b.width+'px'; d.style.height=b.height+'px';
    if (i === 0) { const tag=document.createElement('div'); tag.textContent='匹配 '+boxes.length+' 个'; tag.style.cssText='position:absolute;left:0;top:-20px;background:#ef4444;color:#fff;font:12px sans-serif;padding:1px 6px;border-radius:3px;white-space:nowrap;'; d.appendChild(tag); }
    layer.appendChild(d);
  });
  document.documentElement.appendChild(layer);
  setTimeout(() => layer.remove(), 3000);
}
"""


def run_inspection_worker(
    _stopped: Event, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout
) -> int:
    try:
        return asyncio.run(_run(_read(stdin), stdin, stdout))
    except BaseException:  # noqa: BLE001 -- provider details stay in the worker.
        _write(stdout, {"type": "error", "error": "Inspection worker failed"})
        return 1


async def _run(start: dict[str, Any], stdin: TextIO, stdout: TextIO) -> int:
    run_id = _required(start, "runId")
    profile_id = _required(start, "profileId")
    async with launch_workflow_session(start) as browser:
        ready: dict[str, Any] = {"type": "ready", "runId": run_id, "profileId": profile_id}
        if isinstance(browser.browser_pid, int):
            ready["childPid"] = browser.browser_pid
        _write(stdout, ready)
        controller = InspectionController(browser)
        initial_url = start.get("inspectionUrl")
        if isinstance(initial_url, str) and initial_url:
            with suppress(Exception):
                await browser.current_page().goto(
                    initial_url, wait_until="domcontentloaded", timeout_ms=15_000
                )
        while True:
            try:
                command = await asyncio.to_thread(_read, stdin)
            except EOFError:
                return 0
            request_id = command.get("requestId")
            if not isinstance(request_id, str) or not request_id:
                continue
            try:
                data = await controller.execute(command)
                _write(
                    stdout,
                    {
                        "type": "inspection:response",
                        "runId": run_id,
                        "requestId": request_id,
                        "success": True,
                        "data": data,
                    },
                )
            except Exception:  # noqa: BLE001 -- never expose provider paths or secrets.
                _write(
                    stdout,
                    {
                        "type": "inspection:response",
                        "runId": run_id,
                        "requestId": request_id,
                        "success": False,
                        "error": "浏览器操作失败或页面已经变化",
                    },
                )


class InspectionController:
    def __init__(self, browser: CloakBrowserWorkflowSession) -> None:
        self.browser = browser
        self.picker_active = False
        self.revision = 0
        self._page_signature: tuple[tuple[str, str], ...] = ()

    async def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        action = command.get("command")
        if action == "pages":
            return await self.pages()
        if action == "page":
            return await self.page_command(command)
        if action == "navigate":
            return await self.navigate(_required(command, "url"))
        if action == "url":
            return {"url": self.browser.current_page().url}
        if action == "start_picker":
            await self.start_picker()
            return {"active": True}
        if action == "stop_picker":
            await self.stop_picker()
            return {"active": False}
        if action == "picker_result":
            return await self.picker_result(_required(command, "key"))
        if action == "test_selector":
            return await self.test_selector(command)
        raise ValueError("unknown inspection command")

    async def pages(self) -> dict[str, Any]:
        pages = [page for page in self.browser.pages() if not page.closed]
        signature = tuple((page.id, page.url) for page in pages)
        if signature != self._page_signature:
            self._page_signature = signature
            self.revision += 1
        current = None
        with suppress(Exception):
            current = self.browser.current_page().id
        items = []
        for page in pages:
            title = ""
            with suppress(Exception):
                title = await page.title()
            items.append({"pageId": page.id, "title": title, "url": page.url})
        return {"revision": self.revision, "targetPageId": current, "pages": items}

    async def page_command(self, command: dict[str, Any]) -> dict[str, Any]:
        expected = command.get("expectedRevision")
        current = await self.pages()
        if type(expected) is not int or expected != current["revision"]:
            raise ValueError("stale page revision")
        page_id = _required(command, "pageId")
        action = command.get("action")
        if action == "focus":
            page = next((item for item in self.browser.pages() if item.id == page_id), None)
            if page is None or page.closed:
                raise ValueError("page not found")
            await page.bring_to_front()
        elif action == "select":
            page = self.browser.select_page(page_id)
            await page.bring_to_front()
            self.revision += 1
        elif action == "navigate":
            page = self.browser.select_page(page_id)
            await page.goto(
                _required(command, "url"),
                wait_until="domcontentloaded",
                timeout_ms=15_000,
            )
        else:
            raise ValueError("invalid page action")
        return await self.pages()

    async def navigate(self, url: str) -> dict[str, Any]:
        page = self.browser.current_page()
        await page.goto(url, wait_until="domcontentloaded", timeout_ms=15_000)
        return {"success": True, "url": page.url}

    async def start_picker(self) -> None:
        context = self.browser._context  # Same provider boundary; never leaves worker.
        if not self.picker_active:
            await context.add_init_script(PICKER_SCRIPT)
        await context.add_init_script("window.__elementPickerDisabled = false;")
        for page in self.browser.pages():
            for frame in page.frames:
                with suppress(Exception):
                    await frame.evaluate("() => { window.__elementPickerDisabled = false; }")
                    await frame.evaluate(PICKER_SCRIPT)
        self.picker_active = True

    async def stop_picker(self) -> None:
        self.picker_active = False
        with suppress(Exception):
            await self.browser._context.add_init_script(
                "window.__elementPickerDisabled = true;"
            )
        script = """() => {
          window.__elementPickerDisabled=true; window.__elementPickerActive=false;
          window.__elementPickerResult=null; window.__elementPickerSimilar=null;
          ['__picker_tip','__picker_box','__picker_first_box','__picker_selected_box','__picker_style'].forEach(id=>document.getElementById(id)?.remove());
          document.querySelectorAll('.__picker_similar_box').forEach(el=>el.remove());
        }"""
        for page in self.browser.pages():
            for frame in page.frames:
                with suppress(Exception):
                    await frame.evaluate(script)

    async def picker_result(self, key: str) -> dict[str, Any]:
        if key not in {"__elementPickerResult", "__elementPickerSimilar"}:
            raise ValueError("invalid picker key")
        if self.picker_active:
            await self.start_picker()
        for page in self.browser.pages():
            frames = [page.main_frame, *page.frames]
            seen: set[int] = set()
            for frame in frames:
                identity = id(frame._raw)
                if identity in seen:
                    continue
                seen.add(identity)
                with suppress(Exception):
                    value = await frame.evaluate(f"() => window.{key} || null")
                    if isinstance(value, dict):
                        return {"selected": True, "value": value}
        return {"selected": False, "value": None}

    async def test_selector(self, command: dict[str, Any]) -> dict[str, Any]:
        selector = _required(command, "selector").strip()
        hints = command.get("hints")
        candidates = [selector]
        if isinstance(hints, dict):
            candidates.extend(
                candidate
                for candidate in fallback_selectors(hints)
                if candidate not in candidates
            )
        page = self.browser.current_page()
        tried: list[dict[str, Any]] = []
        for candidate in candidates:
            try:
                locator = page.locator(format_selector(candidate))
                count = await locator.count()
            except Exception as error:  # noqa: BLE001 -- syntax error is a test result.
                tried.append({"selector": candidate, "error": str(error)[:160]})
                continue
            tried.append({"selector": candidate, "count": count})
            if count == 0:
                continue
            first = locator.first
            element: dict[str, Any] = {}
            with suppress(Exception):
                element["tag"] = await first.evaluate(
                    "e => e.tagName ? e.tagName.toLowerCase() : ''"
                )
            with suppress(Exception):
                element["text"] = (await first.inner_text()).strip()[:120]
            if command.get("highlight", True):
                boxes = []
                for index in range(min(count, 100)):
                    with suppress(Exception):
                        box = await locator.nth(index).bounding_box()
                        if box:
                            boxes.append(box)
                if boxes:
                    with suppress(Exception):
                        await page.evaluate(f"({_OVERLAY_JS})({json.dumps(boxes)})")
            return {
                "success": True,
                "matched": True,
                "count": count,
                "matchedSelector": candidate,
                "isPrimary": candidate == selector,
                "element": element,
                "tried": tried,
            }
        return {"success": True, "matched": False, "count": 0, "tried": tried}


def _read(stream: TextIO) -> dict[str, Any]:
    raw = stream.readline()
    if not raw:
        raise EOFError
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("inspection command must be an object")
    return value


def _required(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a string")
    return value


def _write(stream: TextIO, value: dict[str, Any]) -> None:
    stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    stream.flush()
