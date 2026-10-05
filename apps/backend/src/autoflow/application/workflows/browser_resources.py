from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager, nullcontext
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from threading import RLock
from typing import Any, cast
from urllib.parse import quote

from autoflow.application.profiles.service import ProfileService
from autoflow.domain.environments.identity import (
    profile_from_request,
    request_from_identity,
)
from autoflow.domain.identities.region import check_exit, may_start
from autoflow.domain.kernels.errors import LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel, KernelEdition, KernelRef
from autoflow.domain.profiles.errors import KernelNotInstalled, ProxyUnavailable
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy, ProfileSpec
from autoflow.domain.profiles.ports import ProfileUsageGuard
from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.process.project_test_browser_worker import (
    browser_worker_payload,
)


@dataclass
class BrowserLease:
    executable: Path
    browser: dict[str, Any] = field(repr=False)
    _guards: ExitStack = field(repr=False)
    _release_error: BaseException | None = field(default=None, repr=False)

    def release(self) -> None:
        if self._release_error is not None:
            raise self._release_error
        try:
            self._guards.close()
        except BaseException as error:
            self._release_error = error
            raise


@dataclass
class _SharedGuard:
    context: AbstractContextManager[None]
    users: int = 0
    failed: bool = False


class WorkflowBrowserResources:
    """Freeze profile settings; resolve credentials only for the owned worker."""

    def __init__(
        self, profiles: ProfileService,
        installed_kernels: Callable[[], Sequence[InstalledKernel]],
        resolve_proxy: Callable[..., Awaitable[ProfileBrowserProxy | None]],
        read_license: Callable[[], str | None], usage_guard: ProfileUsageGuard,
        kernel_guard: Callable[[KernelRef], AbstractContextManager[None]],
        environment_directory: Callable[[str], Path | None] | None = None,
        group_guard: Callable[[], AbstractContextManager[None]] = nullcontext,
        license_guard: Callable[[], AbstractContextManager[None]] = nullcontext,
        release_proxy: Callable[[str], None] | None = None,
        locate_exit: Callable[[str | None], tuple[str | None, str | None]] | None = None,
    ) -> None:
        self._profiles = profiles
        # Remediation M4 R4-05: (timezone, exit ip) behind a proxy URL, cached for ten minutes.
        self._locate_exit = locate_exit or _locate_exit_with_geoip
        self._exit_cache: dict[str, tuple[float, tuple[str | None, str | None]]] = {}
        self._installed = installed_kernels
        self._resolve_proxy = resolve_proxy
        self._read_license = read_license
        self._usage_guard = usage_guard
        self._kernel_guard = kernel_guard
        self._environment_directory = environment_directory
        self._release_proxy = release_proxy
        self._group_guard = group_guard
        self._license_guard = license_guard
        self._sharing_lock = RLock()
        self._shared: dict[tuple[str, str], _SharedGuard] = {}

    @contextmanager
    def _share(self, key: tuple[str, str], create: Callable[[], AbstractContextManager[None]]) -> Iterator[None]:
        # Dispatcher and maintenance share synchronous guard accounting;
        # reference sharing is internal, the original OS exclusion stays held.
        with self._sharing_lock:
            guard = self._shared.get(key)
            if guard is None:
                guard = _SharedGuard(create())
                guard.context.__enter__()
                self._shared[key] = guard
            if guard.failed:
                raise WorkflowRuntimeError('WORKFLOW_CLEANUP_FAILED', '资源锁清理尚未确认')
            guard.users += 1
        try:
            yield
        finally:
            with self._sharing_lock:
                guard.users -= 1
                # An unknown native lock pins the workspace even if its owner is
                # the final user; other confirmed Run leases can still finish.
                pinned = key == ('workspace', '') and any(value.failed for identity, value in self._shared.items() if identity != key)
                if not guard.users and not pinned:
                    guard.failed = True
                    guard.context.__exit__(None, None, None)
                    self._shared.pop(key)


    @contextmanager
    def guard(self, profile_id: str, kernel: KernelRef) -> Iterator[None]:
        with ExitStack() as guards:
            guards.enter_context(self._share(('workspace', ''), self._group_guard))
            guards.enter_context(self._share(('profile', profile_id), lambda: self._usage_guard.guard(profile_id)))
            guards.enter_context(self._share(('kernel', f'{kernel.edition}:{kernel.version}'), lambda: self._kernel_guard(kernel)))
            if kernel.edition == 'licensed':
                guards.enter_context(self._share(('license', ''), self._license_guard))
            yield

    def freeze(
        self, profile_id: str, *, proxy: dict[str, Any] | None = None,
        model_provider_id: str | None = None, kernel: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = self._profiles.get(profile_id)
        policy = dict({"mode": "profile"} if proxy is None else proxy)
        spec_values = asdict(profile.spec)
        mode = policy.get("mode")
        allowed = {
            "profile": {"mode"}, "none": {"mode"},
            "fixed": {"mode", "proxyId"}, "pool": {"mode", "proxyPoolId"},
        }
        if not isinstance(mode, str) or mode not in allowed or set(policy) != allowed[mode]:
            raise WorkflowRuntimeError("WORKFLOW_RESOURCE_INVALID", "代理策略字段无效", 422)
        if mode == "none":
            spec_values.update(proxy_mode="none", proxy_id=None, proxy_pool_id=None)
        elif mode == "fixed" and isinstance(policy.get("proxyId"), str) and policy['proxyId']:
            spec_values.update(proxy_mode="proxy", proxy_id=policy['proxyId'], proxy_pool_id=None)
        elif mode == "pool" and isinstance(policy.get("proxyPoolId"), str) and policy['proxyPoolId']:
            spec_values.update(proxy_mode="pool", proxy_id=None, proxy_pool_id=policy['proxyPoolId'])
        elif mode != "profile":
            raise WorkflowRuntimeError("WORKFLOW_RESOURCE_INVALID", "代理策略无效", 422)
        if kernel is not None:
            if set(kernel) != {"edition", "version"}:
                raise WorkflowRuntimeError("WORKFLOW_RESOURCE_INVALID", "内核字段无效", 422)
            spec_values.update(browser_edition=kernel["edition"], browser_version=kernel["version"], release_channel="stable")
        spec = ProfileSpec.from_values(spec_values)
        self._kernel(spec)
        return {
            "browser": "newFromProfile", "profileId": profile.id,
            "kernelId": f"{spec.browser_edition}:{spec.browser_version}",
            "proxy": policy, "modelProviderId": model_provider_id,
            "frozenConfiguration": {
                "profileSpec": asdict(spec), "fingerprintSeed": profile.fingerprint_seed,
                "createdAt": profile.created_at.isoformat(),
                "updatedAt": profile.updated_at.isoformat(),
            },
        }

    async def acquire(self, request: Mapping[str, Any], run_id: str, *, work_directory: Path | None = None) -> BrowserLease:
        if request.get("browser") not in {"newFromProfile", "persistent"}:
            raise WorkflowRuntimeError("WORKFLOW_RESOURCE_UNSUPPORTED", "当前运行需要浏览器配置", 422)
        if request.get("browser") == "persistent":
            identity_request = request_from_identity(request.get("identityPackage"))
            if identity_request["profileId"] != request.get("profileId"):
                raise WorkflowRuntimeError("WORKFLOW_RESOURCE_INVALID", "环境身份来源不一致", 422)
            profile = profile_from_request(identity_request)
        else:
            profile = profile_from_request(request)
        profile = _with_identity(profile, request.get("identity"))
        profile_id = profile.id
        guards = ExitStack()
        try:
            kernel = KernelRef(cast(KernelEdition, profile.spec.browser_edition), profile.spec.browser_version)
            guards.enter_context(self.guard(profile_id, kernel))
            self._profiles.get(profile_id)  # The frozen source must still exist.
            executable = self._kernel(profile.spec).executable_path
            identity = request.get("identity")
            identity_id = identity.get("identityId") if isinstance(identity, Mapping) else None
            try:
                proxy = await (
                    self._resolve_proxy(profile, run_id, identity_id=identity_id) if identity_id
                    else self._resolve_proxy(profile, run_id)
                )
            except ProxyUnavailable as error:
                # Rule 2: the identity's proxy reason (e.g. no member in its region) reaches the run.
                reason = str(error) or "所选代理暂不可用"
                raise WorkflowRuntimeError("PROXY_UNAVAILABLE", f"代理不可用：{reason}", 409) from error
            await self._check_exit_region(identity, proxy)
            if self._release_proxy is not None:
                guards.callback(self._release_proxy, run_id)
            license_key = self._read_license() if profile.spec.browser_edition == 'licensed' else None
            if profile.spec.browser_edition == 'licensed' and not license_key:
                raise LicenseInvalid
            browser = browser_worker_payload(run_id, profile, proxy, license_key)
            browser['headless'] = profile.spec.headless
            user_data_dir = str(work_directory) if work_directory is not None else request.get("userDataDir")
            if work_directory is None and self._environment_directory is not None and request.get("sessionMode") != "pool":
                directory = self._environment_directory(run_id)
                if directory is not None:
                    user_data_dir = str(directory)
            if request.get("browser") == "persistent" or user_data_dir is not None:
                if not isinstance(user_data_dir, str) or not user_data_dir:
                    raise WorkflowRuntimeError(
                        "WORKFLOW_RESOURCE_INVALID", "持久环境缺少工作副本目录", 422
                    )
                browser["userDataDir"] = user_data_dir
            return BrowserLease(executable, browser, guards)
        except BaseException:
            guards.close()
            raise

    async def _check_exit_region(self, identity: object, proxy: ProfileBrowserProxy | None) -> None:
        """Remediation M4 R4-05: an identity with a fixed timezone only starts behind a matching exit."""
        if not isinstance(identity, Mapping) or not isinstance(identity.get("region"), Mapping):
            return
        region = dict(identity["region"])
        if not region.get("timezone"):
            return
        key = proxy.proxy_id or proxy.server if proxy is not None else "direct"
        cached = self._exit_cache.get(key)
        now = time.monotonic()
        if cached is not None and now - cached[0] < EXIT_CACHE_SECONDS:
            timezone, exit_ip = cached[1]
        else:
            url = _proxy_url(proxy) if proxy is not None else None
            timezone, exit_ip = await asyncio.to_thread(self._locate_exit, url)
            if timezone:  # an unlocated exit is not cached; the next run looks again
                self._exit_cache[key] = (now, (timezone, exit_ip))
        check = check_exit(region, timezone, exit_ip)
        if not may_start(check, region):
            code = "IDENTITY_REGION_MISMATCH" if check.outcome == "mismatched" else "IDENTITY_REGION_UNVERIFIED"
            raise WorkflowRuntimeError(code, check.message or "身份地区校验未通过", 409)
        if check.outcome in {"mismatched", "unverified"}:
            _logger.warning("身份地区校验提示（按策略继续）：%s", check.message)

    def _kernel(self, spec: ProfileSpec) -> InstalledKernel:
        for kernel in self._installed():
            if kernel.edition == spec.browser_edition and kernel.version == spec.browser_version:
                return kernel
        raise KernelNotInstalled


def _with_identity(profile: Profile, identity: object) -> Profile:
    """Remediation M4 R4-03: an identity's own seed and region replace the template's."""
    if not isinstance(identity, Mapping) or type(identity.get("seed")) is not int:
        return profile
    raw_region = identity.get("region")
    region: Mapping[str, Any] = raw_region if isinstance(raw_region, Mapping) else {}
    spec = replace(
        profile.spec,
        timezone=region.get("timezone") or profile.spec.timezone,
        locale=region.get("locale") or profile.spec.locale,
    )
    return replace(profile, spec=spec, fingerprint_seed=identity["seed"])


EXIT_CACHE_SECONDS = 600.0
_logger = logging.getLogger(__name__)


def _proxy_url(proxy: ProfileBrowserProxy) -> str:
    scheme, _, address = proxy.server.partition("://")
    if not proxy.username:
        return proxy.server
    return f"{scheme}://{quote(proxy.username, safe='')}:{quote(proxy.password, safe='')}@{address}"


def _locate_exit_with_geoip(proxy_url: str | None) -> tuple[str | None, str | None]:
    """Exit timezone and IP through the proxy, from CloakBrowser's GeoLite2 lookup; never raises."""
    try:
        from cloakbrowser import geoip  # type: ignore[import-untyped]

        timezone, _locale, exit_ip = geoip.resolve_proxy_geo_with_ip(proxy_url)
    except Exception as error:  # noqa: BLE001 -- an unlocated exit is handled by the identity policy
        _logger.warning("出口地区检测失败：%s", type(error).__name__)
        return None, None
    return timezone, exit_ip
