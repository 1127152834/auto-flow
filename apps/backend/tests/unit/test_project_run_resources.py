from datetime import UTC, datetime

import pytest

from autoflow.application.project_runs.resources import ProjectRunResourceResolver
from autoflow.domain.project_automations.models import AutomationRecord
from autoflow.domain.project_runs.models import ProjectRunError

NOW = datetime(2026, 9, 15, tzinfo=UTC)


def automation(environment_policy):
    return AutomationRecord(
        "automation-1",
        "project-1",
        "workflow-1",
        "自动化",
        "",
        1,
        {"inputs": []},
        [],
        environment_policy,
        {"automaticExecutionTimeoutSeconds": 12.5, "manualDeadlineSeconds": 300},
        NOW,
        NOW,
    )


class ResourceQuery:
    def __init__(self, issues=()):
        self.issues = list(issues)
        self.seen = []

    def requires_browser(self, value):
        return True

    def inspect_resources(self, value):
        self.seen.append(value)
        return self.issues


class BrowserResources:
    def __init__(self):
        self.calls = []

    def freeze(self, profile_id, *, proxy=None, model_provider_id=None):
        self.calls.append((profile_id, proxy, model_provider_id))
        return {
            "browser": "newFromProfile",
            "profileId": profile_id,
            "proxy": proxy or {"mode": "profile"},
            "modelProviderId": model_provider_id,
            "frozenConfiguration": {"safe": True},
        }


DEFAULTS = {
    "profileId": "project-profile",
    "proxy": {"mode": "fixed", "proxyId": "project-proxy"},
    "modelProviderId": "project-model",
}


def test_freezes_project_defaults_and_automatic_timeout():
    query, browser = ResourceQuery(), BrowserResources()
    resolver = ProjectRunResourceResolver(query, browser)

    request = resolver(automation({"source": "newFromProfile"}), DEFAULTS)

    assert query.seen[0].automation_id == "automation-1"
    assert browser.calls == [
        (
            "project-profile",
            {"mode": "fixed", "proxyId": "project-proxy"},
            "project-model",
        )
    ]
    assert request["automaticExecutionTimeoutSeconds"] == 12.5
    assert request["manualDeadlineSeconds"] == 300
    assert request["frozenConfiguration"] == {"safe": True}


def test_browser_free_task_freezes_project_model_default_and_explicit_override():
    class NoBrowserQuery(ResourceQuery):
        def requires_browser(self, value):
            return False

    browser = BrowserResources()
    resolver = ProjectRunResourceResolver(NoBrowserQuery(), browser)
    inherited = resolver(automation({"source": "newFromProfile"}), DEFAULTS)
    overridden = resolver(
        automation({"source": "newFromProfile", "modelProviderId": "task-model"}),
        DEFAULTS,
    )
    disabled = resolver(
        automation({"source": "newFromProfile", "modelProviderId": None}),
        DEFAULTS,
    )

    assert inherited == {"browser": "none", "modelProviderId": "project-model", "automaticExecutionTimeoutSeconds": 12.5, "manualDeadlineSeconds": 300}
    assert overridden["modelProviderId"] == "task-model"
    assert "modelProviderId" not in disabled
    assert browser.calls == []


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"mode": "none"}, {"mode": "none"}),
        (
            {"mode": "fixed", "proxyId": "chosen"},
            {"mode": "fixed", "proxyId": "chosen"},
        ),
        (
            {"mode": "pool", "proxyPoolId": "pool-1"},
            {"mode": "pool", "proxyPoolId": "pool-1"},
        ),
    ],
)
def test_explicit_proxy_override_replaces_project_default(override, expected):
    browser = BrowserResources()
    resolver = ProjectRunResourceResolver(ResourceQuery(), browser)

    resolver(
        automation({"source": "newFromProfile", "proxyOverride": override}),
        DEFAULTS,
    )

    assert browser.calls[0][1] == expected


def test_explicit_source_default_skips_project_proxy_and_uses_profile_policy():
    browser = BrowserResources()
    resolver = ProjectRunResourceResolver(ResourceQuery(), browser)

    resolver(
        automation(
            {"source": "newFromProfile", "proxyOverride": {"mode": "sourceDefault"}}
        ),
        DEFAULTS,
    )

    assert browser.calls[0][1] is None


def test_project_source_default_uses_profile_policy_when_override_is_omitted():
    browser = BrowserResources()
    resolver = ProjectRunResourceResolver(ResourceQuery(), browser)
    defaults = {**DEFAULTS, "proxy": {"mode": "sourceDefault"}}

    resolver(automation({"source": "newFromProfile"}), defaults)

    assert browser.calls[0][1] is None


def test_explicit_profile_and_model_values_preserve_null_semantics():
    browser = BrowserResources()
    resolver = ProjectRunResourceResolver(ResourceQuery(), browser)

    resolver(
        automation(
            {
                "source": "newFromProfile",
                "profileId": "chosen-profile",
                "modelProviderId": None,
            }
        ),
        DEFAULTS,
    )

    assert browser.calls == [
        ("chosen-profile", {"mode": "fixed", "proxyId": "project-proxy"}, None)
    ]


def test_resource_issues_block_freezing_and_keep_structured_locations():
    issues = [
        {
            "path": ["environmentPolicy", "profileId"],
            "code": "PROFILE_NOT_FOUND",
            "message": "浏览器配置不存在",
            "resource": {"type": "profile", "profileId": "missing"},
        }
    ]
    browser = BrowserResources()
    resolver = ProjectRunResourceResolver(ResourceQuery(issues), browser)

    with pytest.raises(ProjectRunError) as caught:
        resolver(automation({"source": "newFromProfile"}), DEFAULTS)

    assert caught.value.code == "RESOURCE_UNAVAILABLE"
    assert caught.value.status == 422
    assert caught.value.details == {"issues": issues, "retryable": False}
    assert browser.calls == []


def test_fixed_environment_freezes_persistent_source():
    class Environments:
        def resolve(self, project_id, policy, inputs=None):
            from autoflow.domain.environments.models import (
                EnvironmentRef,
                ResolvedEnvironmentSource,
            )

            return ResolvedEnvironmentSource(
                "fixedEnvironment",
                EnvironmentRef(project_id, policy["environmentId"], 4, 1),
                "env-profile",
                {"source": "fixedEnvironment", "environmentId": policy["environmentId"]},
            )

    browser = BrowserResources()
    resolver = ProjectRunResourceResolver(ResourceQuery(), browser, Environments())
    request = resolver(
        automation(
            {
                "source": "fixedEnvironment",
                "environmentId": "00000000-0000-0000-0000-000000000010",
            }
        ),
        DEFAULTS,
    )
    assert request["browser"] == "persistent"
    assert request["environmentRef"]["contentGeneration"] == 4
    assert browser.calls[0][0] == "env-profile"


def test_rejects_missing_effective_profile_without_freezing():
    browser = BrowserResources()
    resolver = ProjectRunResourceResolver(ResourceQuery(), browser)

    with pytest.raises(ProjectRunError) as caught:
        resolver(
            automation({"source": "newFromProfile"}),
            {**DEFAULTS, "profileId": None},
        )

    assert caught.value.details["fields"] == {
        "environmentPolicy.profileId": "请选择浏览器配置"
    }
    assert browser.calls == []


@pytest.mark.parametrize("defaults", [{}, {"profileId": "unrelated-default"}])
def test_input_environment_defers_profile_until_claim_and_uses_selected_source(defaults):
    from autoflow.domain.environments.models import (
        EnvironmentRef,
        ResolvedEnvironmentSource,
    )

    browser = BrowserResources()
    resolver = ProjectRunResourceResolver(ResourceQuery(), browser, object())
    pending = resolver(automation({"source": "inputEnvironment", "inputId": "input-1", "proxyOverride": {"mode": "none"}}), defaults)
    assert pending["environmentResolution"] == "atTaskStart"
    assert "profileId" not in pending
    assert browser.calls == []
    selected = ResolvedEnvironmentSource("inputEnvironment", EnvironmentRef("project-1", "environment-1", 3, 1), "saved-profile", {"profileId": "saved-profile"})
    request = resolver.freeze_input_environment(pending, selected)
    assert browser.calls == [("saved-profile", {"mode": "none"}, None)]
    assert request["browser"] == "persistent"
    assert request["environmentRef"]["contentGeneration"] == 3
    assert request["automaticExecutionTimeoutSeconds"] == 12.5
    assert "environmentResolution" not in request
