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


def profile(values):
    now = datetime.now(UTC)
    return Profile("profile-1", ProfileSpec.from_values(values), 12345, now, now)


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
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


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


def test_pure_data_recovery_requires_native_worker_identity_and_exact_run_marker(monkeypatch, tmp_path):
    from autoflow.infrastructure.process import project_browser_processes as module

    run = (tmp_path / 'run').resolve()
    other = (tmp_path / 'other').resolve()
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *_args, **_kwargs: '\n'.join(
        f'{pid} 1 {pid} --project-workflow-worker {run}' for pid in range(700, 705)
    ))
    monkeypatch.setattr(module, 'process_birth', lambda pid: pid + 10)
    native = {
        700: (Path(sys.executable), ['--project-workflow-worker'], {'CLOAKBROWSER_CACHE_DIR': str(run)}),
        701: (Path(sys.executable), ['--project-workflow-worker'], {'CLOAKBROWSER_CACHE_DIR': str(other)}),
        702: (Path(sys.executable), ['diagnostic', str(run)], {}),
        703: (Path('/usr/bin/grep'), ['--project-workflow-worker'], {'CLOAKBROWSER_CACHE_DIR': str(run)}),
        704: (Path('/opt/playwright/driver/node'), ['/opt/playwright/driver/package/cli.js', 'run-driver'], {'CLOAKBROWSER_CACHE_DIR': str(run)}),
    }
    monkeypatch.setattr(module, '_native_arguments', native.get)
    assert module.capture_processes(0, None, run, None, strict_ownership=True) == {700: (700, 710)}


def test_pure_data_recovery_does_not_assume_unreadable_live_candidate_is_gone(monkeypatch, tmp_path):
    from autoflow.infrastructure.process import project_browser_processes as module

    monkeypatch.setattr(module.subprocess, 'check_output', lambda *_args, **_kwargs: '700 1 700 python --project-workflow-worker\n')
    monkeypatch.setattr(module, 'process_birth', lambda _pid: 710)
    monkeypatch.setattr(module, '_native_arguments', lambda _pid: None)
    monkeypatch.setattr(module, '_process_exists', lambda _pid: True)
    with pytest.raises(RuntimeError, match='ownership is unavailable'):
        module.capture_processes(0, None, tmp_path, None, strict_ownership=True)


@pytest.mark.asyncio
async def test_unverified_worker_exit_has_bounded_cleanup_failure(monkeypatch):
    from autoflow.infrastructure.process import test_browser_worker as module

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
