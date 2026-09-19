"""Deleting a global resource must not break a saved project reference.

The resource is named by ``projects.default_resources`` or by an automation's
environment policy. Both are saved facts, so the delete is refused with the
owners listed and nothing is removed: no half-deleted profile directory, no
half-deleted proxy connection, no orphaned pool.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.database.models import (
    ModelProviderRow,
    ProfileRow,
    ProjectRow,
    ProxyRow,
)
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.proxy_models import (
    ProxyConnectionRow,
    ProxyProjectionRow,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway

TOKEN = {"x-autoflow-token": "renderer"}
PROFILE_ID = "11111111-1111-4111-8111-111111111111"
PROXY_ID = "22222222-2222-4222-8222-222222222222"
POOL_ID = "33333333-3333-4333-8333-333333333333"
CONNECTION_ID = "44444444-4444-4444-8444-444444444444"
PROJECT_ID = "66666666-6666-4666-8666-666666666666"
PROVIDER_ID = "77777777-7777-4777-8777-777777777777"


@pytest.fixture
def app(tmp_path):
    return create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="resource-references-test",
            instance_token="renderer",
            host_token="host",
            api_version="v1",
        ),
        credential_store=FakeCredentialStore(),
        model_gateway=FakeModelGateway(),
    )


@pytest.fixture
def client(app):
    with TestClient(app, headers=TOKEN) as client:
        yield client


def _project(default_resources: dict) -> ProjectRow:
    now = datetime.now(UTC)
    return ProjectRow(
        id=PROJECT_ID,
        name="引用项目",
        name_key="引用项目",
        description="",
        search_text="",
        default_resources=default_resources,
        management_revision=1,
        lifecycle_state="active",
        created_at=now,
        updated_at=now,
    )


def _automation(app, policy: dict) -> None:
    now = datetime.now(UTC)
    workflow_id = str(uuid4())
    with app.state.session_factory.begin() as session:
        session.add(
            WorkflowDocumentRow(
                id=workflow_id,
                name="引用流程",
                document={},
                layout={},
                revision=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            ProjectAutomationRow(
                id=str(uuid4()),
                project_id=PROJECT_ID,
                workflow_id=workflow_id,
                name="引用自动化",
                name_key="引用自动化",
                search_text="",
                description="",
                management_revision=1,
                input_plan={},
                parameter_schema=[],
                environment_policy=policy,
                run_policy={},
                created_at=now,
                updated_at=now,
            )
        )


def _profile(app, *, edition: str = "public", version: str = "1.2.3") -> None:
    now = datetime.now(UTC)
    with app.state.session_factory.begin() as session:
        session.add(
            ProfileRow(
                id=PROFILE_ID,
                name="引用配置",
                spec={
                    "name": "引用配置",
                    "browser_version": version,
                    "browser_edition": edition,
                },
                fingerprint_seed=1,
                created_at=now,
                updated_at=now,
            )
        )


def _proxy_connection(app) -> None:
    now = datetime.now(UTC)
    with app.state.session_factory.begin() as session:
        session.add(
            ProxyConnectionRow(
                id=CONNECTION_ID,
                name="面板",
                secret_ref="proxy/panel",
                status="ready",
                revision=1,
                generation=1,
                capabilities=[],
                created_at=now,
                updated_at=now,
            )
        )
        session.add(ProxyRow(id=PROXY_ID, name="固定代理", enabled=True))
        session.add(
            ProxyProjectionRow(
                proxy_id=PROXY_ID,
                connection_id=CONNECTION_ID,
                provider_id="provider-1",
                remote_name="固定代理",
                remote_missing=False,
                credential_available=True,
                health_state="untested",
                health_source="none",
                capabilities=[],
                created_at=now,
                updated_at=now,
            )
        )


def _references(payload: dict) -> list[dict]:
    return payload["error"]["details"]["references"]


def test_profile_delete_is_refused_by_project_default(app, client):
    _profile(app)
    with app.state.session_factory.begin() as session:
        session.add(_project({"profileId": PROFILE_ID}))

    response = client.delete(f"/api/v1/profiles/{PROFILE_ID}")

    assert response.status_code == 409, response.text
    payload = response.json()
    assert payload["error"]["code"] == "RESOURCE_REFERENCED"
    assert _references(payload) == [
        {
            "kind": "project",
            "projectId": PROJECT_ID,
            "projectName": "引用项目",
            "path": ["defaultResources", "profileId"],
        }
    ]
    with app.state.session_factory() as session:
        assert session.get(ProfileRow, PROFILE_ID) is not None


def test_profile_delete_is_refused_by_automation_policy(app, client):
    _profile(app)
    with app.state.session_factory.begin() as session:
        session.add(_project({"profileId": None}))
    _automation(app, {"source": "newFromProfile", "profileId": PROFILE_ID})

    response = client.delete(f"/api/v1/profiles/{PROFILE_ID}")

    assert response.status_code == 409, response.text
    references = _references(response.json())
    assert references[0]["kind"] == "automation"
    assert references[0]["path"] == ["environmentPolicy", "profileId"]
    with app.state.session_factory() as session:
        assert session.get(ProfileRow, PROFILE_ID) is not None


def test_unreferenced_profile_still_deletes(app, client):
    _profile(app)

    response = client.delete(f"/api/v1/profiles/{PROFILE_ID}")

    assert response.status_code == 204, response.text
    with app.state.session_factory() as session:
        assert session.get(ProfileRow, PROFILE_ID) is None


def test_kernel_delete_is_refused_through_the_referencing_profile(app, client, monkeypatch):
    _profile(app, version="1.2.3.4")
    with app.state.session_factory.begin() as session:
        session.add(_project({"profileId": PROFILE_ID}))
    monkeypatch.setattr(
        app.state.kernel_service.catalog_provider, "is_installed", lambda *_: True
    )

    response = client.delete("/api/v1/kernels/1.2.3.4?edition=public")

    assert response.status_code == 409, response.text
    payload = response.json()
    assert payload["error"]["code"] == "RESOURCE_REFERENCED"
    assert _references(payload) == [
        {
            "kind": "profile",
            "projectId": PROJECT_ID,
            "projectName": "引用项目",
            "path": ["defaultResources", "profileId"],
            "profileId": PROFILE_ID,
            "profileName": "引用配置",
            "usedBy": "project",
        }
    ]


def test_proxy_connection_delete_is_refused_by_default_resources(app, client):
    _proxy_connection(app)
    with app.state.session_factory.begin() as session:
        session.add(
            _project({"proxy": {"mode": "fixed", "proxyId": PROXY_ID}})
        )

    response = client.delete(f"/api/v1/proxy-panel/connections/{CONNECTION_ID}")

    assert response.status_code == 409, response.text
    payload = response.json()
    assert payload["error"]["code"] == "RESOURCE_REFERENCED"
    assert payload["error"]["details"]["resourceType"] == "proxyConnection"
    assert _references(payload)[0]["path"] == ["defaultResources", "proxy", "proxyId"]
    with app.state.session_factory() as session:
        assert session.get(ProxyConnectionRow, CONNECTION_ID) is not None
        assert session.get(ProxyRow, PROXY_ID) is not None


def test_pool_delete_is_refused_by_automation_override(app, client):
    with app.state.session_factory.begin() as session:
        session.add(_project({"proxy": {"mode": "none"}}))
    _automation(
        app,
        {
            "source": "newFromProfile",
            "profileId": None,
            "proxyOverride": {"mode": "pool", "proxyPoolId": POOL_ID},
        },
    )

    response = client.delete(f"/api/v1/proxy-groups/{POOL_ID}")

    assert response.status_code == 409, response.text
    assert _references(response.json())[0]["path"] == [
        "environmentPolicy",
        "proxyOverride",
        "proxyPoolId",
    ]


def test_model_provider_delete_is_refused_by_automation_policy(app, client):
    now = datetime.now(UTC)
    with app.state.session_factory.begin() as session:
        session.add(
            ModelProviderRow(
                id=PROVIDER_ID,
                name="引用供应商",
                preset_id=None,
                provider_kind="openai",
                base_url=None,
                secret_ref=None,
                enabled=True,
                description="",
                connection_status="untested",
                last_checked_at=None,
                last_check_latency_ms=None,
                last_check_message=None,
                created_at=now,
                updated_at=now,
            )
        )
    with app.state.session_factory.begin() as session:
        session.add(_project({"profileId": None}))
    _automation(app, {"source": "newFromProfile", "modelProviderId": PROVIDER_ID})

    response = client.delete(f"/api/v1/model-providers/{PROVIDER_ID}")

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "RESOURCE_REFERENCED"
    assert _references(response.json())[0]["path"] == [
        "environmentPolicy",
        "modelProviderId",
    ]
    assert client.get(f"/api/v1/model-providers/{PROVIDER_ID}").status_code == 200


def test_active_profile_occupancy_is_reported_separately(app, client, monkeypatch):
    """The usage guard keeps its own answer; a busy profile is not a reference."""
    _profile(app)
    from autoflow.domain.profiles.errors import ProfileDirectoryBusy

    class BusyGuard:
        def guard(self, profile_id: str):
            raise ProfileDirectoryBusy()

    app.state.profile_service.profile_usage = BusyGuard()

    response = client.delete(f"/api/v1/profiles/{PROFILE_ID}")

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "PROFILE_DIRECTORY_BUSY"
    with app.state.session_factory() as session:
        assert session.get(ProfileRow, PROFILE_ID) is not None
