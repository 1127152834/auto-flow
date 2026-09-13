import asyncio
import io
import json
import os
import sys
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.workflows.catalog import node_catalog
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import PreparedWorkflow
from autoflow.infrastructure.filesystem.workflow_artifacts import (
    WorkflowArtifacts,
    artifact_path,
)
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager
from autoflow.providers.browser.workflow_executor import WorkflowExecutor
from autoflow.providers.browser.workflow_worker import _run


def node(kind, **config):
    default = next(item["defaultConfig"] for item in node_catalog() if item["type"] == kind)
    return {"id": kind, "type": kind, "config": {**default, **config}}


def prepared(*nodes):
    return PreparedWorkflow({"nodes": list(nodes)}, [n["id"] for n in nodes], {}, [])


def profile(values):
    now = datetime.now(UTC)
    return Profile("profile-1", ProfileSpec.from_values(values), 12345, now, now)


class Locator:
    async def count(self):
        return 1

    def __init__(self, page):
        self.page = page
        self.first = self

    def locator(self, selector):
        self.page.calls.append(("nested", selector))
        return self

    async def wait_for(self, **kwargs):
        self.page.calls.append(("wait", kwargs))
        await asyncio.sleep(self.page.delay)

    async def evaluate(self, script, *args, **kwargs):
        self.page.calls.append(("evaluate", script, args, kwargs))
        await asyncio.sleep(self.page.delay)
        if "el.matches" in script:
            return self.page.direct
        return self.page.value

    async def input_value(self, **kwargs):
        return self.page.value

    async def click(self, **kwargs):
        self.page.calls.append(("click", kwargs))
        if self.page.popup:
            for callback in self.page.listeners.get("popup", []):
                callback(self.page.popup)

    async def dblclick(self, **kwargs):
        self.page.calls.append(("double", kwargs))

    async def fill(self, text, **kwargs):
        self.page.value = text
        self.page.calls.append(("fill", text, kwargs))

    async def screenshot(self, **kwargs):
        self.page.calls.append(("element_png", kwargs))
        return b"\x89PNG\r\n\x1a\nfixture"


class Page:
    def __init__(self):
        self.calls = []
        self.closed = False
        self.delay = 0
        self.direct = True
        self.value = "original"
        self.popup = None
        self.listeners = {}

    def is_closed(self):
        return self.closed

    def locator(self, selector):
        self.calls.append(("selector", selector))
        return Locator(self)

    async def goto(self, url, **kwargs):
        self.calls.append(("goto", url, kwargs))

    async def screenshot(self, **kwargs):
        self.calls.append(("page_png", kwargs))
        return b"\x89PNG\r\n\x1a\nfixture"

    def on(self, event, callback):
        self.listeners.setdefault(event, []).append(callback)

    def remove_listener(self, event, callback):
        self.listeners[event].remove(callback)


class Context:
    def __init__(self):
        self.pages = []
        self.closed = False

    async def new_page(self):
        page = Page()
        self.pages.append(page)
        return page

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_executor_six_nodes_order_variables_and_file_references(tmp_path):
    context, events, variables = Context(), [], {}
    executor = WorkflowExecutor(context, WorkflowArtifacts(tmp_path, "run"), variables, events.append)
    nodes = [
        node("open_page", url="http://localhost/example", openMode="current_tab"),
        node("click_element", selector="xpath=//button", clickType="right"),
        node("input_text", selector="#field", text="example"),
        node("wait_element", selector="#field", waitCondition="hidden"),
        node("get_element_info", selector="#field", attribute="value", variableName="value"),
        node("screenshot", screenshotType="viewport", savePath="{value}.PNG"),
    ]
    snapshot = deepcopy(nodes)
    result = await executor.run({"nodes": nodes}, [n["id"] for n in nodes])
    assert result == {"state": "succeeded", "error": None}
    assert nodes == snapshot
    assert len(context.pages) == 1
    assert variables["value"] == "example"
    assert Path(variables["screenshot_path"]).name == "example.PNG"
    assert [event["type"] for event in events] == ["ready"] + [
        kind for _ in nodes for kind in ("node_started", "node_succeeded")
    ]
    artifacts = [event["artifact"] for event in events if "artifact" in event]
    assert len(artifacts) == 2
    assert json.loads(artifact_path(tmp_path, "run", artifacts[0]["relativePath"]).read_text()) == "example"
    assert artifact_path(tmp_path, "run", artifacts[1]["relativePath"]).read_bytes().startswith(b"\x89PNG")
    assert any(call[:2] == ("selector", "xpath=//button") for call in context.pages[0].calls)
    assert any(call[0] == "click" and call[1]["button"] == "right" for call in context.pages[0].calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("clear,text,expected", [(True, "", ""), (False, " suffix", "original suffix"), (False, "", "original")])
async def test_input_targets_editable_descendant_without_keyboard_fallback(tmp_path, clear, text, expected):
    context = Context()
    executor = WorkflowExecutor(context, WorkflowArtifacts(tmp_path, "run"), {}, lambda _: None)
    executor.page = await context.new_page()
    executor.page.direct = False
    executor.deadline = asyncio.get_running_loop().time() + 1
    await executor._execute("input_text", "input", node("input_text", selector="#container", clearBefore=clear, text=text)["config"])
    assert executor.page.value == expected
    assert any(call[0] == "nested" for call in executor.page.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ["visible", "hidden", "attached", "detached"])
async def test_wait_conditions_are_passed_through(tmp_path, condition):
    context = Context()
    executor = WorkflowExecutor(context, WorkflowArtifacts(tmp_path, "run"), {}, lambda _: None)
    step = node("wait_element", selector=".x", waitCondition=condition)
    assert (await executor.run({"nodes": [step]}, [step["id"]]))["state"] == "succeeded"
    assert context.pages[0].calls[-1][1]["state"] == condition


@pytest.mark.asyncio
async def test_total_timeout_includes_all_input_suboperations(tmp_path):
    events = []
    context = Context()
    original = context.new_page

    async def delayed_page():
        page = await original()
        page.delay = 0.035
        return page

    context.new_page = delayed_page
    executor = WorkflowExecutor(context, WorkflowArtifacts(tmp_path, "run"), {}, events.append)
    step = node("input_text", selector="#field", timeoutSeconds=0.06)
    started = time.monotonic()
    result = await executor.run({"nodes": [step]}, [step["id"]])
    assert result["error"]["code"] == "workflow_node_timeout"
    assert time.monotonic() - started < 0.15
    assert events[-1]["type"] == "node_failed"
    assert not any(call[0] == "fill" for call in context.pages[0].calls)


@pytest.mark.asyncio
async def test_popup_registered_before_click_and_no_popup_is_not_failure(tmp_path):
    context = Context()
    executor = WorkflowExecutor(context, WorkflowArtifacts(tmp_path, "run"), {}, lambda _: None)
    executor.page = await context.new_page()
    original = executor.page
    popup = original.popup = Page()
    executor.deadline = asyncio.get_running_loop().time() + 0.1
    await executor._execute("click_element", "click", node("click_element", selector="button", followNewTab=True)["config"])
    assert executor.page is popup
    assert original.listeners["popup"] == []
    executor.deadline = asyncio.get_running_loop().time() + 0.04
    await executor._execute("click_element", "click", node("click_element", selector="button", followNewTab=True)["config"])
    assert executor.page is popup
    popup.closed = True
    # Even an unrelated surviving tab is never selected after the owned page closes.
    step = node("wait_element", selector="body")
    with pytest.raises(Exception, match="当前网页已关闭"):
        await executor._execute(step["type"], step["id"], step["config"])


@pytest.mark.asyncio
async def test_large_result_only_crosses_protocol_as_registered_short_preview(tmp_path):
    context = Context()
    events = []
    executor = WorkflowExecutor(context, WorkflowArtifacts(tmp_path, "run"), {}, events.append)
    executor.page = await context.new_page()
    executor.page.value = "汉" * 100_000
    executor.deadline = asyncio.get_running_loop().time() + 1
    artifact = await executor._execute("get_element_info", "extract", node("get_element_info", selector="body")["config"])
    assert len(json.dumps(artifact).encode()) < 2048
    assert len(artifact_path(tmp_path, "run", artifact["relativePath"]).read_bytes()) > 64 * 1024
    assert executor.variables["element_value"] == "汉" * 100_000


def test_artifact_paths_custom_copy_no_overwrite_and_symlink_rejection(tmp_path):
    store = WorkflowArtifacts(tmp_path / "runs", "run")
    custom = tmp_path / "custom" / "image.PNG"
    result = store.save_png("image", b"png", str(custom))
    assert custom.read_bytes() == b"png"
    assert artifact_path(tmp_path / "runs", "run", result["relativePath"]).read_bytes() == b"png"
    with pytest.raises(FileExistsError):
        store.save_png("image", b"new", str(custom))
    assert custom.read_bytes() == b"png"
    for unsafe in ("../outside.png", "../../outside"):
        with pytest.raises(ValueError):
            store.save_png("image", b"new", unsafe)
    (store.root / "link.png").symlink_to(custom)
    with pytest.raises(ValueError):
        artifact_path(tmp_path / "runs", "run", "link.png")
    with pytest.raises(ValueError):
        artifact_path(tmp_path / "runs", "run", "../custom/image.PNG")
    (store.root / "escape").symlink_to(tmp_path / "custom", target_is_directory=True)
    with pytest.raises(ValueError):
        store.save_png("image", b"new", "escape/output.png")


@pytest.mark.asyncio
async def test_workflow_worker_respects_headless_and_never_opens_profile_start_url(monkeypatch, tmp_path):
    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))
    context, captured, output = Context(), {}, io.StringIO()

    async def launch(**kwargs):
        captured.update(kwargs)
        return context

    monkeypatch.setitem(sys.modules, "cloakbrowser", SimpleNamespace(launch_context_async=launch))
    step = node("wait_element", selector="body")
    command = {
        "headless": True, "fingerprintSeed": 12345, "expertArgs": ["--headless=false", "--lang=zh"],
        "geoip": False, "humanize": False, "humanPreset": "default", "extensionPaths": [],
        "browserVersion": "146.0.1", "releaseChannel": "stable", "startUrl": "https://never.example",
        "runId": "run", "runsRoot": str(tmp_path / "runs"), "variables": {},
        "document": {"nodes": [step]}, "nodeIds": [step["id"]],
    }
    assert await _run(command, Event(), output) == 0
    assert captured["headless"] is True
    assert captured["args"] == ["--lang=zh", "--fingerprint=12345"]
    assert not any(call[0] == "goto" for page in context.pages for call in page.calls)
    assert context.closed
    assert not cache.exists()
    assert json.loads(output.getvalue().splitlines()[-1])["state"] == "succeeded"


@pytest.mark.asyncio
@pytest.mark.parametrize("when", ["starting", "running", "immediate"])
async def test_manager_stop_waits_for_cleanup_and_is_idempotent(tmp_path, valid_profile_values, when):
    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    events = []
    ready = asyncio.Event()
    script = (
        "import json,sys,time; json.loads(sys.stdin.readline()); "
        + ("time.sleep(60); " if when == "starting" else "")
        + "print(json.dumps({'type':'ready'}),flush=True); sys.stdin.read(); time.sleep(.1)"
    )
    manager = WorkflowWorkerManager(tmp_path / "temp", tmp_path / "runs", command=(sys.executable, "-c", script), termination_timeout=0.05)

    async def on_event(event):
        events.append(event)
        ready.set()

    execution = asyncio.create_task(manager.execute("run", prepared(), profile(valid_profile_values), executable, None, None, on_event))
    if when == "running":
        await asyncio.wait_for(ready.wait(), 2)
    elif when == "starting":
        await asyncio.sleep(0.1)
    else:
        await asyncio.sleep(0)
    assert manager.busy()
    await asyncio.gather(manager.stop("run"), manager.stop("run"))
    assert await execution == {"state": "cancelled", "error": None}
    assert not manager.busy()
    assert not list((tmp_path / "temp").rglob("run"))
    await manager.stop("missing")
    await manager.shutdown()


@pytest.mark.asyncio
async def test_manager_callback_does_not_observe_finished_and_completion_waits_for_cleanup(tmp_path, valid_profile_values):
    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    script = "import json,sys; sys.stdin.readline(); print(json.dumps({'type':'finished','state':'succeeded','error':None}),flush=True); sys.stdin.read()"
    manager = WorkflowWorkerManager(tmp_path / "temp", tmp_path / "runs", command=(sys.executable, "-c", script))
    events = []

    async def on_event(event):
        events.append(event)

    result = await manager.execute("run", prepared(), profile(valid_profile_values), executable, None, None, on_event)
    assert result == {"state": "succeeded", "error": None}
    assert events == []
    assert not manager.busy()
    assert not list((tmp_path / "temp").rglob("run"))
    await manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process-group regression")
@pytest.mark.parametrize("detached", [False, True])
async def test_manager_reaps_descendant_after_successful_worker_exit(tmp_path, valid_profile_values, detached):
    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    pid_file = tmp_path / "child.pid"
    child = "import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); open(os.environ['CHILD_PID'],'w').write(str(os.getpid())); time.sleep(60)"
    script = (
        "import json,os,subprocess,sys,time; sys.stdin.readline(); "
        f"subprocess.Popen([sys.executable,'-c',{child!r},'--user-data-dir='+os.environ['TMPDIR']+'/browser'],start_new_session={detached!r},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "time.sleep(.15); print(json.dumps({'type':'finished','state':'succeeded','error':None}),flush=True)"
    )
    manager = WorkflowWorkerManager(tmp_path / "temp", tmp_path / "runs", command=(sys.executable, "-c", script), worker_env={"CHILD_PID": str(pid_file)}, termination_timeout=0.05)

    async def on_event(_):
        pass

    assert (await manager.execute("run", prepared(), profile(valid_profile_values), executable, None, None, on_event))["state"] == "succeeded"
    pid = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.01)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert not manager.busy()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_new_tab_is_lazy_and_explicit_open_can_recover_closed_page(tmp_path):
    context = Context()
    executor = WorkflowExecutor(context, WorkflowArtifacts(tmp_path, "run"), {}, lambda _: None)
    step = node("open_page", url="http://localhost/first")
    assert (await executor.run({"nodes": [step]}, [step["id"]]))["state"] == "succeeded"
    assert len(context.pages) == 1
    context.pages[0].closed = True
    executor.deadline = asyncio.get_running_loop().time() + 1
    await executor._execute("open_page", "open", step["config"])
    assert len(context.pages) == 2
    assert executor.page is context.pages[1]
    context.pages[1].closed = True
    with pytest.raises(Exception, match="当前网页已关闭"):
        await executor._execute("open_page", "open", {**step["config"], "openMode": "current_tab"})


@pytest.mark.asyncio
async def test_disk_write_counts_toward_total_node_budget(tmp_path, monkeypatch):
    store = WorkflowArtifacts(tmp_path, "run")
    save = store.save_png

    def slow_write(*args):
        time.sleep(0.04)
        return save(*args)

    monkeypatch.setattr(store, "save_png", slow_write)
    variables, events = {}, []
    executor = WorkflowExecutor(Context(), store, variables, events.append)
    step = node("screenshot", timeoutSeconds=0.02)
    result = await executor.run({"nodes": [step]}, [step["id"]])
    assert result["error"]["code"] == "workflow_node_timeout"
    assert variables == {}
    assert events[-1]["type"] == "node_failed"


@pytest.mark.asyncio
async def test_cancelled_caller_and_repeated_stop_cannot_interrupt_cleanup(tmp_path, monkeypatch, valid_profile_values):
    import autoflow.infrastructure.process.workflow_worker as module

    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    script = "import sys,time; sys.stdin.readline(); print('{\"type\":\"ready\"}',flush=True); time.sleep(60)"
    manager = WorkflowWorkerManager(tmp_path / "temp", tmp_path / "runs", command=(sys.executable, "-c", script), termination_timeout=0.02)
    ready, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    real_cleanup = module.stop_process_tree

    async def cleanup(process, timeout, directory=None, executable=None, birth=None):
        cleaning.set()
        await release.wait()
        await real_cleanup(process, timeout, directory, executable, birth)

    monkeypatch.setattr(module, "stop_process_tree", cleanup)

    async def on_event(_):
        ready.set()

    execution = asyncio.create_task(manager.execute("run", prepared(), profile(valid_profile_values), executable, None, None, on_event))
    await asyncio.wait_for(ready.wait(), 2)
    execution.cancel()
    await asyncio.wait_for(cleaning.wait(), 2)
    stopping = asyncio.create_task(manager.stop("run"))
    await asyncio.sleep(0)
    execution.cancel()
    stopping.cancel()
    await asyncio.sleep(0)
    assert manager.busy()
    assert not execution.done()
    assert not stopping.done()
    release.set()
    assert await execution == {"state": "cancelled", "error": None}
    await stopping
    assert not manager.busy()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_start_timeout_returns_safe_failure_after_cleanup(tmp_path, valid_profile_values):
    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    manager = WorkflowWorkerManager(
        tmp_path / "temp", tmp_path / "runs", command=(sys.executable, "-c", "import time; time.sleep(60)"),
        start_timeout=0.03, termination_timeout=0.02,
    )

    async def on_event(_):
        raise AssertionError("No worker events expected")

    result = await manager.execute("run", prepared(), profile(valid_profile_values), executable, None, "never-log-license", on_event)
    assert result["error"]["code"] == "workflow_worker_timeout"
    assert "never-log-license" not in json.dumps(result)
    assert not manager.busy()
    assert not list((tmp_path / "temp").rglob("run"))
    await manager.shutdown()


def test_process_identity_does_not_reclaim_reused_worker_pid_or_diagnostic_command(monkeypatch, tmp_path):
    from autoflow.infrastructure.process import browser_processes as module

    run = tmp_path / "run"
    executable = tmp_path / "Chromium"
    rows = (
        "500 1 500 /bin/zsh\n"
        "700 500 500 unrelated-job\n"
        f"800 500 500 /usr/bin/grep --user-data-dir={run}/profile\n"
        f"900 1 900 {executable} --user-data-dir={run}/profile\n"
    )
    monkeypatch.setattr(module.subprocess, "check_output", lambda *_args, **_kwargs: rows)
    monkeypatch.setattr(module, "process_birth", lambda pid: {500: 1, 700: 22, 800: 3, 900: 4}.get(pid))
    monkeypatch.setattr(module, "_native_arguments", lambda pid: (
        (Path("/usr/bin/grep"), ["grep", f"--user-data-dir={run}/profile"], {})
        if pid == 800 else
        (executable, [str(executable), f"--user-data-dir={run}/profile"], {"CLOAKBROWSER_CACHE_DIR": str(run)})
    ))
    assert module.capture_processes(700, 11, run, executable) == {900: (900, 4)}
    assert module.capture_processes(700, 11, None, None, {700: (500, 11)}) == {}
    sent = []
    monkeypatch.setattr(module.os, "killpg", lambda *args: sent.append(args))
    module.signal_processes({700: (500, 11)}, 9)
    assert sent == []


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process metadata regression")
async def test_test_browser_shutdown_cannot_cancel_start_cleanup_twice(monkeypatch, tmp_path, valid_profile_values):
    import autoflow.infrastructure.process.test_browser_worker as module

    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    manager = module.TestBrowserWorkerManager(
        tmp_path / "temp", command=(sys.executable, "-c", "import sys; sys.stdin.readline(); sys.stdin.read()"),
        termination_timeout=0.03,
    )
    opening = asyncio.create_task(manager.start("run", profile(valid_profile_values), executable, None, None))
    deadline = time.monotonic() + 2
    while not manager.active_processes() and time.monotonic() < deadline:
        await asyncio.sleep(0.01)
    pid = manager.active_processes()[0]
    entered, release = Event(), Event()
    real_capture = module.capture_processes

    def blocked_capture(*args):
        entered.set()
        release.wait(3)
        return real_capture(*args)

    monkeypatch.setattr(module, "capture_processes", blocked_capture)
    stopping = asyncio.create_task(manager.stop("profile-1"))
    assert await asyncio.to_thread(entered.wait, 2)
    shutdown = asyncio.create_task(manager.shutdown())
    await asyncio.sleep(0.02)
    assert not shutdown.done()
    release.set()
    await shutdown
    await stopping
    with pytest.raises(asyncio.CancelledError):
        await opening
    assert not manager.busy()
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.asyncio
async def test_cleanup_failure_keeps_ownership_until_stop_retry_finishes(monkeypatch, tmp_path, valid_profile_values):
    import autoflow.infrastructure.process.workflow_worker as module

    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    script = "import sys; sys.stdin.readline(); print('{\"type\":\"finished\",\"state\":\"succeeded\",\"error\":null}',flush=True); sys.stdin.read()"
    manager = WorkflowWorkerManager(tmp_path / "temp", tmp_path / "runs", command=(sys.executable, "-c", script), termination_timeout=0.03)
    real_cleanup = module.stop_process_tree
    attempts, owned = [], []

    async def cleanup(process, *args):
        attempts.append(True)
        owned.append(process.pid)
        if len(attempts) == 1:
            raise RuntimeError("temporary metadata failure")
        await real_cleanup(process, *args)

    monkeypatch.setattr(module, "stop_process_tree", cleanup)

    async def on_event(_):
        pass

    with pytest.raises(WorkflowError) as failure:
        await manager.execute("run", prepared(), profile(valid_profile_values), executable, None, None, on_event)
    assert failure.value.code == "WORKFLOW_CLEANUP_FAILED"
    assert manager.busy()
    os.kill(owned[0], 0)
    await manager.stop("run")
    assert len(attempts) == 2
    assert not manager.busy()
    with pytest.raises(ProcessLookupError):
        os.kill(owned[0], 0)
    await manager.shutdown()


def test_unreadable_metadata_never_confirms_a_live_owned_process_exited(monkeypatch):
    from autoflow.infrastructure.process import browser_processes as module

    monkeypatch.setattr(module, "process_birth", lambda _: None)
    monkeypatch.setattr(module, "_process_exists", lambda pid: pid == 700)
    owned = {700: (700, 123), 701: (700, 456)}
    assert module.living_processes(owned) == {700: (700, 123)}
    sent = []
    monkeypatch.setattr(module.os, "killpg", lambda *args: sent.append(args))
    module.signal_processes(owned, 9)
    assert sent == []


def test_second_identity_read_failure_preserves_a_live_owned_process(monkeypatch):
    from autoflow.infrastructure.process import browser_processes as module

    values = iter([123, None])
    monkeypatch.setattr(module, "process_birth", lambda _: next(values))
    monkeypatch.setattr(module, "_process_exists", lambda _: True)
    monkeypatch.setattr(module.subprocess, "check_output", lambda *_args, **_kwargs: "700 1 700 worker\n")
    assert module.capture_processes(700, 123, None, None) == {700: (700, 123)}


@pytest.mark.asyncio
async def test_test_browser_failed_start_cleanup_can_be_stopped_again(monkeypatch, tmp_path, valid_profile_values):
    import autoflow.infrastructure.process.test_browser_worker as module

    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    manager = module.TestBrowserWorkerManager(tmp_path / "temp", command=(sys.executable, "-c", "import sys; sys.stdin.readline(); sys.stdin.read()"), termination_timeout=0.03)
    opening = asyncio.create_task(manager.start("run", profile(valid_profile_values), executable, None, None))
    deadline = time.monotonic() + 2
    while not manager.active_processes() and time.monotonic() < deadline:
        await asyncio.sleep(0.01)
    pid = manager.active_processes()[0]
    cleanup = module.stop_process_tree

    async def fail(*args):
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(module, "stop_process_tree", fail)
    with pytest.raises(module.ProfileTestBrowserUnavailable):
        await manager.stop("profile-1")
    with pytest.raises(RuntimeError, match="metadata unavailable"):
        await opening
    assert manager.busy()
    os.kill(pid, 0)
    monkeypatch.setattr(module, "stop_process_tree", cleanup)
    await manager.stop("profile-1")
    assert not manager.busy()
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_test_browser_failed_monitor_cleanup_retains_session_for_retry(monkeypatch, tmp_path, valid_profile_values):
    import autoflow.infrastructure.process.test_browser_worker as module

    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    script = "import json,sys,time; p=json.loads(sys.stdin.readline()); print(json.dumps({'type':'ready','sessionId':p['sessionId'],'profileId':p['profileId'],'fingerprintSeed':p['fingerprintSeed']}),flush=True); time.sleep(.1)"
    manager = module.TestBrowserWorkerManager(tmp_path / "temp", command=(sys.executable, "-c", script), termination_timeout=0.03)
    cleanup = module.force_process_tree
    failed = asyncio.Event()

    async def fail(*args):
        failed.set()
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(module, "force_process_tree", fail)
    await manager.start("run", profile(valid_profile_values), executable, None, None)
    await asyncio.wait_for(failed.wait(), 2)
    await asyncio.sleep(0)
    assert manager.busy()
    assert manager.statuses()[0].state == "stopping"
    monkeypatch.setattr(module, "force_process_tree", cleanup)
    await manager.stop("profile-1")
    assert not manager.busy()
    await manager.shutdown()


def test_inspection_worker_can_be_identified_after_initial_birth_probe_was_unavailable(monkeypatch, tmp_path):
    from autoflow.infrastructure.process import browser_processes as module

    run, executable = tmp_path / 'run', tmp_path / 'Chromium'
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *_args, **_kwargs: '700 1 700 autoflow-backend --inspection-worker\n')
    monkeypatch.setattr(module, 'process_birth', lambda _: 123)
    monkeypatch.setattr(module, '_native_arguments', lambda _: (
        Path(sys.executable), ['autoflow-backend', '--inspection-worker'], {'CLOAKBROWSER_CACHE_DIR': str(run)},
    ))
    assert module.capture_processes(700, None, run, executable) == {700: (700, 123)}
    monkeypatch.setattr(module, '_native_arguments', lambda _: (
        Path(sys.executable), ['autoflow-backend', '--inspection-worker'], {'CLOAKBROWSER_CACHE_DIR': str(tmp_path / 'other')},
    ))
    assert module.capture_processes(700, None, run, executable) == {}


@pytest.mark.asyncio
async def test_unverified_worker_exit_has_bounded_cleanup_failure(monkeypatch):
    from autoflow.infrastructure.process import test_browser_worker as module

    exited = asyncio.Event()
    process = SimpleNamespace(pid=700, returncode=None, wait=exited.wait)
    monkeypatch.setattr(module, 'capture_processes', lambda *_args: {})
    monkeypatch.setattr(module, 'signal_processes', lambda *_args: None)
    try:
        async with asyncio.timeout(1):
            with pytest.raises(RuntimeError, match='identity or process exit'):
                await module.force_process_tree(process, 0.01)
    finally:
        exited.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("inspection", [False, True])
@pytest.mark.parametrize("phase", ["drain", "read"])
async def test_worker_transport_does_not_swallow_stop_when_io_completes(tmp_path, inspection, phase):
    from autoflow.infrastructure.process.inspection_worker import (
        InspectionWorkerManager,
    )

    manager = InspectionWorkerManager(tmp_path) if inspection else WorkflowWorkerManager(tmp_path, tmp_path)
    owner = None
    reads = 0

    async def drain():
        if phase == "drain":
            asyncio.get_running_loop().call_soon(owner.cancel)

    async def readline():
        nonlocal reads
        reads += 1
        if phase == "read" and reads == 1:
            asyncio.get_running_loop().call_soon(owner.cancel)
            return json.dumps({"type": "inspection" if inspection else "ready"}).encode() + b"\n"
        await asyncio.Event().wait()

    async def event(_value):
        pass

    process = SimpleNamespace(stdin=SimpleNamespace(write=lambda _: None, drain=drain),
                              stdout=SimpleNamespace(readline=readline))
    owner = asyncio.create_task(manager._exchange(process, {}, prepared(), event))
    try:
        done, _ = await asyncio.wait({owner}, timeout=0.2)
        assert done and owner.cancelled(), "completed I/O swallowed stop and kept reading the worker"
    finally:
        owner.cancel()
        await asyncio.gather(owner, return_exceptions=True)
