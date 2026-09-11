import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.database.models import (
    KernelOperationRow,
    LocalModelRow,
    ModelProviderRow,
    ProfileRow,
    ProxyPoolRow,
    ProxyRow,
)
from autoflow.infrastructure.database.proxy_models import (
    ProxyConnectionRow,
    ProxyOperationRow,
)
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway


def _app(tmp_path):
    return create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="settings-test",
            instance_token="renderer",
            host_token="host",
            api_version="v1",
        ),
        credential_store=FakeCredentialStore(),
        model_gateway=FakeModelGateway(),
    )


def test_runtime_and_dashboard_report_real_local_values(tmp_path):
    app = _app(tmp_path)
    now = datetime.now(UTC)
    with app.state.session_factory.begin() as session:
        session.add(ProfileRow(id=str(uuid4()), name="Profile", spec={}, fingerprint_seed=1, created_at=now, updated_at=now))
        session.add_all([
            ProxyRow(id=str(uuid4()), name="Enabled", enabled=True),
            ProxyRow(id=str(uuid4()), name="Disabled", enabled=False),
            ProxyPoolRow(id=str(uuid4()), name="Group"),
        ])
        provider_id = str(uuid4())
        session.add(ModelProviderRow(
            id=provider_id, name="Provider", preset_id=None, provider_kind="openai",
            base_url=None, secret_ref=None, enabled=True, description="",
            connection_status="unknown", last_checked_at=None,
            last_check_latency_ms=None, last_check_message=None,
            created_at=now, updated_at=now,
        ))
        session.add(LocalModelRow(
            id=str(uuid4()), provider_id=provider_id, model_key="model",
            display_name="Model", tags_json=[], context_window=None, enabled=True,
            description="", created_at=now, updated_at=now,
        ))
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        runtime = client.get("/api/v1/settings/runtime")
        assert runtime.status_code == 200
        assert runtime.json() == {
            "apiVersion": "v1",
            "backendVersion": "0.1.0",
            "pythonVersion": runtime.json()["pythonVersion"],
            "sqliteVersion": runtime.json()["sqliteVersion"],
            "paths": {
                "workspace": str(tmp_path),
                "database": str(tmp_path / "data" / "autoflow.sqlite3"),
                "profiles": str(tmp_path / "workspace" / "profiles"),
                "kernels": str(tmp_path / "data" / "kernels"),
                "logs": str(tmp_path / "logs"),
            },
            "blockers": [],
        }
        dashboard = client.get("/api/v1/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json() | {"generatedAt": "ignored"} == {
            "profiles": 1,
            "enabledProxies": 1,
            "proxyGroups": 1,
            "installedKernels": 0,
            "modelProviders": 1,
            "models": 1,
            "generatedAt": "ignored",
        }


def test_quiesce_requires_host_auth_blocks_writes_and_resumes(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        assert client.post("/internal/settings/quiesce").status_code == 401
        assert client.post(
            "/internal/settings/quiesce",
            headers={"x-autoflow-host-token": "host", "origin": "http://renderer"},
        ).status_code == 401
        paused = client.post(
            "/internal/settings/quiesce", headers={"x-autoflow-host-token": "host"}
        )
        assert paused.status_code == 200 and paused.json() == {"paused": True}
        rejected = client.post(
            "/api/v1/profiles",
            headers={"x-autoflow-token": "renderer"},
            json={},
        )
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "SERVICE_QUIESCED"
        guarded_get = client.get(
            "/api/v1/kernels/catalog", headers={"x-autoflow-token": "renderer"}
        )
        assert guarded_get.status_code == 409
        assert guarded_get.json()["error"]["code"] == "SERVICE_QUIESCED"
        resumed = client.post(
            "/internal/settings/resume", headers={"x-autoflow-host-token": "host"}
        )
        assert resumed.status_code == 200 and resumed.json() == {"paused": False}
        assert client.post(
            "/api/v1/profiles",
            headers={"x-autoflow-token": "renderer"},
            json={},
        ).status_code == 422


def test_kernel_catalog_get_is_counted_before_quiesce(tmp_path, monkeypatch):
    app = _app(tmp_path)
    started = Event()
    release = Event()

    async def slow_catalog():
        started.set()
        await asyncio.to_thread(release.wait, 2)
        raise RuntimeError("synthetic catalog failure")

    monkeypatch.setattr(app.state.kernel_service, "catalog", slow_catalog)
    with (
        TestClient(app, raise_server_exceptions=False) as client,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        pending = pool.submit(
            client.get,
            "/api/v1/kernels/catalog",
            headers={"x-autoflow-token": "renderer"},
        )
        assert started.wait(timeout=1)
        paused = client.post(
            "/internal/settings/quiesce",
            headers={"x-autoflow-host-token": "host"},
        )
        assert paused.status_code == 409
        assert "api_mutation_in_progress" in paused.json()["error"]["details"]["blockers"]
        release.set()
        assert pending.result(timeout=2).status_code == 500


def test_quiesce_reports_persisted_and_inflight_blockers(tmp_path):
    app = _app(tmp_path)
    now = datetime.now(UTC)
    with app.state.session_factory.begin() as session:
        profile_id = str(uuid4())
        session.add(ProfileRow(id=profile_id, name="Busy profile", spec={}, fingerprint_seed=1, created_at=now, updated_at=now))
        session.add(KernelOperationRow(
            id=str(uuid4()), kind="kernel_install", status="queued", result={},
            error=None, created_at=now, updated_at=now,
        ))
        session.add(ProxyConnectionRow(
            id=str(uuid4()), name="Syncing", secret_ref="secret", status="connected",
            revision=0, generation=1, sync_token=str(uuid4()), sync_started_at=now,
            last_verified_at=None, last_synced_at=None, last_error=None,
            capabilities=[], created_at=now, updated_at=now,
        ))
        session.add(ProxyOperationRow(
            id=str(uuid4()), kind="probe", target_id=str(uuid4()), status="running",
            resource_revision=None, error=None, created_at=now, updated_at=now,
        ))
    profile_path = tmp_path / "workspace" / "profiles" / profile_id
    profile_path.mkdir()
    (profile_path / "SingletonLock").touch()
    with TestClient(app) as client:
        response = client.post(
            "/internal/settings/quiesce", headers={"x-autoflow-host-token": "host"}
        )
        assert response.status_code == 409
        assert response.json()["error"]["details"]["blockers"] == [
            "kernel_operation_active",
            "profile_in_use",
            "proxy_operation_active",
            "proxy_sync_active",
        ]

        with app.state.settings_runtime.gate.mutation() as admitted:
            assert admitted
            response = client.post(
                "/internal/settings/quiesce", headers={"x-autoflow-host-token": "host"}
            )
        assert response.status_code == 409
        assert "api_mutation_in_progress" in response.json()["error"]["details"]["blockers"]


def test_dashboard_read_failure_uses_safe_error_envelope(tmp_path, monkeypatch):
    app = _app(tmp_path)

    def fail():
        raise RuntimeError("database detail must not escape")

    monkeypatch.setattr(app.state.settings_runtime, "dashboard", fail)
    with TestClient(app, raise_server_exceptions=False, headers={"x-autoflow-token": "renderer"}) as client:
        response = client.get("/api/v1/dashboard")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "database detail" not in response.text


def test_dashboard_uses_null_when_model_tables_are_not_connected(tmp_path):
    app = _app(tmp_path)
    engine = app.state.session_factory.kw["bind"]
    LocalModelRow.__table__.drop(engine)
    ModelProviderRow.__table__.drop(engine)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    assert response.json()["modelProviders"] is None
    assert response.json()["models"] is None


def test_dashboard_does_not_hide_model_query_failures(tmp_path, monkeypatch):
    app = _app(tmp_path)
    from autoflow.infrastructure.database import settings_runtime

    original_count = settings_runtime._count

    def fail_model_read(session, row):
        if row is ModelProviderRow:
            raise OperationalError("select", {}, RuntimeError("broken storage"))
        return original_count(session, row)

    monkeypatch.setattr(settings_runtime, "_count", fail_model_read)
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"x-autoflow-token": "renderer"},
    ) as client:
        response = client.get("/api/v1/dashboard")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "broken storage" not in response.text
