from __future__ import annotations

from typing import Any

from autoflow.application.project_automations.resource_query import (
    ProjectAutomationResourceQuery,
)
from autoflow.application.workflows.browser_resources import WorkflowBrowserResources
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
    ) -> None:
        self._query = resource_query
        self._browser = browser_resources

    def __call__(
        self, automation: AutomationRecord, project_defaults: dict[str, Any]
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
        if policy.get("source") != "newFromProfile":
            raise _field_error(
                "environmentPolicy.source", "当前运行仅支持按浏览器配置新建临时环境"
            )
        profile_id = policy.get("profileId") or project_defaults.get("profileId")
        if not isinstance(profile_id, str) or not profile_id:
            raise _field_error("environmentPolicy.profileId", "请选择浏览器配置")

        proxy = _effective_proxy(policy, project_defaults)
        model_provider_id = (
            policy["modelProviderId"]
            if "modelProviderId" in policy
            else project_defaults.get("modelProviderId")
        )
        try:
            request = self._browser.freeze(
                profile_id,
                proxy=proxy,
                model_provider_id=model_provider_id,
            )
        except (ProfileNotFound, KernelNotInstalled, WorkflowRuntimeError) as error:
            raise ProjectRunError(
                "RESOURCE_UNAVAILABLE",
                "运行所需资源不可用",
                422,
                {"retryable": False},
            ) from error
        return {
            **request,
            "automaticExecutionTimeoutSeconds": automation.run_policy[
                "automaticExecutionTimeoutSeconds"
            ],
        }


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
