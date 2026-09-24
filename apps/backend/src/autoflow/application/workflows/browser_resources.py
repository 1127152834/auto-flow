from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager, nullcontext
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, cast

from autoflow.application.profiles.service import ProfileService
from autoflow.domain.environments.identity import (
    profile_from_request,
    request_from_identity,
)
from autoflow.domain.kernels.errors import LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel, KernelEdition, KernelRef
from autoflow.domain.profiles.errors import KernelNotInstalled
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
        resolve_proxy: Callable[[Profile, str], Awaitable[ProfileBrowserProxy | None]],
        read_license: Callable[[], str | None], usage_guard: ProfileUsageGuard,
        kernel_guard: Callable[[KernelRef], AbstractContextManager[None]],
        environment_directory: Callable[[str], Path | None] | None = None,
        group_guard: Callable[[], AbstractContextManager[None]] = nullcontext,
        license_guard: Callable[[], AbstractContextManager[None]] = nullcontext,
    ) -> None:
        self._profiles = profiles
        self._installed = installed_kernels
        self._resolve_proxy = resolve_proxy
        self._read_license = read_license
        self._usage_guard = usage_guard
        self._kernel_guard = kernel_guard
        self._environment_directory = environment_directory
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

    async def acquire(self, request: Mapping[str, Any], run_request_id: str) -> BrowserLease:
        if request.get("browser") not in {"newFromProfile", "persistent"}:
            raise WorkflowRuntimeError("WORKFLOW_RESOURCE_UNSUPPORTED", "当前运行需要浏览器配置", 422)
        if request.get("browser") == "persistent":
            identity_request = request_from_identity(request.get("identityPackage"))
            if identity_request["profileId"] != request.get("profileId"):
                raise WorkflowRuntimeError("WORKFLOW_RESOURCE_INVALID", "环境身份来源不一致", 422)
            profile = profile_from_request(identity_request)
        else:
            profile = profile_from_request(request)
        profile_id = profile.id
        guards = ExitStack()
        try:
            kernel = KernelRef(cast(KernelEdition, profile.spec.browser_edition), profile.spec.browser_version)
            guards.enter_context(self.guard(profile_id, kernel))
            self._profiles.get(profile_id)  # The frozen source must still exist.
            executable = self._kernel(profile.spec).executable_path
            proxy = await self._resolve_proxy(profile, run_request_id)
            license_key = self._read_license() if profile.spec.browser_edition == 'licensed' else None
            if profile.spec.browser_edition == 'licensed' and not license_key:
                raise LicenseInvalid
            browser = browser_worker_payload(run_request_id, profile, proxy, license_key)
            browser['headless'] = profile.spec.headless
            user_data_dir = request.get("userDataDir")
            if self._environment_directory is not None:
                directory = self._environment_directory(run_request_id)
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

    def _kernel(self, spec: ProfileSpec) -> InstalledKernel:
        for kernel in self._installed():
            if kernel.edition == spec.browser_edition and kernel.version == spec.browser_version:
                return kernel
        raise KernelNotInstalled
