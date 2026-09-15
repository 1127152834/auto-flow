from __future__ import annotations

import io
import json
import sys
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import pytest
from autoflow.domain.workflows.browser import CurrentPageClosed, UnknownPage
from autoflow.providers.browser.workflow_session import CloakBrowserWorkflowSession
from autoflow.providers.browser.workflow_worker import _run, run_workflow_worker


class RawPage:
    def __init__(self, url: str) -> None:
        self.url = url
        self.closed = False
        self.goto_calls: list[tuple[str, dict[str, Any]]] = []
        self.download = SimpleNamespace(
            suggested_filename="report.csv",
            save_as=self._save_download,
        )
        self.saved_download: str | None = None

    def is_closed(self) -> bool:
        return self.closed

    async def goto(self, url: str, **options: Any) -> None:
        self.url = url
        self.goto_calls.append((url, options))

    async def bring_to_front(self) -> None:
        return None

    async def _save_download(self, path: str) -> None:
        self.saved_download = path

    def expect_download(self) -> AbstractAsyncContextManager[Any]:
        download = self.download

        class ExpectedDownload:
            async def __aenter__(self) -> Any:
                return SimpleNamespace(value=_value())

            async def __aexit__(self, *_args: object) -> None:
                return None

        async def _value() -> Any:
            return download

        return ExpectedDownload()


class RawContext:
    def __init__(self) -> None:
        self.pages = [RawPage("about:blank")]
        self.closed = 0

    async def new_page(self) -> RawPage:
        page = RawPage("about:blank")
        self.pages.append(page)
        return page

    async def close(self) -> None:
        self.closed += 1


@pytest.mark.asyncio
async def test_session_uses_stable_page_ids_and_requires_explicit_selection() -> None:
    raw = RawContext()
    session = CloakBrowserWorkflowSession.from_context(raw)

    first = session.current_page()
    second = await session.new_page()

    assert first.id != second.id
    assert session.current_page().id == second.id
    assert [page.id for page in session.pages()] == [first.id, second.id]
    assert session.select_page(first.id).id == first.id
    with pytest.raises(UnknownPage):
        session.select_page("missing")


@pytest.mark.asyncio
async def test_closed_current_page_does_not_silently_fall_back() -> None:
    raw = RawContext()
    session = CloakBrowserWorkflowSession.from_context(raw)
    first = session.current_page()
    await session.new_page()
    session.select_page(first.id)
    raw.pages[0].closed = True
    raw.pages.pop(0)

    with pytest.raises(CurrentPageClosed):
        session.current_page()


@pytest.mark.asyncio
async def test_session_closes_context_once() -> None:
    raw = RawContext()
    session = CloakBrowserWorkflowSession.from_context(raw)

    await session.close()
    await session.close()

    assert raw.closed == 1


@pytest.mark.asyncio
async def test_page_download_port_captures_action_and_saves_explicit_path(
    tmp_path: Path,
) -> None:
    raw = RawContext()
    session = CloakBrowserWorkflowSession.from_context(raw)
    action_calls: list[str] = []

    async def action() -> None:
        action_calls.append("clicked")

    download = await session.current_page().capture_download(action)
    target = tmp_path / "report.csv"
    await download.save_as(target)

    assert action_calls == ["clicked"]
    assert download.suggested_filename == "report.csv"
    assert raw.pages[0].saved_download == str(target)


def test_workflow_worker_launches_only_cloakbrowser_with_frozen_profile_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")
    cache = tmp_path / "run"
    cache.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))
    captured: dict[str, Any] = {}

    class Context(RawContext):
        async def close(self) -> None:
            captured["closed"] = True

    async def launch_context_async(**options: Any) -> Context:
        captured.update(options)
        return Context()

    monkeypatch.setitem(
        sys.modules,
        "cloakbrowser",
        SimpleNamespace(launch_context_async=launch_context_async),
    )
    command = {
        "runId": "run-real-provider",
        "profileId": "profile-1",
        "fingerprintSeed": 54321,
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "geoip": False,
        "humanize": True,
        "humanPreset": "default",
        "userAgent": "AutoFlow",
        "viewport": {"width": 1280, "height": 720},
        "colorScheme": "dark",
        "extensionPaths": [],
        "expertArgs": [],
        "browserVersion": "145.0.7632.109",
        "releaseChannel": "stable",
        "proxy": None,
        "licenseKey": None,
        "headless": True,
    }
    stopped = Event()
    stopped.set()
    output = io.StringIO()

    result = run_workflow_worker(
        stopped, io.StringIO(json.dumps(command) + "\n"), output
    )

    assert result == 0, output.getvalue()
    assert json.loads(output.getvalue()) == {
        "type": "ready",
        "runId": "run-real-provider",
        "profileId": "profile-1",
    }
    assert captured == {
        "headless": True,
        "args": ["--accept-lang=zh-CN", "--fingerprint=54321"],
        "stealth_args": True,
        "user_agent": "AutoFlow",
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "color_scheme": "dark",
        "geoip": False,
        "humanize": True,
        "human_preset": "default",
        "extension_paths": [],
        "license_key": None,
        "browser_version": "145.0.7632.109",
        "release_channel": "stable",
        "viewport": {"width": 1280, "height": 720},
        "proxy": None,
        "closed": True,
    }


def test_workflow_worker_rejects_uncontrolled_browser_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    output = io.StringIO()

    result = run_workflow_worker(
        Event(),
        io.StringIO(json.dumps({"runId": "run", "profileId": "profile"}) + "\n"),
        output,
    )

    assert result == 1
    assert json.loads(output.getvalue()) == {
        "type": "error",
        "error": "Workflow worker failed",
    }


@pytest.mark.asyncio
async def test_workflow_worker_executes_document_and_emits_identified_events(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")
    cache = tmp_path / "run"
    cache.mkdir()
    artifacts = tmp_path / "workspace"
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))
    raw = RawContext()

    async def launch_context_async(**_options: Any) -> RawContext:
        return raw

    monkeypatch.setitem(
        sys.modules,
        "cloakbrowser",
        SimpleNamespace(launch_context_async=launch_context_async),
    )
    command = {
        "runId": "run-execute",
        "workflowId": "workflow-execute",
        "profileId": "profile-1",
        "fingerprintSeed": 54321,
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "geoip": False,
        "humanize": False,
        "humanPreset": "default",
        "userAgent": None,
        "viewport": None,
        "colorScheme": None,
        "extensionPaths": [],
        "expertArgs": [],
        "browserVersion": "145.0.7632.109",
        "releaseChannel": "stable",
        "proxy": None,
        "licenseKey": None,
        "headless": True,
        "artifactRoot": str(artifacts),
        "document": {
            "nodes": [
                {
                    "id": "open",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "open_page",
                        "config": {
                            "url": "https://example.test/worker",
                            "openMode": "current_tab",
                        },
                    },
                }
            ],
            "edges": [],
            "variables": [],
        },
    }
    output = io.StringIO()

    result = await _run(command, Event(), output)

    assert result == 0, output.getvalue()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [event["type"] for event in events] == [
        "ready",
        "execution:node_start",
        "execution:node_complete",
        "execution:completed",
    ]
    assert events[1]["runId"] == events[2]["runId"] == "run-execute"
    assert events[1]["executionId"] == events[2]["executionId"]
    assert events[2]["success"] is True
    assert events[3]["executedNodes"] == 1
    assert raw.pages[0].goto_calls[0][0] == "https://example.test/worker"
