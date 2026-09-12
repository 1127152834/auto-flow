import asyncio
import io
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from autoflow.application.profiles.test_browser import ProfileTestBrowserService
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.errors import ProfileTestBrowserBusy
from autoflow.domain.profiles.models import (
    Profile,
    ProfileSpec,
    ProfileTestBrowserSession,
)
from autoflow.infrastructure.process.test_browser_worker import (
    TestBrowserWorkerManager as BrowserWorkerManager,
)
from autoflow.providers.browser.worker import run_worker


def _profile(values: dict[str, object], *, profile_id: str = "profile-1") -> Profile:
    now = datetime.now(UTC)
    return Profile(profile_id, ProfileSpec.from_values(values), 54321, now, now)


def test_worker_launches_fresh_headed_context_with_saved_seed_and_all_options(
    monkeypatch, tmp_path: Path, valid_profile_values: dict[str, object]
) -> None:
    executable = tmp_path / "Chromium"
    executable.write_bytes(b"kernel")
    cache = tmp_path / "session"
    cache.mkdir()
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(cache))
    captured: dict[str, object] = {}

    class Page:
        async def goto(self, *_args, **_kwargs):
            raise RuntimeError("secret navigation detail")

    class Context:
        def __init__(self) -> None:
            self.pages = [Page()]

        async def new_page(self):
            return self.pages[0]

        async def close(self):
            captured["closed"] = True

    async def launch_context_async(**kwargs):
        captured.update(kwargs)
        return Context()

    monkeypatch.setitem(
        sys.modules,
        "cloakbrowser",
        SimpleNamespace(launch_context_async=launch_context_async),
    )
    command = {
        "sessionId": "session-1",
        "profileId": "profile-1",
        "fingerprintSeed": 54321,
        "startUrl": "https://example.com",
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "geoip": True,
        "humanize": True,
        "humanPreset": "careful",
        "userAgent": "AutoFlow",
        "viewport": {"width": 1280, "height": 720},
        "colorScheme": "dark",
        "extensionPaths": ["/extension"],
        "expertArgs": ["--lang=en-US", "--headless=new"],
        "browserVersion": "146.0.1.1",
        "releaseChannel": "stable",
        "proxy": {
            "server": "http://example.com:8080",
            "username": "user",
            "password": "pass",
        },
        "licenseKey": None,
    }
    output = io.StringIO()
    stopped = Event()
    stopped.set()

    assert run_worker(stopped, io.StringIO(json.dumps(command) + "\n"), output) == 0

    browser_proxy = captured.pop("proxy")
    assert isinstance(browser_proxy, dict)
    assert set(browser_proxy) == {"server"}
    assert browser_proxy["server"].startswith("http://127.0.0.1:")
    assert captured == {
        "headless": False,
        "args": ["--lang=en-US", "--fingerprint=54321"],
        "stealth_args": True,
        "user_agent": "AutoFlow",
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "color_scheme": "dark",
        "geoip": True,
        "humanize": True,
        "human_preset": "careful",
        "extension_paths": ["/extension"],
        "license_key": None,
        "browser_version": "146.0.1.1",
        "release_channel": "stable",
        "viewport": {"width": 1280, "height": 720},
        "closed": True,
    }
    assert json.loads(output.getvalue())["warning"] == "起始网址加载失败，浏览器已保留，可手动重试"



def test_local_relay_endpoint_stays_free_of_upstream_credentials(
    monkeypatch, tmp_path: Path
) -> None:
    from cloakbrowser.browser import _resolve_proxy_config

    executable = tmp_path / "Chromium"
    executable.write_bytes(b"kernel")
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    proxy = {"server": "http://127.0.0.1:54321"}

    proxy_kwargs, proxy_args = _resolve_proxy_config(
        proxy, browser_version="145.0.7632.109.2", release_channel="stable"
    )

    combined = repr((proxy_kwargs, proxy_args))
    assert "review-user" not in combined
    assert "review-pass" not in combined
    assert "http://127.0.0.1:54321" in combined


@pytest.mark.asyncio
async def test_service_rejects_only_overlapping_start_and_allows_new_ready_session(
    tmp_path: Path, valid_profile_values: dict[str, object]
) -> None:
    profile = _profile(valid_profile_values)
    release = asyncio.Event()
    resolver_started = asyncio.Event()
    calls = 0

    class Profiles:
        def get(self, _profile_id: str) -> Profile:
            return profile

    async def resolve_proxy(_profile: Profile, _session_id: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            resolver_started.set()
            await release.wait()

    class Launcher:
        async def start(self, session_id, profile, executable, proxy, license_key):
            return ProfileTestBrowserSession(session_id, profile.id, profile.fingerprint_seed)

    service = ProfileTestBrowserService(
        Profiles(),  # type: ignore[arg-type]
        lambda: [InstalledKernel("public", profile.spec.browser_version, tmp_path / "chrome", 1)],
        resolve_proxy,  # type: ignore[arg-type]
        lambda: None,
        Launcher(),
    )
    first = asyncio.create_task(service.start(profile.id))
    await resolver_started.wait()
    with pytest.raises(ProfileTestBrowserBusy):
        await service.start(profile.id)
    release.set()
    first_result = await first
    second_result = await service.start(profile.id)

    assert first_result.id != second_result.id
    assert calls == 2


@pytest.mark.asyncio
async def test_manager_allows_two_ready_sessions_and_reaps_them(
    tmp_path: Path, valid_profile_values: dict[str, object]
) -> None:
    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    profile = _profile(valid_profile_values)
    script = (
        "import json,sys,time; p=json.loads(sys.stdin.readline()); "
        "print(json.dumps({'type':'ready','sessionId':p['sessionId'],"
        "'profileId':p['profileId'],'fingerprintSeed':p['fingerprintSeed'],"
        "'warning':None}),flush=True); time.sleep(60)"
    )
    manager = BrowserWorkerManager(
        tmp_path / "temp", command=(sys.executable, "-c", script), start_timeout=2
    )
    try:
        first = await manager.start("session-1", profile, executable, None, None)
        second = await manager.start("session-2", profile, executable, None, None)
        assert (first.id, second.id) == ("session-1", "session-2")
        assert len(manager.active_processes()) == 2
    finally:
        await manager.shutdown()
    assert manager.active_processes() == []
    assert not (tmp_path / "temp" / "test-browser").exists()


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process-group regression")
async def test_manager_kills_descendant_after_worker_exits_on_term(
    tmp_path: Path, valid_profile_values: dict[str, object]
) -> None:
    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    profile = _profile(valid_profile_values)
    pid_file = tmp_path / "grandchild.pid"
    child = (
        "import os,signal,time; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "open(os.environ['GRANDCHILD_PID_FILE'],'w').write(str(os.getpid())); "
        "time.sleep(60)"
    )
    worker = (
        "import json,os,signal,subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "p=json.loads(sys.stdin.readline()); "
        "print(json.dumps({'type':'ready','sessionId':p['sessionId'],"
        "'profileId':p['profileId'],'fingerprintSeed':p['fingerprintSeed'],"
        "'warning':None}),flush=True); time.sleep(60)"
    )
    manager = BrowserWorkerManager(
        tmp_path / "temp",
        command=(sys.executable, "-c", worker),
        worker_env={"GRANDCHILD_PID_FILE": str(pid_file)},
        start_timeout=2,
        termination_timeout=0.1,
    )
    await manager.start("session-tree", profile, executable, None, None)
    deadline = time.monotonic() + 2
    while not pid_file.exists() and time.monotonic() < deadline:
        await asyncio.sleep(0.01)
    child_pid = int(pid_file.read_text())

    await manager.shutdown()

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.01)
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process-group regression")
async def test_manager_kills_descendant_after_clean_worker_eof_exit(
    tmp_path: Path, valid_profile_values: dict[str, object]
) -> None:
    executable = tmp_path / "chrome"
    executable.write_bytes(b"kernel")
    profile = _profile(valid_profile_values)
    pid_file = tmp_path / "grandchild-eof.pid"
    child = (
        "import os,signal,time; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "open(os.environ['GRANDCHILD_PID_FILE'],'w').write(str(os.getpid())); "
        "time.sleep(60)"
    )
    worker = (
        "import json,os,subprocess,sys; "
        f"subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "p=json.loads(sys.stdin.readline()); "
        "print(json.dumps({'type':'ready','sessionId':p['sessionId'],"
        "'profileId':p['profileId'],'fingerprintSeed':p['fingerprintSeed'],"
        "'warning':None}),flush=True); sys.stdin.read()"
    )
    manager = BrowserWorkerManager(
        tmp_path / "temp",
        command=(sys.executable, "-c", worker),
        worker_env={"GRANDCHILD_PID_FILE": str(pid_file)},
        start_timeout=2,
        termination_timeout=0.1,
    )
    await manager.start("session-eof-tree", profile, executable, None, None)
    deadline = time.monotonic() + 2
    while not pid_file.exists() and time.monotonic() < deadline:
        await asyncio.sleep(0.01)
    child_pid = int(pid_file.read_text())

    await manager.shutdown()

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.01)
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)
