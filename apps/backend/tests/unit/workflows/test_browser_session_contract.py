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
        self.listeners: dict[str, list[Any]] = {}

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

    def on(self, name: str, listener: Any) -> None:
        self.listeners.setdefault(name, []).append(listener)

    def remove_listener(self, name: str, listener: Any) -> None:
        self.listeners.get(name, []).remove(listener)

    def emit(self, name: str, value: Any) -> None:
        for listener in list(self.listeners.get(name, [])):
            listener(value)


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


def test_page_request_watch_filters_redacts_and_stops() -> None:
    raw = RawContext()
    session = CloakBrowserWorkflowSession.from_context(raw)
    page = raw.pages[0]
    watch = session.current_page().begin_request_watch(
        filter_type="api", url_pattern="/v1/"
    )

    page.emit(
        "request",
        SimpleNamespace(
            url="https://local.test/v1/items",
            method="POST",
            resource_type="fetch",
            headers={"authorization": "Bearer secret", "accept": "application/json"},
        ),
    )
    page.emit(
        "request",
        SimpleNamespace(
            url="https://local.test/v1/logo.png",
            method="GET",
            resource_type="image",
            headers={},
        ),
    )

    captured = watch.captured_requests()
    assert len(captured) == 1
    assert captured[0]["url"] == "https://local.test/v1/items"
    assert captured[0]["headers"] == {
        "authorization": "[已隐藏]",
        "accept": "application/json",
    }
    assert watch.active is True
    assert watch.overflowed is False

    watch.stop()
    page.emit(
        "request",
        SimpleNamespace(
            url="https://local.test/v1/after-stop",
            method="GET",
            resource_type="xhr",
            headers={},
        ),
    )
    assert len(watch.captured_requests()) == 1
    assert watch.active is False


def test_page_request_watch_reports_capacity_instead_of_silent_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "autoflow.providers.browser.workflow_session._MAX_CAPTURED_REQUESTS", 1
    )
    raw = RawContext()
    session = CloakBrowserWorkflowSession.from_context(raw)
    watch = session.current_page().begin_request_watch(
        filter_type="all", url_pattern=""
    )

    for suffix in ("first", "second"):
        raw.pages[0].emit(
            "request",
            SimpleNamespace(
                url=f"https://local.test/{suffix}",
                method="GET",
                resource_type="fetch",
                headers={},
            ),
        )

    assert len(watch.captured_requests()) == 1
    assert watch.overflowed is True
    watch.stop()


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


@pytest.mark.asyncio
async def test_workflow_worker_runs_pure_data_document_without_launching_browser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def reject_browser_launch(_command: dict[str, Any]) -> None:
        raise AssertionError("pure data workflow must not launch CloakBrowser")

    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    monkeypatch.setattr(
        "autoflow.providers.browser.workflow_worker.launch_workflow_session",
        reject_browser_launch,
    )
    command = {
        "runId": "run-data",
        "workflowId": "workflow-data",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": "concat",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "string_concat",
                        "config": {
                            "string1": "Auto",
                            "string2": "Flow",
                            "variableName": "joined",
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
    assert events[2]["data"] == "AutoFlow"


@pytest.mark.asyncio
async def test_workflow_worker_exports_list_and_emits_registered_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def reject_browser_launch(_command: dict[str, Any]) -> None:
        raise AssertionError("list export must not launch CloakBrowser")

    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    monkeypatch.setattr(
        "autoflow.providers.browser.workflow_worker.launch_workflow_session",
        reject_browser_launch,
    )
    artifact_root = tmp_path / "workspace"
    command = {
        "runId": "run-data-export",
        "workflowId": "workflow-data-export",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(artifact_root),
        "document": {
            "nodes": [
                {
                    "id": "export",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "list_export",
                        "config": {
                            "listVariable": "items",
                            "outputPath": "reports/result.txt",
                            "separator": "\\n",
                            "encoding": "utf-8",
                            "appendMode": False,
                        },
                    },
                }
            ],
            "edges": [],
            "variables": [{"name": "items", "value": ["第一条", "第二条"]}],
        },
    }
    output = io.StringIO()

    result = await _run(command, Event(), output)

    assert result == 0, output.getvalue()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [event["type"] for event in events] == [
        "ready",
        "execution:node_start",
        "artifact:registered",
        "execution:node_complete",
        "execution:completed",
    ]
    assert events[2]["nodeId"] == "export"
    assert events[2]["executionId"] == events[1]["executionId"]
    assert events[2]["artifactId"] in events[3]["artifactIds"]
    assert events[3]["data"] == {"path": "reports/result.txt", "count": 2}
    target = artifact_root / "runs/run-data-export/outputs/reports/result.txt"
    snapshot = artifact_root / events[2]["relativePath"]
    assert target.read_text(encoding="utf-8") == "第一条\n第二条"
    assert snapshot.read_bytes() == target.read_bytes()


@pytest.mark.asyncio
async def test_workflow_worker_runs_math_and_statistics_without_browser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def reject_browser_launch(_command: dict[str, Any]) -> None:
        raise AssertionError("pure math workflow must not launch CloakBrowser")

    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    monkeypatch.setattr(
        "autoflow.providers.browser.workflow_worker.launch_workflow_session",
        reject_browser_launch,
    )
    module_configs = [
        ("sum", "list_sum", {"listVariable": "numbers", "resultVariable": "sum"}),
        (
            "sort",
            "list_sort",
            {"listVariable": "numbers", "order": "desc", "resultVariable": "sorted"},
        ),
        (
            "round",
            "math_round",
            {"numberValue": "{sum}", "decimals": 1, "resultVariable": "rounded"},
        ),
        (
            "log",
            "math_log",
            {"value": "{rounded}", "base": "e", "resultVariable": "logarithm"},
        ),
        (
            "median",
            "stat_median",
            {"listVariable": "numbers", "resultVariable": "median"},
        ),
    ]
    command = {
        "runId": "run-math",
        "workflowId": "workflow-math",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": node_id,
                    "type": "moduleNode",
                    "data": {"moduleType": module_type, "config": config},
                }
                for node_id, module_type, config in module_configs
            ],
            "edges": [
                {
                    "id": f"edge-{index}",
                    "source": module_configs[index][0],
                    "target": module_configs[index + 1][0],
                }
                for index in range(len(module_configs) - 1)
            ],
            "variables": [{"name": "numbers", "value": [3, 1, 2]}],
        },
    }
    output = io.StringIO()

    result = await _run(command, Event(), output)

    assert result == 0, output.getvalue()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    completions = [
        event for event in events if event["type"] == "execution:node_complete"
    ]
    assert [event["nodeId"] for event in completions] == [
        "sum",
        "sort",
        "round",
        "log",
        "median",
    ]
    assert completions[0]["data"] == 6
    assert completions[1]["data"] == [3, 2, 1]
    assert completions[2]["data"] == 6.0
    assert completions[4]["data"] == 2.0
    assert events[-1]["type"] == "execution:completed"


@pytest.mark.asyncio
async def test_workflow_worker_runs_utility_tools_without_browser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def reject_browser_launch(_command: dict[str, Any]) -> None:
        raise AssertionError("pure utility workflow must not launch CloakBrowser")

    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    monkeypatch.setattr(
        "autoflow.providers.browser.workflow_worker.launch_workflow_session",
        reject_browser_launch,
    )
    module_configs = [
        (
            "md5",
            "md5_encrypt",
            {"inputText": "{text}", "outputFormat": "hex", "resultVariable": "md5"},
        ),
        (
            "sha",
            "sha_encrypt",
            {
                "inputText": "{md5}",
                "shaType": "sha256",
                "outputFormat": "hex",
                "resultVariable": "sha",
            },
        ),
        (
            "url",
            "url_encode_decode",
            {"inputText": "{sha}", "operation": "encode", "resultVariable": "url"},
        ),
        (
            "hsv",
            "rgb_to_hsv",
            {"r": 255, "g": 0, "b": 127, "resultVariable": "hsv"},
        ),
        (
            "uuid",
            "uuid_generator",
            {
                "uuidVersion": 5,
                "namespace": "dns",
                "name": "autoflow.cn",
                "resultVariable": "uuid",
            },
        ),
    ]
    command = {
        "runId": "run-utility",
        "workflowId": "workflow-utility",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": node_id,
                    "type": "moduleNode",
                    "data": {"moduleType": module_type, "config": config},
                }
                for node_id, module_type, config in module_configs
            ],
            "edges": [
                {
                    "id": f"edge-{index}",
                    "source": module_configs[index][0],
                    "target": module_configs[index + 1][0],
                }
                for index in range(len(module_configs) - 1)
            ],
            "variables": [{"name": "text", "value": "AutoFlow中文"}],
        },
    }
    output = io.StringIO()

    result = await _run(command, Event(), output)

    assert result == 0, output.getvalue()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    completions = [
        event for event in events if event["type"] == "execution:node_complete"
    ]
    assert [event["nodeId"] for event in completions] == [
        "md5",
        "sha",
        "url",
        "hsv",
        "uuid",
    ]
    assert completions[0]["data"] == "57979e746e277e6f10c20d7f9d3d03da"
    assert completions[3]["data"] == {
        "h": 330,
        "s": 100,
        "v": 100,
        "string": "HSV(330, 100%, 100%)",
    }
    assert completions[4]["data"] == "70cf9137-871f-540f-83f1-ed78acf150de"
    assert events[-1]["type"] == "execution:completed"


@pytest.mark.asyncio
async def test_workflow_worker_runs_advanced_data_without_browser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def reject_browser_launch(_command: dict[str, Any]) -> None:
        raise AssertionError("advanced data workflow must not launch CloakBrowser")

    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    monkeypatch.setattr(
        "autoflow.providers.browser.workflow_worker.launch_workflow_session",
        reject_browser_launch,
    )
    module_configs = [
        (
            "parse",
            "csv_parse",
            {
                "csvContent": "name,score\n甲,1\n乙,2\n丙,3",
                "hasHeader": True,
                "delimiter": ",",
                "resultVariable": "rows",
            },
        ),
        (
            "format-rows",
            "list_to_string_advanced",
            {
                "listVariable": "rows",
                "separator": "；",
                "resultVariable": "rowSummary",
            },
        ),
        (
            "filter",
            "list_filter",
            {
                "listVariable": "numbers",
                "condition": "x % 2 == 0",
                "resultVariable": "filtered",
            },
        ),
        (
            "map",
            "list_map",
            {
                "listVariable": "filtered",
                "expression": "x * 10",
                "resultVariable": "mapped",
            },
        ),
    ]
    command = {
        "runId": "run-advanced-data",
        "workflowId": "workflow-advanced-data",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": node_id,
                    "type": "moduleNode",
                    "data": {"moduleType": module_type, "config": config},
                }
                for node_id, module_type, config in module_configs
            ],
            "edges": [
                {
                    "id": f"edge-{index}",
                    "source": module_configs[index][0],
                    "target": module_configs[index + 1][0],
                }
                for index in range(len(module_configs) - 1)
            ],
            "variables": [{"name": "numbers", "value": [1, 2, 3, 4]}],
        },
    }
    output = io.StringIO()

    result = await _run(command, Event(), output)

    assert result == 0, output.getvalue()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    completions = [
        event for event in events if event["type"] == "execution:node_complete"
    ]
    assert [event["nodeId"] for event in completions] == [
        "parse",
        "format-rows",
        "filter",
        "map",
    ]
    assert completions[0]["data"] == [
        {"name": "甲", "score": "1"},
        {"name": "乙", "score": "2"},
        {"name": "丙", "score": "3"},
    ]
    assert completions[1]["data"] == (
        "{'name': '甲', 'score': '1'}；"
        "{'name': '乙', 'score': '2'}；"
        "{'name': '丙', 'score': '3'}"
    )
    assert completions[2]["data"] == [2, 4]
    assert completions[3]["data"] == [20, 40]
    assert events[-1]["type"] == "execution:completed"


@pytest.mark.asyncio
async def test_workflow_worker_reports_non_json_math_result_as_node_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def reject_browser_launch(_command: dict[str, Any]) -> None:
        raise AssertionError("pure math workflow must not launch CloakBrowser")

    monkeypatch.setattr(
        "autoflow.providers.browser.workflow_worker.launch_workflow_session",
        reject_browser_launch,
    )
    command = {
        "runId": "run-unsafe-math",
        "workflowId": "workflow-unsafe-math",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": "unsafe",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "math_sqrt",
                        "config": {
                            "numberValue": -8,
                            "root": 3,
                            "resultVariable": "result",
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

    assert result == 2, output.getvalue()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert events[-2]["type"] == "execution:node_complete"
    assert events[-2]["success"] is False
    assert events[-2]["data"] is None
    assert events[-2]["error"] == "节点结果包含无法序列化的数据"
    assert events[-1]["type"] == "execution:failed"
    assert events[-1]["failedNodeId"] == "unsafe"


@pytest.mark.asyncio
async def test_workflow_worker_runs_table_family_and_registers_excel_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def reject_browser_launch(_command: dict[str, Any]) -> None:
        raise AssertionError("table workflow must not launch CloakBrowser")

    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    monkeypatch.setattr(
        "autoflow.providers.browser.workflow_worker.launch_workflow_session",
        reject_browser_launch,
    )
    module_configs = [
        ("add-first", "table_add_row", {"rowData": '{"name":"甲","score":1}'}),
        ("add-second", "table_add_row", {"rowData": '{"name":"乙","score":2}'}),
        (
            "add-column",
            "table_add_column",
            {"columnName": "enabled", "defaultValue": True},
        ),
        (
            "set-cell",
            "table_set_cell",
            {"rowIndex": 1, "columnName": "score", "cellValue": 3},
        ),
        (
            "get-cell",
            "table_get_cell",
            {"rowIndex": 1, "columnName": "score", "variableName": "score"},
        ),
        (
            "export",
            "table_export",
            {
                "exportFormat": "excel",
                "savePath": "reports/result.xlsx",
                "sheetName": "结果",
                "variableName": "path",
            },
        ),
    ]
    artifact_root = tmp_path / "artifacts"
    command = {
        "runId": "run-table",
        "workflowId": "workflow-table",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(artifact_root),
        "document": {
            "nodes": [
                {
                    "id": node_id,
                    "type": "moduleNode",
                    "data": {"moduleType": module_type, "config": config},
                }
                for node_id, module_type, config in module_configs
            ],
            "edges": [
                {
                    "id": f"edge-{index}",
                    "source": module_configs[index][0],
                    "target": module_configs[index + 1][0],
                }
                for index in range(len(module_configs) - 1)
            ],
            "variables": [],
        },
    }
    output = io.StringIO()

    result = await _run(command, Event(), output)

    assert result == 0, output.getvalue()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    completions = [
        event for event in events if event["type"] == "execution:node_complete"
    ]
    assert [event["nodeId"] for event in completions] == [
        node_id for node_id, _, _ in module_configs
    ]
    assert completions[4]["data"] == 3
    assert len(completions[5]["artifactIds"]) == 1
    target = artifact_root / "runs/run-table/outputs/reports/result.xlsx"
    assert target.read_bytes().startswith(b"PK")
    artifact_events = [
        event for event in events if event["type"] == "artifact:registered"
    ]
    assert len(artifact_events) == 1
    assert artifact_events[0]["mimeType"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert Path(artifact_root / artifact_events[0]["relativePath"]).read_bytes() == (
        target.read_bytes()
    )
    assert events[-1]["type"] == "execution:completed"
