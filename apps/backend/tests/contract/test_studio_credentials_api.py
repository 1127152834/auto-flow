from __future__ import annotations

from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from tests.fixtures.model_management import FakeCredentialStore


def _client(tmp_path) -> tuple[TestClient, FakeCredentialStore]:
    store = FakeCredentialStore()
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="studio-credentials",
            instance_token="renderer",
        ),
        credential_store=store,
    )
    return TestClient(app, headers={"x-autoflow-token": "renderer"}), store


def test_credentials_store_only_masked_metadata_in_sqlite(tmp_path) -> None:
    client, secrets = _client(tmp_path)
    with client:
        saved = client.post(
            "/api/credentials",
            json={
                "name": "生产账号",
                "description": "网页登录",
                "fields": {"username": "alice", "password": "never-in-sqlite"},
            },
        )
        assert saved.status_code == 200
        assert saved.json() == {"success": True, "name": "生产账号"}

        listed = client.get("/api/credentials").json()
        assert listed["success"] is True
        assert listed["credentials"][0] == {
            "name": "生产账号",
            "description": "网页登录",
            "revision": 1,
            "fields": [
                {"key": "password", "masked": "••••••"},
                {"key": "username", "masked": "••••••"},
            ],
            "created_at": listed["credentials"][0]["created_at"],
            "updated_at": listed["credentials"][0]["updated_at"],
        }
        assert client.get("/api/credentials/names").json() == {
            "success": True,
            "names": ["生产账号"],
        }
        assert b"never-in-sqlite" not in client.app.state.paths.database.read_bytes()
        assert any(b"never-in-sqlite" in value for value in secrets.values.values())


def test_credential_partial_upsert_field_command_idempotency_and_revision(
    tmp_path,
) -> None:
    client, _ = _client(tmp_path)
    with client:
        client.post(
            "/api/credentials",
            json={"name": "service", "fields": {"token": "one", "region": "cn"}},
        )
        client.post(
            "/api/credentials",
            json={"name": "service", "fields": {"token": "two"}},
        )
        item = client.get("/api/credentials").json()["credentials"][0]
        assert item["revision"] == 2
        assert [field["key"] for field in item["fields"]] == ["region", "token"]

        command = {
            "commandId": "fields-1",
            "name": "service",
            "expectedRevision": 2,
            "operations": [
                {"kind": "rename", "key": "token", "newKey": "api_key"},
                {"kind": "remove", "key": "region"},
            ],
        }
        first = client.post("/api/credentials/fields", json=command)
        repeated = client.post("/api/credentials/fields", json=command)
        assert first.status_code == repeated.status_code == 200
        assert first.json() == repeated.json()
        assert first.json()["credential"]["revision"] == 3
        assert first.json()["credential"]["fields"] == [
            {"key": "api_key", "masked": "••••••"}
        ]

        conflict = client.post(
            "/api/credentials/fields",
            json={**command, "operations": [{"kind": "remove", "key": "token"}]},
        )
        stale = client.post(
            "/api/credentials/fields",
            json={**command, "commandId": "fields-stale"},
        )
        assert conflict.status_code == stale.status_code == 409


def test_credential_rename_delete_and_secret_cleanup(tmp_path) -> None:
    client, secrets = _client(tmp_path)
    with client:
        client.post(
            "/api/credentials",
            json={"name": "old", "fields": {"value": "secret"}},
        )
        old_key = next(iter(secrets.values))
        client.post(
            "/api/credentials",
            json={"name": "occupied", "fields": {"value": "keep"}},
        )
        before_conflict = dict(secrets.values)
        assert client.post(
            "/api/credentials/rename",
            json={"old_name": "old", "new_name": "occupied"},
        ).status_code == 409
        assert secrets.values == before_conflict
        renamed = client.post(
            "/api/credentials/rename",
            json={"old_name": "old", "new_name": "new"},
        )
        assert renamed.json() == {"success": True}
        assert old_key not in secrets.values
        assert client.get("/api/credentials/names").json()["names"] == [
            "new",
            "occupied",
        ]

        deleted = client.delete("/api/credentials/new")
        assert deleted.json() == {"success": True}
        assert len(secrets.values) == 1
        assert client.delete("/api/credentials/new").status_code == 404

        recreated = client.post(
            "/api/credentials",
            json={"name": "new", "fields": {"value": "replacement"}},
        )
        assert recreated.status_code == 200
        revisions = {
            item["name"]: item["revision"]
            for item in client.get("/api/credentials").json()["credentials"]
        }
        assert revisions["new"] > revisions["occupied"]


def test_credential_name_with_slash_can_be_deleted(tmp_path) -> None:
    client, _ = _client(tmp_path)
    with client:
        assert client.post(
            "/api/credentials",
            json={"name": "team/account", "fields": {"token": "secret"}},
        ).status_code == 200
        assert client.delete("/api/credentials/team%2Faccount").json() == {
            "success": True
        }
