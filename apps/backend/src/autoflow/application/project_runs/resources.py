from __future__ import annotations

from typing import Any

from autoflow.application.project_automations.resource_query import (
    ProjectAutomationResourceQuery,
)
from autoflow.application.workflows.browser_resources import WorkflowBrowserResources
from autoflow.domain.environments.identity import request_from_identity
from autoflow.domain.environments.models import ResolvedEnvironmentSource
from autoflow.domain.profiles.errors import KernelNotInstalled, ProfileNotFound
from autoflow.domain.project_automations.models import AutomationRecord
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.domain.workflows.runtime import WorkflowRuntimeError


class ProjectRunResourceResolver:
    """Validate saved references and freeze a credential-free run resource request."""

    def __init__(
        self,
        resource_query: ProjectAutomationResourceQuery,
        browser_resources: WorkflowBrowserResources,
        environments: Any | None = None,
    ) -> None:
        self._query = resource_query
        self._browser = browser_resources
        self._environments = environments

    def __call__(
        self,
        automation: AutomationRecord,
        project_defaults: dict[str, Any],
        inputs: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        issues = self._query.inspect_resources(automation)
        if issues:
            raise ProjectRunError(
                "RESOURCE_UNAVAILABLE",
                "运行所需资源不可用",
                422,
                {"issues": issues, "retryable": False},
            )

        policy = automation.environment_policy
        model_provider_id = (
            policy["modelProviderId"]
            if "modelProviderId" in policy
            else project_defaults.get("modelProviderId")
        )
        timing = {
            "manualDeadlineSeconds": automation.run_policy["manualDeadlineSeconds"],
            "automaticExecutionTimeoutSeconds": automation.run_policy["automaticExecutionTimeoutSeconds"],
        }
        if not self._query.requires_browser(automation):
            return {
                "browser": "none",
                **({"modelProviderId": model_provider_id} if model_provider_id else {}),
                **timing,
            }

        source = policy.get("source")
        if source not in {"newFromProfile", "fixedEnvironment", "inputEnvironment"}:
            raise _field_error("environmentPolicy.source", "无效的环境来源")
        proxy = _effective_proxy(policy, project_defaults)
        profile_id = policy.get("profileId") or project_defaults.get("profileId")
        pinned = None
        if source == "fixedEnvironment":
            if self._environments is None:
                raise _field_error("environmentPolicy.source", "保存环境尚未接入")
            pinned = self._environments.resolve(automation.project_id, policy)
            profile_id = pinned.profile_id
        elif source == "inputEnvironment":
            if self._environments is None:
                raise _field_error("environmentPolicy.source", "保存环境尚未接入")
            if inputs is None:
                return {
                    "environmentResolution": "atTaskStart",
                    "environmentPolicy": dict(policy),
                    "proxy": proxy,
                    "modelProviderId": model_provider_id,
                    **timing,
                }
            pinned = self._environments.resolve(
                automation.project_id, policy, inputs=inputs
            )
            profile_id = pinned.profile_id
        if not isinstance(profile_id, str) or not profile_id:
            raise _field_error("environmentPolicy.profileId", "请选择浏览器配置")

        request = (
            request_from_identity(pinned.identity_package) if pinned is not None
            else self._freeze_profile(profile_id, proxy, model_provider_id)
        )
        if pinned is not None:
            request = {
                **request,
                "browser": "persistent",
                "environmentRef": pinned.environment_ref.to_dict() if pinned.environment_ref else None,
                "identityPackage": pinned.identity_package,
                "modelProviderId": model_provider_id,
            }
        return {**request, **timing}

    def freeze_input_environment(
        self, pending: dict[str, Any], selected: ResolvedEnvironmentSource,
    ) -> dict[str, Any]:
        """Freeze the source selected and reserved by the Task claim transaction."""
        request = request_from_identity(selected.identity_package)
        return {
            **request,
            "browser": "persistent",
            "environmentRef": selected.environment_ref.to_dict() if selected.environment_ref else None,
            "identityPackage": selected.identity_package,
            "modelProviderId": pending.get("modelProviderId"),
            "manualDeadlineSeconds": pending["manualDeadlineSeconds"],
            "automaticExecutionTimeoutSeconds": pending["automaticExecutionTimeoutSeconds"],
        }

    def _freeze_profile(
        self, profile_id: str, proxy: dict[str, Any] | None, model_provider_id: str | None,
    ) -> dict[str, Any]:
        try:
            return self._browser.freeze(profile_id, proxy=proxy, model_provider_id=model_provider_id)
        except (ProfileNotFound, KernelNotInstalled, WorkflowRuntimeError) as error:
            raise ProjectRunError(
                "RESOURCE_UNAVAILABLE", "运行所需资源不可用", 422, {"retryable": False},
            ) from error


def _effective_proxy(
    policy: dict[str, Any], project_defaults: dict[str, Any]
) -> dict[str, Any] | None:
    if "proxyOverride" in policy:
        selected = policy["proxyOverride"]
    else:
        selected = project_defaults.get("proxy", {"mode": "sourceDefault"})
    return None if selected.get("mode") == "sourceDefault" else dict(selected)


def _field_error(field: str, message: str) -> ProjectRunError:
    return ProjectRunError(
        "VALIDATION_ERROR",
        "运行资源配置无效",
        422,
        {"fields": {field: message}, "retryable": False},
    )
