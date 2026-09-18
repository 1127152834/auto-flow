from __future__ import annotations

import asyncio
import io
import json
import sys
import threading
from types import SimpleNamespace
from typing import Self

import pytest

from autoflow.providers.browser.workflow_executor import WorkflowExecutor
from autoflow.providers.browser.project_workflow_worker import _run, run_worker


class Locator:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.first = self

    async def fill(self, value: str) -> None:
        self.page.value = value
        self.page.calls.append(("fill", value))

    async def press_sequentially(self, value: str) -> None:
        # Playwright types at the current caret; a fresh locator need not place it last.
        self.page.value = value + self.page.value
        self.page.calls.append(("append", value))

    async def click(self, **kwargs: object) -> None:
        self.page.calls.append(("click", kwargs))

    async def dblclick(self) -> None:
        self.page.calls.append(("double",))

    async def input_value(self) -> str:
        return self.page.value

    async def evaluate(self, script: str, attribute: str) -> object:
        self.page.calls.append(("evaluate", attribute))
        return {"text": "Hello world", "innerHTML": "<strong>Hello</strong> world", "attributes": {"data-kind": "fixture"}}.get(attribute, "42")


class Page:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.value = "before"
        self.closed = False
        self.listeners: dict[str, list[object]] = {}
        self.goto_delay = 0.0

    def is_closed(self) -> bool:
        return self.closed

    async def goto(self, url: str, **kwargs: object) -> None:
        await asyncio.sleep(self.goto_delay)
        self.calls.append(("goto", url, kwargs))

    async def screenshot(self, **kwargs: object) -> bytes:
        self.calls.append(("screenshot", kwargs))
        return b"png"

    def locator(self, selector: str) -> Locator:
        self.calls.append(("locator", selector))
        return Locator(self)

    def on(self, event: str, callback: object) -> None:
        self.listeners.setdefault(event, []).append(callback)

    def remove_listener(self, event: str, callback: object) -> None:
        self.listeners[event].remove(callback)


class Context:
    def __init__(self) -> None:
        self.pages: list[Page] = []
        self.closed = False
        self.default_timeout: int | None = None
        self.navigation_timeout: int | None = None

    def set_default_timeout(self, timeout: int) -> None:
        self.default_timeout = timeout

    def set_default_navigation_timeout(self, timeout: int) -> None:
        self.navigation_timeout = timeout

    async def new_page(self) -> Page:
        page = Page()
        self.pages.append(page)
        return page

    async def close(self) -> None:
        self.closed = True


def plan(*nodes: dict[str, object]) -> dict[str, object]:
    return {"orderedNodeIds": [node["nodeId"] for node in nodes], "nodes": list(nodes)}


def node(node_id: str, module_type: str, **data: object) -> dict[str, object]:
    return {"nodeId": node_id, "moduleType": module_type, "data": {"timeout": 0, **data}}


@pytest.mark.asyncio
async def test_four_nodes_current_page_append_variables_and_output() -> None:
    context, events = Context(), []

    async def emit(*event: object) -> None:
        events.append(event)

    execution = plan(
        node("open", "open_page", url="https://example.test/{id}", openMode="current_tab", waitUntil="domcontentloaded"),
        node("input", "input_text", selector="#field", text="-{suffix}", clearBefore=False),
        node("click", "click_element", selector="#button", clickType="right", followNewTab=False),
        node("read", "get_element_info", selector="#result", attribute="data-answer", variableName="answer"),
    )
    result = await WorkflowExecutor(context, {"id": 7, "suffix": True}, emit, lambda: False).run(execution)
    assert result == {"status": "succeeded", "error": None}
    assert len(context.pages) == 1
    assert context.pages[0].value == "before-true"
    assert context.pages[0].calls[:2] == [("goto", "https://example.test/7", {"wait_until": "domcontentloaded"}), ("locator", "#field")]
    assert ("click", {"button": "right"}) in context.pages[0].calls
    output = next(event for event in events if event[0] == "output")
    assert output[3] == {"name": "answer", "value": "42"}


@pytest.mark.asyncio
async def test_timeout_zero_is_unlimited_and_replacement_is_not_recursive() -> None:
    context = Context()
    executor = WorkflowExecutor(context, {"first": "{second}", "second": "wrong"}, lambda *_: asyncio.sleep(0), lambda: False)
    result = await executor.run(plan(node("open", "open_page", url="https://x/{first}")))
    assert result["status"] == "succeeded"
    assert context.pages[0].calls[0][1] == "https://x/{second}"


@pytest.mark.asyncio
async def test_nonzero_timeout_is_measured_in_seconds() -> None:
    context = Context()
    original = context.new_page

    async def delayed_page() -> Page:
        page = await original()
        page.goto_delay = 0.01
        return page

    context.new_page = delayed_page  # type: ignore[method-assign]
    executor = WorkflowExecutor(context, {}, lambda *_: asyncio.sleep(0), lambda: False)
    result = await executor.run(plan(node("open", "open_page", timeout=1, url="https://x")))
    assert result == {"status": "succeeded", "error": None}


@pytest.mark.asyncio
async def test_fractional_second_timeout_is_not_truncated_to_zero() -> None:
    context = Context()
    original = context.new_page

    async def delayed_page() -> Page:
        page = await original()
        page.goto_delay = 0.05
        return page

    context.new_page = delayed_page  # type: ignore[method-assign]
    executor = WorkflowExecutor(context, {}, lambda *_: asyncio.sleep(0), lambda: False)
    result = await executor.run(plan(node("open", "open_page", timeout=0.02, url="https://x")))
    assert result["status"] == "failed"
    assert result["error"]["code"] == "WORKFLOW_NODE_TIMEOUT"


@pytest.mark.asyncio
async def test_worker_disables_playwright_default_timeouts_for_zero_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    executable, cache, context = tmp_path / "chrome", tmp_path / "cache", Context()
    executable.write_bytes(b"x")
    cache.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))

    async def launch(**_: object) -> Context:
        return context

    monkeypatch.setitem(
        sys.modules, "cloakbrowser", _fake_cloakbrowser(launch)
    )
    output = io.StringIO()

    class Ack:
        async def next(self) -> dict[str, object]:
            event = json.loads(output.getvalue().splitlines()[-1])["event"]
            return {"type": "event_committed", "eventId": event["eventId"], "executionGeneration": 3}

    assert await _run(command(), threading.Event(), Ack(), output) == 0
    assert context.default_timeout == 0
    assert context.navigation_timeout == 0


@pytest.mark.asyncio
async def test_stop_at_safe_point_does_not_start_next_node() -> None:
    context, started, stopped = Context(), [], False

    async def emit(kind: str, node_id: str, visit: str, payload: dict[str, object]) -> None:
        nonlocal stopped
        if kind == "nodeAttempt" and payload["status"] == "started":
            started.append(node_id)
        if kind == "nodeAttempt" and node_id == "one" and payload["status"] == "succeeded":
            stopped = True

    result = await WorkflowExecutor(context, {}, emit, lambda: stopped).run(plan(
        node("one", "open_page", url="https://one"), node("two", "open_page", url="https://two")
    ))
    assert result["status"] == "cancelled"
    assert started == ["one"]


@pytest.mark.asyncio
async def test_stop_while_start_log_waits_for_ack_then_skips_action() -> None:
    context, stopped = Context(), False

    async def emit(kind: str, _node_id: str, _visit: str, payload: dict[str, object]) -> None:
        nonlocal stopped
        if kind == "log" and payload["message"] == "开始执行节点":
            stopped = True

    result = await WorkflowExecutor(context, {}, emit, lambda: stopped).run(
        plan(node("open", "open_page", url="https://must-not-open"))
    )
    assert result == {"status": "cancelled", "error": None}
    assert context.pages == []


@pytest.mark.asyncio
async def test_stop_while_started_event_waits_for_ack_then_skips_action() -> None:
    context, stopped = Context(), False

    async def emit(kind: str, _node_id: str, _visit: str, payload: dict[str, object]) -> None:
        nonlocal stopped
        if kind == "nodeAttempt" and payload["status"] == "started":
            stopped = True

    result = await WorkflowExecutor(context, {}, emit, lambda: stopped).run(
        plan(node("open", "open_page", url="https://must-not-open"))
    )
    assert result == {"status": "cancelled", "error": None}
    assert context.pages == []


class Incoming:
    def __init__(self, messages: list[dict[str, object] | Exception]) -> None:
        self.messages = iter(messages)

    async def next(self) -> dict[str, object]:
        value = next(self.messages)
        if isinstance(value, Exception):
            raise value
        return value

def _fake_cloakbrowser(launch, persistent=None):
    """The worker imports both launchers; a missing one breaks the whole run."""

    async def unexpected_persistent(**_: object) -> Context:
        raise AssertionError("persistent launch was not expected")

    return SimpleNamespace(
        launch_context_async=launch,
        launch_persistent_context_async=persistent or unexpected_persistent,
    )


def command() -> dict[str, object]:
    browser = {
        "headless": True, "fingerprintSeed": 12345, "expertArgs": [], "geoip": False,
        "humanize": False, "humanPreset": "default", "extensionPaths": [],
        "browserVersion": "145", "releaseChannel": "stable",
    }
    return {"type": "start", "protocolVersion": 1, "runId": "run", "executionGeneration": 3,
            "executionPlan": plan(node("open", "open_page", url="https://one")),
            "parameters": {}, "variables": {}, "browser": browser}


@pytest.mark.asyncio
async def test_worker_envelopes_ack_gate_and_cleanup(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    executable, cache, context = tmp_path / "chrome", tmp_path / "cache", Context()
    executable.write_bytes(b"x"); cache.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable)); monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))
    async def launch(**_: object) -> Context:
        return context

    monkeypatch.setitem(sys.modules, "cloakbrowser", _fake_cloakbrowser(launch))

    class Ack:
        async def next(self) -> dict[str, object]:
            while not output.getvalue().splitlines(): await asyncio.sleep(0)
            event = json.loads(output.getvalue().splitlines()[-1])
            while event["type"] != "event":
                await asyncio.sleep(0); event = json.loads(output.getvalue().splitlines()[-1])
            return {"type": "event_committed", "eventId": event["event"]["eventId"], "executionGeneration": 3}

    output = io.StringIO()
    assert await _run(command(), threading.Event(), Ack(), output) == 0
    decoded = [json.loads(line) for line in output.getvalue().splitlines()]
    assert decoded[0] == {"type": "ready", "protocolVersion": 1, "runId": "run", "executionGeneration": 3}
    assert all(message.get("protocolVersion") == 1 for message in decoded if message["type"] != "error")
    assert decoded[-1]["status"] == "succeeded" and decoded[-1]["cleanupConfirmed"] is True
    assert context.closed and cache.exists()


@pytest.mark.asyncio
async def test_invalid_ack_stops_before_web_action_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    executable, cache, context = tmp_path / "chrome", tmp_path / "cache", Context()
    executable.write_bytes(b"x")
    cache.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))

    async def launch(**_: object) -> Context:
        return context

    monkeypatch.setitem(
        sys.modules, "cloakbrowser", _fake_cloakbrowser(launch)
    )
    incoming = Incoming(
        [{"type": "event_committed", "eventId": "wrong", "executionGeneration": 3}]
    )
    output = io.StringIO()
    assert await _run(command(), threading.Event(), incoming, output) == 1
    assert context.pages == []
    assert context.closed and cache.exists()
    finished = json.loads(output.getvalue().splitlines()[-1])
    assert finished["error"]["code"] == "WORKFLOW_PARENT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_node_failure_emits_failed_evidence_then_cleans_up() -> None:
    context, events = Context(), []

    async def closed_page() -> Page:
        page = Page()
        page.closed = True
        context.pages.append(page)
        return page

    context.new_page = closed_page  # type: ignore[method-assign]

    async def emit(*event: object) -> None:
        events.append(event)

    result = await WorkflowExecutor(context, {}, emit, lambda: False).run(
        plan(node("read", "get_element_info", selector="#missing"))
    )
    assert result["status"] == "failed"
    assert events[-1][0] == "nodeAttempt"
    assert events[-1][3]["status"] == "failed"
    assert events[-1][3]["error"]["code"] == "WORKFLOW_PAGE_CLOSED"


@pytest.mark.asyncio
async def test_worker_captures_failure_screenshot_before_closing_browser(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    executable, cache, context = tmp_path / "chrome", tmp_path / "cache", Context()
    artifact_directory = tmp_path / "workspace" / "runs" / "run" / "generation-3"
    executable.write_bytes(b"x")
    cache.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))
    monkeypatch.setenv("AUTOFLOW_WORKFLOW_ARTIFACT_DIR", str(artifact_directory))
    monkeypatch.setenv(
        "AUTOFLOW_WORKFLOW_ARTIFACT_RELATIVE_DIR", "runs/run/generation-3"
    )

    class FailingPage(Page):
        async def goto(self, url: str, **kwargs: object) -> None:
            raise RuntimeError("secret browser failure")

        async def screenshot(self, **kwargs: object) -> bytes:
            assert context.closed is False
            return b"failure-png"

    async def new_page() -> Page:
        page = FailingPage()
        context.pages.append(page)
        return page

    context.new_page = new_page  # type: ignore[method-assign]

    async def launch(**_: object) -> Context:
        return context

    monkeypatch.setitem(
        sys.modules, "cloakbrowser", _fake_cloakbrowser(launch)
    )
    output = io.StringIO()

    class Ack:
        async def next(self) -> dict[str, object]:
            event = json.loads(output.getvalue().splitlines()[-1])["event"]
            return {
                "type": "event_committed",
                "eventId": event["eventId"],
                "executionGeneration": 3,
            }

    assert await _run(command(), threading.Event(), Ack(), output) == 1
    events = [
        message["event"]
        for message in map(json.loads, output.getvalue().splitlines())
        if message["type"] == "event"
    ]
    artifact = next(event for event in events if event["kind"] == "artifact")
    assert artifact["payload"]["availability"] == "available"
    assert artifact["payload"]["relativePath"].startswith(
        "runs/run/generation-3/"
    )
    assert "secret" not in json.dumps(artifact)
    assert (
        tmp_path / "workspace" / artifact["payload"]["relativePath"]
    ).read_bytes() == b"failure-png"
    assert context.closed is True


def test_run_worker_rejects_eof_and_oversized_jsonl_without_traceback() -> None:
    for raw in ("", "{" + "x" * (1024 * 1024) + "}\n"):
        output = io.StringIO()
        assert run_worker(threading.Event(), io.StringIO(raw), output) == 1
        assert json.loads(output.getvalue())["code"] == "WORKFLOW_WORKER_FAILED"


@pytest.mark.asyncio
async def test_cleanup_failure_has_identity_and_never_claims_finished(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    executable, cache = tmp_path / "chrome", tmp_path / "cache"
    executable.write_bytes(b"x")
    cache.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))

    class BadContext(Context):
        async def close(self) -> None:
            raise RuntimeError("secret path")

    async def launch(**_: object) -> Context:
        return BadContext()

    monkeypatch.setitem(
        sys.modules, "cloakbrowser", _fake_cloakbrowser(launch)
    )

    class Ack:
        def __init__(self, output: io.StringIO) -> None:
            self.output = output

        async def next(self) -> dict[str, object]:
            event = json.loads(self.output.getvalue().splitlines()[-1])["event"]
            return {
                "type": "event_committed",
                "eventId": event["eventId"],
                "executionGeneration": 3,
            }

    output = io.StringIO()
    assert await _run(command(), threading.Event(), Ack(output), output) == 1
    decoded = [json.loads(line) for line in output.getvalue().splitlines()]
    assert decoded[-1] == {
        "type": "error",
        "protocolVersion": 1,
        "runId": "run",
        "executionGeneration": 3,
        "code": "WORKFLOW_CLEANUP_FAILED",
        "message": "工作流资源清理失败",
    }
    assert not any(message["type"] == "finished" for message in decoded)


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_ack", [True, False])
async def test_proxy_relay_exit_failure_never_claims_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path, valid_ack: bool
) -> None:
    executable, cache, context = tmp_path / "chrome", tmp_path / "cache", Context()
    executable.write_bytes(b"x")
    cache.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))

    async def launch(**_: object) -> Context:
        return context

    class BadRelay:
        url = "http://127.0.0.1:1"

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            raise OSError("secret relay failure")

    monkeypatch.setitem(
        sys.modules, "cloakbrowser", _fake_cloakbrowser(launch)
    )
    monkeypatch.setattr(
        "autoflow.providers.browser.project_workflow_worker.BrowserProxyRelay",
        lambda _: BadRelay(),
    )
    payload = command()
    payload["browser"] = {**payload["browser"], "proxy": {"server": "http://upstream", "username": "u", "password": "p"}}
    output = io.StringIO()

    class Ack:
        async def next(self) -> dict[str, object]:
            event = json.loads(output.getvalue().splitlines()[-1])["event"]
            return {"type": "event_committed", "eventId": event["eventId"], "executionGeneration": 3}

    incoming = Ack() if valid_ack else Incoming(
        [{"type": "event_committed", "eventId": "wrong", "executionGeneration": 3}]
    )
    assert await _run(payload, threading.Event(), incoming, output) == 1
    decoded = [json.loads(line) for line in output.getvalue().splitlines()]
    assert decoded[-1]["code"] == "WORKFLOW_CLEANUP_FAILED"
    assert not any(message["type"] == "finished" for message in decoded)


@pytest.mark.asyncio
async def test_worker_opens_saved_environment_directory_as_persistent_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    executable, cache, context = tmp_path / "chrome", tmp_path / "cache", Context()
    executable.write_bytes(b"x")
    cache.mkdir()
    work_directory = tmp_path / "instance"
    work_directory.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))
    seen: list[dict[str, object]] = []

    async def persistent(**kwargs: object) -> Context:
        seen.append(kwargs)
        return context

    async def ephemeral(**_: object) -> Context:
        raise AssertionError("a saved environment must not start an ephemeral context")

    monkeypatch.setitem(
        sys.modules, "cloakbrowser", _fake_cloakbrowser(ephemeral, persistent)
    )
    output = io.StringIO()

    class Ack:
        async def next(self) -> dict[str, object]:
            event = json.loads(output.getvalue().splitlines()[-1])["event"]
            return {"type": "event_committed", "eventId": event["eventId"], "executionGeneration": 3}

    payload = command()
    payload["browser"]["userDataDir"] = str(work_directory)  # type: ignore[index]
    assert await _run(payload, threading.Event(), Ack(), output) == 0
    assert seen and seen[0]["user_data_dir"] == str(work_directory)
    assert context.closed
