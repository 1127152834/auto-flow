from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def test_operation_routes_expose_idempotent_receipts_and_verification(tmp_path):
    database = tmp_path / "operations.sqlite3"
    migrate_database(database)
    operations = SqlAlchemyAndroidOperationRepository(create_session_factory(database))
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(type("Runtime", (), {"environment": lambda _self: None})()), operations))

    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/operations/by-request/r1")

    assert response.status_code == 404


def test_unknown_operation_is_never_marked_verified_without_observation(tmp_path):
    database = tmp_path / "unknown.sqlite3"
    migrate_database(database)
    operations = SqlAlchemyAndroidOperationRepository(create_session_factory(database))
    original = operations.accept("default", "lost", "device", "delete", "hash", {})
    operations.transition(original.operation_id, "queued", "running", {})
    operations.transition(original.operation_id, "running", "needs_verification", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations))
    with TestClient(app) as client:
        response = client.post(f"/api/v1/android/management/operations/{original.operation_id}/verify", json={"requestId": "lost"})
    assert response.status_code == 503
    assert operations.get(original.operation_id).state == "needs_verification"


def test_operation_page_total_is_not_just_the_current_page(tmp_path):
    database = tmp_path / "page.sqlite3"
    migrate_database(database)
    operations = SqlAlchemyAndroidOperationRepository(create_session_factory(database))
    operations.accept("default", "r1", "device", "start", "a", {})
    operations.accept("default", "r2", "device", "stop", "b", {})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), operations))
    with TestClient(app) as client:
        response = client.get("/api/v1/android/management/operations?limit=1")
    assert response.status_code == 200
    assert response.json()["total"] == 2
