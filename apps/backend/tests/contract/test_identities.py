"""Remediation M4 S2 (R4-09): identity HTTP contract."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.identities import identities_router
from autoflow.application.identities.service import IdentityService
from autoflow.application.projects.service import ProjectService
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)

PROJECT = "00000000-0000-4000-8000-0000000000bb"
BASE = f"/api/v1/projects/{PROJECT}/identities"


@pytest.fixture
def client(tmp_path):
    database = tmp_path / "identities.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    now = datetime.now(UTC)
    with factory() as session:
        session.add(ProjectRow(
            id=PROJECT, name="P", name_key="p", description="", search_text="p",
            default_resources={"profileId": None, "proxy": {"mode": "sourceDefault"}, "modelProviderId": None},
            management_revision=1, lifecycle_state="active", created_at=now, updated_at=now,
        ))
        session.commit()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(identities_router(IdentityService(SqlAlchemyIdentities(factory), ProjectService(SqlAlchemyProjects(factory)))))
    yield TestClient(app)
    factory.dispose()


def _create(client, name, key=None):
    return client.post(BASE, headers={"Idempotency-Key": key or str(uuid4())}, json={"name": name})


def test_create_is_idempotent_by_key_and_names_are_unique(client):
    key = str(uuid4())
    first = _create(client, "账号A", key)
    assert first.status_code == 201
    again = _create(client, "账号A", key)
    assert again.status_code == 200 and again.json()["identityId"] == first.json()["identityId"]
    assert _create(client, "账号A").status_code == 409
    listed = client.get(BASE).json()["items"]
    assert [item["name"] for item in listed] == ["账号A"]
    view = listed[0]
    assert len(view["seedFingerprint"]) == 10 and "seed" not in view
    assert view["health"] == {"lastLoginSuccessAt": None, "consecutiveFailures": 0, "banned": False}


def test_rows_get_one_identity_each_and_rerunning_creates_nothing(client):
    body = {"tableId": "t1", "rows": [{"recordKey": f"r{i}", "name": f"行{i}"} for i in range(5)]}
    first = client.post(f"{BASE}/from-records", json=body).json()
    assert (first["created"], first["kept"]) == (5, 0)
    second = client.post(f"{BASE}/from-records", json=body).json()
    assert (second["created"], second["kept"]) == (0, 5)
    assert first["identities"] == second["identities"]
    assert len(client.get(BASE).json()["items"]) == 5


def test_regenerating_a_seed_needs_confirmation_and_changes_the_fingerprint(client):
    created = _create(client, "账号B").json()
    path = f"{BASE}/{created['identityId']}/regenerate-seed"
    refused = client.post(path, json={"confirmRegenerate": False})
    assert refused.status_code == 422 and "重新验证" in refused.json()["error"]["message"]
    changed = client.post(path, json={"confirmRegenerate": True}).json()
    assert changed["seedFingerprint"] != created["seedFingerprint"]


def test_rename_reset_and_delete(client):
    created = _create(client, "账号C").json()
    path = f"{BASE}/{created['identityId']}"
    assert client.patch(path, json={"name": "账号C2"}).json()["name"] == "账号C2"
    assert client.post(f"{path}/reset-health").json()["health"]["consecutiveFailures"] == 0
    assert client.delete(path).status_code == 204
    assert client.get(BASE).json()["items"] == []
    assert client.delete(path).status_code == 404
