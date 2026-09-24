"""Headed browser sessions for saved/running environment instances.

"进入当前浏览器" must open the real work copy on the instance directory so a
human can finish login by hand. The launcher below owns those processes: the
same object satisfies ``EnvironmentService``'s ``opener`` and ``closer`` hooks,
so a save or an End can confirm the browser is really gone before copying files.

Cookies, tokens and passwords live only inside the instance directory and are
never logged.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable, Coroutine, Sequence
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any

from autoflow.domain.environments.identity import (
    profile_from_request,
    request_from_identity,
)
from autoflow.domain.environments.rules import environment_error
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.errors import KernelNotInstalled
from autoflow.domain.profiles.models import Profile
from autoflow.providers.browser.persistent_context import persistent_launch_kwargs
from autoflow.providers.browser.proxy_relay import BrowserProxyRelay

_START_TIMEOUT_SECONDS = 110
_CLOSE_TIMEOUT_SECONDS = 60
# A close that arrives while the window is still coming up waits for that start
# instead of failing the whole End. The wait covers the start gate itself, so a
# start that never settles is still reported instead of blocking forever.
_START_SETTLE_SECONDS = _START_TIMEOUT_SECONDS + 5
# A stop closes the task's own browser a moment later than the stop itself, so an
# End that arrives first waits briefly for the work copy instead of failing.
_COPY_RELEASE_SECONDS = 30
_KERNEL_ENV = "CLOAKBROWSER_BINARY_PATH"
_KERNEL_ENV_LOCK = Lock()


class _OwnerLoop:
    """One dedicated event loop shared by every browser this launcher owns.

    Playwright binds a context to the loop that created it. Launching with one
    ``asyncio.run`` and closing with another is not a lesser way to close the
    browser, it is a way to hang forever with the work copy still locked, so
    both directions run on this loop and nothing else.
    """

    def __init__(self, thread_name: str = "environment-browser") -> None:
        self._loop = asyncio.new_event_loop()
        self._ready = Event()
        self._thread = Thread(target=self._serve, name=thread_name, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def _serve(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def run(self, coroutine: Coroutine[Any, Any, Any], *, timeout: float) -> Any:
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            future.cancel()
            raise TimeoutError(f"browser operation exceeded {timeout:g}s") from None

    def stop(self) -> None:
        if not self._thread.is_alive():
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)


class EnvironmentBrowserLauncher:
    """Own the headed persistent contexts opened for environment instances."""

    def __init__(
        self,
        profiles,
        installed_kernels: Callable[[], Sequence[InstalledKernel]],
        store,
        *,
        launcher=None,
        resource_provider=None,
    ) -> None:
        self._resource_provider = resource_provider
        self._leases: dict[str, Any] = {}
        self._relays: dict[str, BrowserProxyRelay] = {}
        self._profiles = profiles
        self._installed_kernels = installed_kernels
        self._store = store
        self._launcher = launcher or _launch_context
        self._contexts: dict[str, Any] = {}
        self._starting: set[str] = set()
        self._settled: dict[str, Event] = {}
        self._lock = Lock()
        self._owner: _OwnerLoop | None = None

    def _owner_loop(self) -> _OwnerLoop:
        """Created on first use so a launcher that never opens costs no thread."""

        with self._lock:
            if self._owner is None:
                self._owner = _OwnerLoop()
            return self._owner

    def opener(self, service, instance) -> None:
        """``opener`` hook: open a headed work copy for the instance."""

        instance_id = instance.instance_id
        with self._lock:
            if instance_id in self._contexts or instance_id in self._starting:
                return
            if self._store.runtime_lock_present(instance_id):
                # Chromium refuses a second ProcessSingleton on a work copy
                # another process owns, and that failure says nothing a user can
                # act on. Report the holder instead of attempting the launch.
                raise environment_error(
                    "INSTANCE_NOT_QUIESCENT",
                    "工作副本正被任务内的浏览器占用，请先停止该任务",
                    409,
                )
            self._starting.add(instance_id)
            settled = Event()
            self._settled[instance_id] = settled
        try:
            directory = self._instance_directory(instance_id)
            owner = self._owner_loop()
            context = owner.run(self._launch_owned(instance, directory), timeout=_START_TIMEOUT_SECONDS)
        except BaseException:
            with self._lock:
                self._starting.discard(instance_id)
                self._settled.pop(instance_id, None)
                settled.set()
            raise
        with self._lock:
            self._starting.discard(instance_id)
            self._settled.pop(instance_id, None)
            self._contexts[instance_id] = context
            settled.set()

    async def _launch_owned(self, instance, directory):
        request = request_from_identity(instance.identity_package)
        profile = profile_from_request(request)
        if profile.id != instance.profile_id:
            raise environment_error("WORKFLOW_RESOURCE_INVALID", "环境身份来源不一致", 422)
        lease = None
        relay = None
        try:
            if self._resource_provider is not None:
                lease = await self._resource_provider().acquire({
                    **request, "identityPackage": instance.identity_package, "userDataDir": str(directory),
                }, f"maintenance:{instance.instance_id}")
                command = {**lease.browser, "headless": False, "executablePath": str(lease.executable)}
                upstream = command.pop("proxy", None)
                if upstream is not None:
                    relay = BrowserProxyRelay(upstream)
                    relay.__enter__()
                    command["proxy"] = {"server": relay.url}
            else:
                self._profiles.get(profile.id)
                command = self._launch_command(profile, self._kernel_executable(profile))
            context = await self._launcher(directory, command)
        except BaseException:
            if relay is not None:
                relay.close()
            if lease is not None:
                lease.release()
            raise
        if lease is not None:
            self._leases[instance.instance_id] = lease
        if relay is not None:
            self._relays[instance.instance_id] = relay
        return context

    async def _close_owned(self, instance_id, context):
        await context.close()
        if instance_id in self._relays:
            self._relays.pop(instance_id).close()
        if instance_id in self._leases:
            self._leases[instance_id].release()
            self._leases.pop(instance_id)

    def closer(self, _service, instance) -> None:
        """``closer`` hook: close the owned context and confirm it is gone."""

        instance_id = instance.instance_id
        with self._lock:
            context = self._contexts.pop(instance_id, None)
            pending = self._settled.get(instance_id)
        if pending is not None:
            # The window is still coming up. Waiting for it is the only way End
            # can both keep the login and close the browser: refusing here left
            # the user with a failed End and a running kernel they could not stop.
            pending.wait(timeout=_START_SETTLE_SECONDS)
            with self._lock:
                context = self._contexts.pop(instance_id, None)
                pending = self._settled.get(instance_id)
        if pending is not None:
            raise environment_error(
                "INSTANCE_NOT_QUIESCENT", "浏览器仍在启动，请稍后重试", 409
            )
        if context is None:
            # Nothing of ours to close. A task browser that is still winding down
            # gets a bounded chance to release the copy: failing the whole End in
            # that window would throw away a save the user already asked for.
            if self._store.runtime_lock_present(instance_id) and not self._wait_for_release(
                instance_id
            ):
                raise environment_error(
                    "INSTANCE_NOT_QUIESCENT",
                    "环境工作副本仍被浏览器占用，请先结束该任务",
                    409,
                )
            return
        try:
            self._owner_loop().run(self._close_owned(instance_id, context), timeout=_CLOSE_TIMEOUT_SECONDS)
        except Exception as error:
            # The context stays owned: a later attempt may still close it, and a
            # copy that is not confirmed closed must never be copied as a save.
            with self._lock:
                self._contexts[instance_id] = context
            raise environment_error(
                "INSTANCE_NOT_QUIESCENT", "无法确认浏览器已关闭，请核验运行现场", 409
            ) from error

    def _wait_for_release(self, instance_id: str) -> bool:
        """Wait for a foreign browser to let go of the work copy.

        Returns ``True`` once the copy is free, ``False`` when it is still held
        after the bounded wait, so the caller can refuse instead of copying a
        profile that is still being written.
        """

        deadline = time.monotonic() + _COPY_RELEASE_SECONDS
        while time.monotonic() < deadline:
            if not self._store.runtime_lock_present(instance_id):
                return True
            time.sleep(0.25)
        return not self._store.runtime_lock_present(instance_id)

    def shutdown(self) -> None:
        with self._lock:
            contexts = list(self._contexts.items())
            owner = self._owner
        for instance_id, context in contexts:
            try:
                if owner is not None:
                    owner.run(self._close_owned(instance_id, context), timeout=_CLOSE_TIMEOUT_SECONDS)
                with self._lock:
                    self._contexts.pop(instance_id, None)
            except Exception:  # noqa: BLE001, S112 -- preserve ownership when close is unconfirmed.
                continue
        if owner is not None and not self._contexts:
            owner.stop()

    def owner_loop_running(self) -> bool:
        """True while the owner loop thread is alive; false after shutdown."""

        with self._lock:
            owner = self._owner
        return owner is not None and owner._thread.is_alive()

    def _instance_directory(self, instance_id: str) -> Path:
        directory = self._store.root / "instances" / instance_id
        if not directory.is_dir():
            raise environment_error(
                "ENVIRONMENT_UNAVAILABLE", "任务环境工作副本不存在", 409
            )
        return directory

    def _kernel_executable(self, profile: Profile) -> Path:
        for kernel in self._installed_kernels():
            if (
                kernel.edition == profile.spec.browser_edition
                and kernel.version == profile.spec.browser_version
            ):
                return kernel.executable_path
        raise KernelNotInstalled

    def _launch_command(self, profile: Profile, executable: Path) -> dict[str, Any]:
        spec = profile.spec
        return {
            "fingerprintSeed": profile.fingerprint_seed,
            "expertArgs": list(spec.expert_args),
            "humanPreset": spec.human_preset,
            "browserVersion": spec.browser_version,
            "releaseChannel": spec.release_channel,
            "geoip": spec.geoip,
            "humanize": spec.humanize,
            "locale": spec.locale,
            "timezone": spec.timezone,
            "colorScheme": spec.color_scheme,
            "userAgent": spec.user_agent,
            "extensionPaths": list(spec.extension_paths),
            "viewport": spec.viewport,
            "executablePath": str(executable),
            "headless": False,
        }

async def _launch_context(user_data_dir: Path, command: dict[str, Any]):
    from cloakbrowser import (  # type: ignore[import-untyped]
        launch_persistent_context_async,
    )

    headless = command.pop("headless", False)
    executable = command.pop("executablePath", None)
    with _pinned_kernel(executable):
        options = persistent_launch_kwargs(user_data_dir, command, headless=headless)
        if command.get("proxy") is not None:
            options["proxy"] = command["proxy"]
        return await launch_persistent_context_async(**options)


@contextmanager
def _pinned_kernel(executable: str | None):
    """Force the profile's installed kernel onto a CloakBrowser launch.

    CloakBrowser resolves the binary itself: a free-plan license key silently
    upgrades to the latest Pro build and drops the version pin, so a profile that
    declares the installed public kernel would otherwise run a different
    executable (and demand a license for it). ``CLOAKBROWSER_BINARY_PATH`` is the
    same override the out-of-process workers already receive, so the declared
    kernel is what actually launches.
    """

    if not executable:
        yield
        return
    with _KERNEL_ENV_LOCK:
        previous = os.environ.get(_KERNEL_ENV)
        os.environ[_KERNEL_ENV] = executable
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop(_KERNEL_ENV, None)
            else:
                os.environ[_KERNEL_ENV] = previous
