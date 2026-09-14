from datetime import UTC, datetime
from types import SimpleNamespace

from autoflow.application.project_automations.resource_query import (
    ProjectAutomationResourceQuery,
)
from autoflow.domain.models.errors import ModelError
from autoflow.domain.profiles.errors import ProfileNotFound
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.project_automations.models import AutomationRecord
from autoflow.domain.projects.models import ProjectRecord

NOW = datetime(2026, 9, 15, tzinfo=UTC)


def _profile(*, proxy_mode="none", proxy_id=None, proxy_pool_id=None):
    spec = ProfileSpec.from_values(
        {
            "name": "配置",
            "browser_version": "1",
            "browser_edition": "public",
            "proxy_mode": proxy_mode,
            "proxy_id": proxy_id,
            "proxy_pool_id": proxy_pool_id,
        }
    )
    return Profile("profile-1", spec, 12345, NOW, NOW)


def _automation(policy=None):
    return AutomationRecord(
        "automation-1",
        "project-1",
        "workflow-1",
        "自动化",
        "",
        1,
        {"inputs": []},
        [],
        policy or {"source": "newFromProfile"},
        {},
        NOW,
        NOW,
    )


class Projects:
    def __init__(self, defaults):
        self.project = ProjectRecord(
            "project-1", "项目", "", defaults, 1, "active", NOW, NOW
        )

    def get(self, _project_id):
        return self.project


class Profiles:
    def __init__(self, profile=None):
        self.profile = profile

    def get(self, _profile_id):
        if self.profile is None:
            raise ProfileNotFound
        return self.profile


class Kernels:
    def __init__(self, installed=True):
        self.installed = installed

    def is_installed(self, _edition, _version):
        return self.installed


class Proxies:
    def __init__(self, available=(), pools=()):
        self.available, self.pools = set(available), set(pools)

    def proxy_is_available(self, proxy_id):
        return proxy_id in self.available

    def pool_exists(self, pool_id):
        return pool_id in self.pools


class Models:
    def __init__(self, provider=None):
        self.provider = provider

    def get_provider(self, _provider_id):
        if self.provider is None:
            raise ModelError("MODEL_PROVIDER_NOT_FOUND", "missing", 404)
        return self.provider


def _query(defaults, profile=None, *, installed=True, proxies=None, models=None):
    return ProjectAutomationResourceQuery(
        Projects(defaults),
        Profiles(profile),
        Kernels(installed),
        proxies or Proxies(),
        models or Models(SimpleNamespace(enabled=True)),
    )


def test_reports_missing_profile_and_never_claims_license_availability():
    query = _query(
        {
            "profileId": "missing",
            "proxy": {"mode": "sourceDefault"},
            "modelProviderId": None,
        }
    )

    assert query.inspect_resources(_automation()) == [
        {
            "path": ["environmentPolicy", "profileId"],
            "code": "PROFILE_NOT_FOUND",
            "message": "浏览器配置不存在",
            "resource": {"type": "profile", "profileId": "missing"},
        }
    ]


def test_reports_kernel_and_effective_project_proxy_resources():
    query = _query(
        {
            "profileId": "profile-1",
            "proxy": {"mode": "fixed", "proxyId": "proxy-1"},
            "modelProviderId": None,
        },
        _profile(),
        installed=False,
    )

    issues = query.inspect_resources(_automation())

    assert [issue["code"] for issue in issues] == [
        "KERNEL_NOT_INSTALLED",
        "PROXY_UNAVAILABLE",
    ]
    assert issues[1]["path"] == ["defaultResources", "proxy"]
    assert issues[1]["resource"] == {"type": "proxy", "proxyId": "proxy-1"}


def test_explicit_none_stops_project_and_profile_proxy_inheritance():
    query = _query(
        {
            "profileId": "profile-1",
            "proxy": {"mode": "fixed", "proxyId": "missing"},
            "modelProviderId": None,
        },
        _profile(proxy_mode="proxy", proxy_id="also-missing"),
    )

    issues = query.inspect_resources(
        _automation({"source": "newFromProfile", "proxyOverride": {"mode": "none"}})
    )

    assert issues == []


def test_source_default_falls_back_to_profile_pool_and_checks_it_exists():
    query = _query(
        {
            "profileId": "profile-1",
            "proxy": {"mode": "sourceDefault"},
            "modelProviderId": None,
        },
        _profile(proxy_mode="pool", proxy_pool_id="pool-1"),
        proxies=Proxies(pools={"pool-1"}),
    )

    assert (
        query.inspect_resources(
            _automation(
                {"source": "newFromProfile", "proxyOverride": {"mode": "sourceDefault"}}
            )
        )
        == []
    )


def test_explicit_source_default_skips_project_proxy_and_uses_profile():
    project_missing = _query(
        {
            "profileId": "profile-1",
            "proxy": {"mode": "fixed", "proxyId": "missing"},
            "modelProviderId": None,
        },
        _profile(proxy_mode="proxy", proxy_id="profile-proxy"),
        proxies=Proxies(available={"profile-proxy"}),
    )
    profile_missing = _query(
        {
            "profileId": "missing",
            "proxy": {"mode": "fixed", "proxyId": "project-proxy"},
            "modelProviderId": None,
        },
        proxies=Proxies(available={"project-proxy"}),
    )
    policy = {"source": "newFromProfile", "proxyOverride": {"mode": "sourceDefault"}}

    assert project_missing.inspect_resources(_automation(policy)) == []
    assert [
        item["code"] for item in profile_missing.inspect_resources(_automation(policy))
    ] == ["PROFILE_NOT_FOUND"]


def test_checks_project_model_provider_without_reading_credentials():
    defaults = {
        "profileId": "profile-1",
        "proxy": {"mode": "none"},
        "modelProviderId": "model-1",
    }
    disabled = _query(
        defaults, _profile(), models=Models(SimpleNamespace(enabled=False))
    )
    missing = _query(defaults, _profile(), models=Models())

    assert (
        disabled.inspect_resources(_automation())[0]["code"]
        == "MODEL_PROVIDER_DISABLED"
    )
    assert (
        missing.inspect_resources(_automation())[0]["code"]
        == "MODEL_PROVIDER_NOT_FOUND"
    )


def test_automation_model_none_suppresses_inheritance_and_selected_model_is_located():
    defaults = {
        "profileId": "profile-1",
        "proxy": {"mode": "none"},
        "modelProviderId": "project-model",
    }
    query = _query(defaults, _profile(), models=Models())

    assert (
        query.inspect_resources(
            _automation({"source": "newFromProfile", "modelProviderId": None})
        )
        == []
    )
    issue = query.inspect_resources(
        _automation({"source": "newFromProfile", "modelProviderId": "automation-model"})
    )[0]
    assert issue["path"] == ["environmentPolicy", "modelProviderId"]
    assert issue["resource"] == {
        "type": "modelProvider",
        "modelProviderId": "automation-model",
    }
