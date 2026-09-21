import asyncio
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.infrastructure.process.browser_processes import process_identity_is_alive


def profile(values):
    now = datetime.now(UTC)
    return Profile("profile-1", ProfileSpec.from_values(values), 12345, now, now)


def test_process_identity_does_not_reclaim_reused_worker_pid_or_diagnostic_command(monkeypatch, tmp_path):
    from autoflow.infrastructure.process import browser_processes as module

    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="darwin", executable=sys.executable))
    monkeypatch.setattr(module.os, "getpgrp", lambda: 100, raising=False)

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
    monkeypatch.setattr(module.os, "killpg", lambda *args: sent.append(args), raising=False)
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

    def blocked_capture(*args, **kwargs):
        entered.set()
        release.wait(3)
        return real_capture(*args, **kwargs)

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
    assert not process_identity_is_alive(pid, None)


def test_unreadable_metadata_never_confirms_a_live_owned_process_exited(monkeypatch):
    from autoflow.infrastructure.process import browser_processes as module

    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="darwin", executable=sys.executable))
    monkeypatch.setattr(module.os, "getpgrp", lambda: 100, raising=False)

    monkeypatch.setattr(module, "process_birth", lambda _: None)
    monkeypatch.setattr(module, "_process_exists", lambda pid: pid == 700)
    owned = {700: (700, 123), 701: (700, 456)}
    assert module.living_processes(owned) == {700: (700, 123)}
    sent = []
    monkeypatch.setattr(module.os, "killpg", lambda *args: sent.append(args), raising=False)
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
    assert process_identity_is_alive(pid, None)
    monkeypatch.setattr(module, "stop_process_tree", cleanup)
    await manager.stop("profile-1")
    assert not manager.busy()
    assert not process_identity_is_alive(pid, None)
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


def test_browser_worker_can_be_identified_after_initial_birth_probe_was_unavailable(monkeypatch, tmp_path):
    from autoflow.infrastructure.process import browser_processes as module

    run, executable = tmp_path / 'run', tmp_path / 'Chromium'
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *_args, **_kwargs: '700 1 700 autoflow-backend --test-browser-worker\n')
    monkeypatch.setattr(module, 'process_birth', lambda _: 123)
    monkeypatch.setattr(module, '_native_arguments', lambda _: (
        Path(sys.executable), ['autoflow-backend', '--test-browser-worker'], {'CLOAKBROWSER_CACHE_DIR': str(run)},
    ))
    assert module.capture_processes(700, None, run, executable) == {700: (700, 123)}
    monkeypatch.setattr(module, '_native_arguments', lambda _: (
        Path(sys.executable), ['autoflow-backend', '--test-browser-worker'], {'CLOAKBROWSER_CACHE_DIR': str(tmp_path / 'other')},
    ))
    assert module.capture_processes(700, None, run, executable) == {}


@pytest.mark.asyncio
async def test_unverified_worker_exit_has_bounded_cleanup_failure(monkeypatch):
    from autoflow.infrastructure.process import test_browser_worker as module

    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(module, "signal", SimpleNamespace(SIGTERM=15, SIGKILL=9))

    exited = asyncio.Event()
    process = SimpleNamespace(pid=700, returncode=None, wait=exited.wait)
    monkeypatch.setattr(module, 'capture_processes', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(module, 'signal_processes', lambda *_args: None)
    try:
        async with asyncio.timeout(1):
            with pytest.raises(RuntimeError, match='identity or process exit'):
                await module.force_process_tree(process, 0.01)
    finally:
        exited.set()


@pytest.mark.parametrize('module_name', ['browser_processes', 'project_browser_processes'])
def test_framework_python_worker_uses_native_interpreter_identity(monkeypatch, tmp_path, module_name):
    from importlib import import_module

    module = import_module(f'autoflow.infrastructure.process.{module_name}')
    native_python = Path('/Library/Frameworks/Python.framework/Resources/Python.app/Contents/MacOS/Python')
    run = tmp_path / 'run'
    marker = {'CLOAKBROWSER_CACHE_DIR': str(run)}
    monkeypatch.setattr(module, '_native_arguments', lambda pid: (
        native_python if pid in (700, os.getpid()) else Path('/unrelated/python'),
        ['python', '--workflow-worker'], marker,
    ))
    assert module._belongs_to_run(700, run, tmp_path / 'Chromium') is True
    assert module._belongs_to_run(701, run, tmp_path / 'Chromium') is False


def test_windows_unknown_birth_probe_never_sends_a_signal(monkeypatch):
    from autoflow.infrastructure.process import browser_processes as module

    monkeypatch.setattr(module, 'sys', SimpleNamespace(platform='win32'))
    monkeypatch.setattr(module, 'process_birth', lambda _: None)
    monkeypatch.setattr(module, '_windows_process_exists', lambda _: True, raising=False)

    def forbidden(*_args):
        raise AssertionError('a liveness probe must never send a Windows signal')

    monkeypatch.setattr(module.os, 'kill', forbidden)
    assert module.process_identity_is_alive(700, None)


@pytest.mark.asyncio
async def test_native_liveness_probe_preserves_a_live_process_and_detects_exit():
    from autoflow.infrastructure.process.browser_processes import (
        process_birth,
        process_identity_is_alive,
    )

    process = await asyncio.create_subprocess_exec(sys.executable, '-c', 'import time; time.sleep(30)')
    birth = process_birth(process.pid)
    try:
        assert process_identity_is_alive(process.pid, None)
        assert process_identity_is_alive(process.pid, birth)
        await asyncio.sleep(.05)
        assert process.returncode is None
    finally:
        if process.returncode is None:
            process.terminate()
        await process.wait()
    assert not process_identity_is_alive(process.pid, birth)


@pytest.mark.parametrize('handle,wait,error,expected', [
    (700, 258, 0, True), (700, 0, 0, False), (700, 0xFFFFFFFF, 0, True),
    (0, 0, 87, False), (0, 0, 5, True),
])
def test_windows_handle_probe_requires_positive_exit_evidence(monkeypatch, handle, wait, error, expected):
    from autoflow.infrastructure.process import browser_processes as module

    calls = []
    closed = []

    def open_process(*args):
        calls.append(args)
        return handle

    kernel = SimpleNamespace(OpenProcess=open_process, WaitForSingleObject=lambda *_: wait, CloseHandle=lambda h: closed.append(h))
    monkeypatch.setattr(module.ctypes, 'WinDLL', lambda *_args, **_kwargs: kernel, raising=False)
    monkeypatch.setattr(module.ctypes, 'get_last_error', lambda: error, raising=False)
    assert module._windows_process_exists(700) is expected
    assert calls == [(0x00100000, False, 700)]
    assert closed == ([handle] if handle else [])


@pytest.mark.asyncio
@pytest.mark.parametrize('module_name', ['test_browser_worker', 'project_test_browser_worker', 'kernel_worker'])
@pytest.mark.parametrize('still_alive', [False, True])
async def test_exit_race_never_releases_a_process_without_confirming_exit(monkeypatch, module_name, still_alive):
    from importlib import import_module

    module = import_module(f'autoflow.infrastructure.process.{module_name}')
    if module_name != 'kernel_worker':
        monkeypatch.setattr(module, 'sys', SimpleNamespace(platform='win32'))

    def denied():
        raise PermissionError('process may have exited before its watcher updated')

    async def wait():
        if still_alive:
            await asyncio.Event().wait()
        process.returncode = 0
        return 0

    process = SimpleNamespace(pid=700, returncode=None, kill=denied, terminate=denied, wait=wait)

    async def killer_wait():
        return 0

    async def spawn(*_args, **_kwargs):
        return SimpleNamespace(wait=killer_wait)

    monkeypatch.setattr(module.asyncio, 'create_subprocess_exec', spawn)
    if module_name == 'kernel_worker':
        manager = object.__new__(module.KernelWorkerManager)
        manager._termination_timeout = .01
        cleanup = manager._stop_process(process)
    else:
        cleanup = module.force_process_tree(process, .01)
    if still_alive:
        with pytest.raises(TimeoutError):
            await cleanup
        assert process.returncode is None
    else:
        await cleanup
        assert process.returncode == 0


@pytest.mark.parametrize('birth,member,owned,allowed', [(123, True, False, True), (123, False, False, False), (123, False, True, True), (456, True, True, False), (None, True, True, False)])
def test_windows_job_verifies_same_process_handle_and_only_live_owner_assigns(monkeypatch, birth, member, owned, allowed):
    from autoflow.infrastructure.process import windows_job as module
    calls = []
    def membership(process, job, result):
        calls.append(('member', process, job))
        result._obj.value = member
        return True
    def assign(job, process):
        calls.append(('assign', process, job))
        return True
    kernel = SimpleNamespace(OpenProcess=lambda *_: 9001, IsProcessInJob=membership, AssignProcessToJobObject=assign, CloseHandle=lambda value: calls.append(('close', value)))
    def read(_kernel, process):
        calls.append(('birth', process))
        return birth
    monkeypatch.setattr(module, '_windows_handle_birth', read)
    if allowed:
        assert module._verified_process(kernel, 8001, 700, 123, owned_launcher=owned) == 9001
        kernel.CloseHandle(9001)
    else:
        with pytest.raises(OSError):
            module._verified_process(kernel, 8001, 700, 123, owned_launcher=owned)
    assert calls[0] == ('birth', 9001) and calls[-1] == ('close', 9001)
    assert (('assign', 9001, 8001) in calls) == (birth == 123 and not member and owned)
