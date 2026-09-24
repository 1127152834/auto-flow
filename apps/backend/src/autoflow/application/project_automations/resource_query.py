from __future__ import annotations

from typing import Any

from autoflow.application.models.service import ModelService
from autoflow.application.profiles.service import ProfileService
from autoflow.application.workflows.core_runtime import WorkflowRuntimeService
from autoflow.domain.environments.identity import (
    profile_from_request,
    request_from_identity,
)
from autoflow.domain.models.errors import ModelError
from autoflow.domain.profiles.errors import ProfileNotFound
from autoflow.domain.profiles.models import Profile
from autoflow.domain.profiles.ports import InstalledKernelLookup, ProxyOptionsLookup
from autoflow.domain.project_automations.models import AutomationRecord
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.projects.ports import Projects
from autoflow.domain.workflows.runtime import WorkflowRuntimeError


class ProjectAutomationResourceQuery:
    """Inspect saved resource references without acquiring or probing them."""

    def __init__(
        self,
        projects: Projects,
        profiles: ProfileService,
        installed_kernels: InstalledKernelLookup,
        proxy_options: ProxyOptionsLookup,
        model_service: ModelService,
        environments: Any | None = None,
        workflow_runtime: WorkflowRuntimeService | None = None,
    ) -> None:
        self._projects = projects
        self._profiles = profiles
        self._installed_kernels = installed_kernels
        self._proxy_options = proxy_options
        self._model_service = model_service
        self._environments = environments
        self._workflow_runtime = workflow_runtime

    def requires_browser(self, automation: AutomationRecord) -> bool:
        return self._workflow_runtime is None or self._workflow_runtime.requires_browser(
            automation.workflow_id
        )

    def inspect_resources(self, automation: AutomationRecord) -> list[dict[str, Any]]:
        project = self._projects.get(automation.project_id)
        if project is None:
            return [
                _issue(
                    ["projectId"],
                    "PROJECT_NOT_FOUND",
                    "项目不存在",
                    "project",
                    automation.project_id,
                )
            ]
        defaults = project.default_resources
        issues: list[dict[str, Any]] = []
        if not self.requires_browser(automation):
            return self._model_issues(automation, defaults) if (
                self._workflow_runtime is not None
                and self._workflow_runtime.requires_default_model(automation.workflow_id)
            ) else []
        profile: Profile | None = None
        policy = automation.environment_policy
        source = policy.get("source")
        profile_id = None if source == "inputEnvironment" else policy.get("profileId") or defaults.get("profileId")
        if source == "fixedEnvironment" and self._environments is not None:
            try:
                selected = self._environments.resolve(automation.project_id, policy)
                profile_id = selected.profile_id
                profile = profile_from_request(request_from_identity(selected.identity_package))
            except (ProjectError, WorkflowRuntimeError) as error:
                profile_id = None
                issues.append(
                    _issue(
                        ["environmentPolicy", "environmentId"],
                        error.code,
                        error.message,
                        "environment",
                        policy.get("environmentId"),
                    )
                )
        if source == "newFromProfile" and not profile_id:
            issues.append(
                _issue(
                    ["environmentPolicy", "profileId"],
                    "PROFILE_REQUIRED",
                    "请选择浏览器配置",
                    "profile",
                    None,
                )
            )
        elif profile_id:
            try:
                current = self._profiles.get(profile_id)
                if source == "newFromProfile":
                    profile = current
            except ProfileNotFound:
                issues.append(
                    _issue(
                        ["environmentPolicy", "profileId"],
                        "PROFILE_NOT_FOUND",
                        "浏览器配置不存在",
                        "profile",
                        profile_id,
                    )
                )
            if profile is not None and not self._installed_kernels.is_installed(
                profile.spec.browser_edition, profile.spec.browser_version
            ):
                kernel_id = (
                    f"{profile.spec.browser_edition}:{profile.spec.browser_version}"
                )
                issues.append(
                    _issue(
                        ["environmentPolicy", "profileId"],
                        "KERNEL_NOT_INSTALLED",
                        "浏览器配置所需内核尚未安装",
                        "kernel",
                        kernel_id,
                    )
                )
        proxy, proxy_path = _effective_proxy(
            automation.environment_policy.get("proxyOverride") if source == "newFromProfile" else None,
            defaults.get("proxy") if source == "newFromProfile" else None,
            profile,
        )
        if proxy.get("mode") == "fixed" and not self._proxy_options.proxy_is_available(
            str(proxy.get("proxyId", ""))
        ):
            issues.append(
                _issue(
                    proxy_path,
                    "PROXY_UNAVAILABLE",
                    "固定代理不存在、未启用或凭据不可用",
                    "proxy",
                    proxy.get("proxyId"),
                )
            )
        elif proxy.get("mode") == "pool" and not self._proxy_options.pool_exists(
            str(proxy.get("proxyPoolId", ""))
        ):
            issues.append(
                _issue(
                    proxy_path,
                    "PROXY_POOL_NOT_FOUND",
                    "代理池不存在",
                    "proxyPool",
                    proxy.get("proxyPoolId"),
                )
            )
        if self._workflow_runtime is None or self._workflow_runtime.requires_default_model(automation.workflow_id):
            issues.extend(self._model_issues(automation, defaults))
        return issues

    def _model_issues(
        self, automation: AutomationRecord, defaults: dict[str, Any]
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if "modelProviderId" in automation.environment_policy:
            model_provider_id = automation.environment_policy["modelProviderId"]
            model_path = ["environmentPolicy", "modelProviderId"]
        else:
            model_provider_id = defaults.get("modelProviderId")
            model_path = ["defaultResources", "modelProviderId"]
        if model_provider_id:
            try:
                provider = self._model_service.get_provider(model_provider_id)
            except ModelError:
                issues.append(
                    _issue(
                        model_path,
                        "MODEL_PROVIDER_NOT_FOUND",
                        "选用的模型提供方不存在",
                        "modelProvider",
                        model_provider_id,
                    )
                )
            else:
                if not provider.enabled:
                    issues.append(
                        _issue(
                            model_path,
                            "MODEL_PROVIDER_DISABLED",
                            "选用的模型提供方未启用",
                            "modelProvider",
                            model_provider_id,
                        )
                    )
        return issues


def _effective_proxy(
    override: Any, project_proxy: Any, profile: Profile | None
) -> tuple[dict[str, Any], list[str]]:
    if isinstance(override, dict):
        if override.get("mode") != "sourceDefault":
            return override, ["environmentPolicy", "proxyOverride"]
    elif (
        isinstance(project_proxy, dict) and project_proxy.get("mode") != "sourceDefault"
    ):
        return project_proxy, ["defaultResources", "proxy"]
    if profile is None:
        return {"mode": "none"}, ["environmentPolicy", "profileId"]
    if profile.spec.proxy_mode == "proxy":
        return {
            "mode": "fixed",
            "proxyId": profile.spec.proxy_id,
        }, ["environmentPolicy", "profileId"]
    if profile.spec.proxy_mode == "pool":
        return {
            "mode": "pool",
            "proxyPoolId": profile.spec.proxy_pool_id,
        }, ["environmentPolicy", "profileId"]
    return {"mode": "none"}, ["environmentPolicy", "profileId"]


def _issue(
    path: list[str], code: str, message: str, resource_type: str, resource_id: Any
) -> dict[str, Any]:
    resource = {"type": resource_type}
    if resource_id is not None:
        resource[f"{resource_type}Id"] = resource_id
    return {"path": path, "code": code, "message": message, "resource": resource}
