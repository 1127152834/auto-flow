"""Opener/closer ownership for headed environment work copies.

The launcher is the only owner of these contexts: ``opener`` must reuse a
context it already holds, and ``closer`` must refuse to report success when the
context cannot be confirmed closed.
"""

import asyncio
import os
import threading
import time
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from autoflow.domain.environments.models import EnvironmentInstance
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore
from autoflow.providers.browser.environment_browser import (
    EnvironmentBrowserLauncher,
    _launch_context,
)

VERSION = "145.0.7632.109.2"


class _Profiles:
    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def get(self, profile_id: str) -> Profile:
        assert profile_id == self.profile.id
        return self.profile


class _Context:
    def __init__(self, loop=None) -> None:
        self.closed = 0
        self.fail = False
        self.loop = loop
        self.fail_by_hanging = False

    async def close(self) -> None:
        self.closed += 1
        if self.fail_by_hanging:
            await asyncio.sleep(3600)
        if self.fail:
            raise RuntimeError("close failed")
        if self.loop is not None:
            # Playwright binds a context to the loop that launched it; closing it
            # from anywhere else deadlocks instead of raising a tidy exception.
            assert asyncio.get_running_loop() is self.loop


def _profile() -> Profile:
    now = datetime(2026, 9, 17, tzinfo=UTC)
    return Profile(
        str(uuid4()),
        ProfileSpec.from_values(
            {
                "name": "主账号",
                "start_url": "about:blank",
                "browser_version": VERSION,
                "browser_edition": "public",
                "release_channel": "stable",
                "human_preset": "default",
            }
        ),
        31415,
        now,
        now,
    )


def _instance(profile: Profile, project_id: str, instance_id: str) -> EnvironmentInstance:
    now = datetime(2026, 9, 17, tzinfo=UTC)
    return EnvironmentInstance(
        instance_id=instance_id,
        project_id=project_id,
        environment_id=None,
        state="active",
        source="newFromProfile",
        source_content_generation=None,
        instance_use_generation=1,
        active_task_id=None,
        active_run_id=None,
        maintenance_operation_id=None,
        profile_id=profile.id,
        created_at=now,
        updated_at=now,
        identity_package={"schemaVersion": 1, "profileId": profile.id, "kernelId": f"public:{VERSION}", "frozenConfiguration": {"profileSpec": asdict(profile.spec), "fingerprintSeed": profile.fingerprint_seed, "createdAt": now.isoformat(), "updatedAt": now.isoformat()}},
    )


def _launcher(tmp_path, profile: Profile):
    store = EnvironmentStore(tmp_path / "environments")
    calls: list[tuple[Path, dict]] = []
    contexts: list[_Context] = []

    async def launch(directory: Path, command: dict):
        calls.append((directory, command))
        context = _Context(asyncio.get_running_loop())
        contexts.append(context)
        return context

    kernel = InstalledKernel("public", VERSION, Path("/kernels/chromium/Chromium"), 1)
    launcher = EnvironmentBrowserLauncher(
        _Profiles(profile), lambda: [kernel], store, launcher=launch
    )
    return launcher, store, calls, contexts


def test_opener_launches_headed_on_the_instance_directory(tmp_path):
    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, calls, _contexts = _launcher(tmp_path, profile)
    store.prepare_instance(instance.instance_id)

    launcher.opener(None, instance)
    launcher.opener(None, instance)

    assert len(calls) == 1
    directory, command = calls[0]
    assert directory == store.root / "instances" / instance.instance_id
    assert command["headless"] is False
    assert command["fingerprintSeed"] == 31415
    assert command["executablePath"] == str(Path("/kernels/chromium/Chromium"))


def test_closer_confirms_close_and_retries_when_it_fails(tmp_path):
    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, _calls, contexts = _launcher(tmp_path, profile)
    store.prepare_instance(instance.instance_id)
    launcher.opener(None, instance)

    contexts[0].fail = True
    with pytest.raises(ProjectError) as failed:
        launcher.closer(None, instance)
    assert failed.value.code == "INSTANCE_NOT_QUIESCENT"

    contexts[0].fail = False
    launcher.closer(None, instance)
    assert contexts[0].closed == 2
    launcher.closer(None, instance)
    assert contexts[0].closed == 2


def test_opener_rejects_a_missing_work_copy(tmp_path):
    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, _store, calls, _contexts = _launcher(tmp_path, profile)

    with pytest.raises(ProjectError) as missing:
        launcher.opener(None, instance)
    assert missing.value.code == "ENVIRONMENT_UNAVAILABLE"
    assert calls == []


def test_closer_refuses_while_another_process_holds_the_work_copy(tmp_path, monkeypatch):
    """A task-owned browser is not ours to close, so we cannot claim it is gone."""

    monkeypatch.setattr(
        "autoflow.providers.browser.environment_browser._COPY_RELEASE_SECONDS", 0.5
    )
    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, _calls, contexts = _launcher(tmp_path, profile)
    directory = store.prepare_instance(instance.instance_id)
    (directory / "SingletonLock").write_text("held", encoding="utf-8")

    with pytest.raises(ProjectError) as busy:
        launcher.closer(None, instance)
    assert busy.value.code == "INSTANCE_NOT_QUIESCENT"
    assert contexts == []


def test_closer_waits_for_a_task_browser_to_release_the_copy(tmp_path, monkeypatch):
    """A stop closes the task browser a moment later than the End that follows it."""

    monkeypatch.setattr(
        "autoflow.providers.browser.environment_browser._COPY_RELEASE_SECONDS", 10
    )
    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, _calls, _contexts = _launcher(tmp_path, profile)
    directory = store.prepare_instance(instance.instance_id)
    lock = directory / "SingletonLock"
    lock.write_text("held", encoding="utf-8")

    releaser = threading.Timer(0.4, lock.unlink)
    releaser.daemon = True
    releaser.start()
    try:
        launcher.closer(None, instance)
    finally:
        releaser.cancel()


def test_opener_reports_the_task_browser_holding_the_copy(tmp_path):
    """Do not attempt a launch Chromium must refuse with an opaque error."""

    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, calls, _contexts = _launcher(tmp_path, profile)
    directory = store.prepare_instance(instance.instance_id)
    (directory / "SingletonLock").write_text("held", encoding="utf-8")

    with pytest.raises(ProjectError) as busy:
        launcher.opener(None, instance)
    assert busy.value.code == "INSTANCE_NOT_QUIESCENT"
    assert "浏览器" in busy.value.message
    assert calls == []


def test_closer_reports_success_for_a_copy_nobody_holds(tmp_path):
    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, _calls, _contexts = _launcher(tmp_path, profile)
    store.prepare_instance(instance.instance_id)

    launcher.closer(None, instance)


def test_close_runs_on_the_loop_that_launched_the_browser(tmp_path):
    """A fresh loop per call hangs the real browser; the launcher owns one loop."""

    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, _calls, contexts = _launcher(tmp_path, profile)
    store.prepare_instance(instance.instance_id)

    launcher.opener(None, instance)
    launcher.closer(None, instance)

    assert contexts[0].closed == 1
    assert contexts[0].loop is not None


def test_close_that_hangs_is_reported_instead_of_blocking(tmp_path, monkeypatch):
    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, _calls, contexts = _launcher(tmp_path, profile)
    store.prepare_instance(instance.instance_id)
    launcher.opener(None, instance)
    monkeypatch.setattr(
        "autoflow.providers.browser.environment_browser._CLOSE_TIMEOUT_SECONDS", 0.25
    )
    contexts[0].fail_by_hanging = True

    with pytest.raises(ProjectError) as stuck:
        launcher.closer(None, instance)
    assert stuck.value.code == "INSTANCE_NOT_QUIESCENT"

    contexts[0].fail_by_hanging = False
    launcher.closer(None, instance)
    assert contexts[0].closed == 2


def test_shutdown_closes_owned_browsers_and_stops_the_owner_loop(tmp_path):
    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, _calls, contexts = _launcher(tmp_path, profile)
    store.prepare_instance(instance.instance_id)
    launcher.opener(None, instance)

    launcher.shutdown()

    assert contexts[0].closed == 1
    assert launcher.owner_loop_running() is False


def test_closer_waits_for_a_window_that_is_still_starting(tmp_path):
    """End during an in-flight start must close and keep the login.

    Refusing here is what turned "结束并保留" into a failed end operation with a
    live kernel left behind: the user had no way to finish the task.
    """

    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    store = EnvironmentStore(tmp_path / "environments")
    store.prepare_instance(instance.instance_id)
    gate = threading.Event()
    started = threading.Event()
    launched: list[_Context] = []

    async def launch(_directory: Path, _command: dict):
        started.set()
        while not gate.is_set():
            await asyncio.sleep(0.01)
        context = _Context(asyncio.get_running_loop())
        launched.append(context)
        return context

    kernel = InstalledKernel("public", VERSION, Path("/kernels/chromium/Chromium"), 1)
    launcher = EnvironmentBrowserLauncher(
        _Profiles(profile), lambda: [kernel], store, launcher=launch
    )
    opener = threading.Thread(target=lambda: launcher.opener(None, instance), daemon=True)
    opener.start()
    assert started.wait(10)
    failures: list[BaseException] = []
    finished = threading.Event()

    def close() -> None:
        try:
            launcher.closer(None, instance)
        except BaseException as error:  # noqa: BLE001 -- reported through the list
            failures.append(error)
        finally:
            finished.set()

    closer = threading.Thread(target=close, daemon=True)
    closer.start()
    try:
        time.sleep(0.3)
        assert not finished.is_set(), "closer must wait for the start instead of failing"
    finally:
        gate.set()
    opener.join(10)
    closer.join(10)

    assert failures == []
    assert [context.closed for context in launched] == [1]


def test_launch_pins_the_declared_kernel_for_cloakbrowser(tmp_path, monkeypatch):
    """A profile that names an installed kernel must launch that executable.

    CloakBrowser resolves the binary itself and a free-plan license key silently
    upgrades to the latest Pro build, so the declared kernel was ignored until
    the launch pinned it through the same override the workers already receive.
    """

    import cloakbrowser

    seen: list[str | None] = []

    async def fake_launch_persistent_context(user_data_dir, **kwargs):
        seen.append(os.environ.get("CLOAKBROWSER_BINARY_PATH"))
        assert str(user_data_dir) == str((tmp_path / "work").resolve())
        assert kwargs["headless"] is False
        return _Context()

    monkeypatch.setattr(
        cloakbrowser, "launch_persistent_context_async", fake_launch_persistent_context
    )
    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    profile = _profile()
    launcher, _store, _calls, _contexts = _launcher(tmp_path, profile)
    command = launcher._launch_command(profile, Path("/kernels/chromium/Chromium"))

    asyncio.run(_launch_context(tmp_path / "work", command))

    assert seen == [str(Path("/kernels/chromium/Chromium"))]
    assert "CLOAKBROWSER_BINARY_PATH" not in os.environ


def test_pinned_kernel_restores_the_previous_override(tmp_path, monkeypatch):
    import cloakbrowser

    seen: list[str | None] = []

    async def fake_launch_persistent_context(user_data_dir, **_kwargs):
        del user_data_dir
        seen.append(os.environ.get("CLOAKBROWSER_BINARY_PATH"))
        return _Context()

    monkeypatch.setattr(
        cloakbrowser, "launch_persistent_context_async", fake_launch_persistent_context
    )
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", "/kernels/outer/Chromium")
    profile = _profile()
    launcher, _store, _calls, _contexts = _launcher(tmp_path, profile)
    command = launcher._launch_command(profile, Path("/kernels/chromium/Chromium"))

    asyncio.run(_launch_context(tmp_path / "work", command))

    assert seen == [str(Path("/kernels/chromium/Chromium"))]
    assert os.environ["CLOAKBROWSER_BINARY_PATH"] == "/kernels/outer/Chromium"


def test_maintenance_uses_saved_identity_after_template_edit(tmp_path):
    profile = _profile()
    instance = _instance(profile, str(uuid4()), str(uuid4()))
    launcher, store, calls, _contexts = _launcher(tmp_path, replace(profile, fingerprint_seed=999))
    store.prepare_instance(instance.instance_id)
    try:
        launcher.opener(None, instance)
        assert calls[0][1]['fingerprintSeed'] == 31415
    finally:
        launcher.shutdown()


def test_maintenance_without_identity_does_not_guess_template(tmp_path):
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError

    profile = _profile()
    instance = replace(_instance(profile, str(uuid4()), str(uuid4())), identity_package=None)
    launcher, store, calls, _contexts = _launcher(tmp_path, profile)
    store.prepare_instance(instance.instance_id)
    with pytest.raises(WorkflowRuntimeError) as caught:
        launcher.opener(None, instance)
    assert caught.value.code == 'ENVIRONMENT_IDENTITY_UNVERIFIED'
    assert calls == []
