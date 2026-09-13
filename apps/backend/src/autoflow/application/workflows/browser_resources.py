"""Shared Profile/kernel resource checks for workflow execution and inspection."""
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager, ExitStack
from pathlib import Path

from autoflow.application.profiles.service import ProfileService
from autoflow.domain.kernels.errors import KernelBusy, LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.errors import (
    KernelNotInstalled,
    ProfileDirectoryBusy,
    ProfileNotFound,
    ProxyUnavailable,
)
from autoflow.domain.profiles.models import Profile
from autoflow.domain.workflows.models import WorkflowError, WorkflowIssue


def resource_error(error: Exception) -> WorkflowError:
    if isinstance(error, WorkflowError):
        return error
    mappings: list[tuple[type[Exception], str, str, str, int]] = [
        (ProfileNotFound, "WORKFLOW_PROFILE_NOT_FOUND", "所选浏览器配置不存在", "profileId", 422),
        (ProfileDirectoryBusy, "WORKFLOW_PROFILE_BUSY", "所选浏览器配置正在使用", "profileId", 409),
        (KernelNotInstalled, "WORKFLOW_KERNEL_UNAVAILABLE", "所选浏览器内核未安装或不可用", "profileId", 422),
        (KernelBusy, "WORKFLOW_KERNEL_BUSY", "所选浏览器内核正在使用或安装", "profileId", 409),
        (ProxyUnavailable, "WORKFLOW_PROXY_UNAVAILABLE", "所选代理或代理池不可用", "profileId", 422),
        (LicenseInvalid, "WORKFLOW_LICENSE_UNAVAILABLE", "所选内核需要有效的 License", "profileId", 422),
        (TimeoutError, "WORKFLOW_RESOURCE_TIMEOUT", "运行资源准备超时", "profileId", 422),
    ]
    for exception, code, message, path, status in mappings:
        if isinstance(error, exception):
            return WorkflowError(code, message, status, [WorkflowIssue(None, [path], code, message)])
    return WorkflowError("WORKFLOW_RUN_FAILED", "运行失败，请检查配置与本地服务状态", 500)


def acquire_browser(guards: ExitStack, profiles: ProfileService,
                    kernel_guard: Callable[[Profile], AbstractContextManager[None]],
                    installed_kernels: Callable[[], Sequence[InstalledKernel]],
                    profile_id: str) -> tuple[Profile, Path]:
    guards.enter_context(profiles.profile_usage.guard(profile_id))
    profile = profiles.get(profile_id)
    guards.enter_context(kernel_guard(profile))
    executable = kernel_executable(installed_kernels, profile)
    # Verify configured resource references before accepting the run.
    spec = profile.spec
    if spec.proxy_mode == "proxy" and (
        spec.proxy_id is None or not profiles.proxy_options.proxy_is_available(spec.proxy_id)
    ):
        raise ProxyUnavailable
    if spec.proxy_mode == "pool" and (
        spec.proxy_pool_id is None or not profiles.proxy_options.pool_exists(spec.proxy_pool_id)
    ):
        raise ProxyUnavailable
    return profile, executable


def kernel_executable(installed_kernels: Callable[[], Sequence[InstalledKernel]], profile: Profile) -> Path:
    for kernel in installed_kernels():
        if (kernel.edition == profile.spec.browser_edition and kernel.version == profile.spec.browser_version
                and kernel.executable_path.is_file()):
            return kernel.executable_path
    raise KernelNotInstalled
