from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway


def _client(tmp_path):
    store, gateway = FakeCredentialStore(), FakeModelGateway()
    app = create_app(
        Settings(
            data_dir=str(tmp_path), instance_id="models", instance_token="test-token"
        ),
        credential_store=store,
        model_gateway=gateway,
    )
    return TestClient(app, headers={"x-autoflow-token": "test-token"}), store, gateway


def _provider(models=None):
    return {
        "provider": {
            "name": "Local",
            "presetId": "ollama",
            "providerKind": "openai-compatible",
            "baseUrl": "http://127.0.0.1:9999/v1",
            "apiKey": "",
            "enabled": True,
            "description": "",
        },
        "selectedModels": models or [],
    }


def test_all_fourteen_routes_and_secret_free_reads(tmp_path):
    client, _, _ = _client(tmp_path)
    assert (
        client.post(
            "/api/v1/model-providers/connection-preview", json=_provider()["provider"]
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/model-providers/connect",
        json=_provider(
            [
                {
                    "modelKey": "Model-A",
                    "displayName": "A",
                    "tagsJson": [],
                    "contextWindow": None,
                    "enabled": True,
                    "description": "",
                }
            ]
        ),
    )
    assert response.status_code == 201
    provider = response.json()
    provider_id = provider["id"]
    model_id = provider["models"][0]["id"]
    assert "apiKey" not in provider and "secretRef" not in provider
    assert client.get("/api/v1/model-providers").json()["total"] == 1
    assert client.get(f"/api/v1/model-providers/{provider_id}").status_code == 200
    assert client.post(f"/api/v1/model-providers/{provider_id}/test").status_code == 200
    assert (
        client.get(f"/api/v1/model-providers/{provider_id}/models/discover").status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/model-providers/{provider_id}/models/test",
            json={"modelKey": "Model-A"},
        ).json()["latencyMs"]
        == 2.5
    )
    metadata = {"name": "Local 2", "description": "d", "enabled": True}
    assert (
        client.put(f"/api/v1/model-providers/{provider_id}", json=metadata).status_code
        == 200
    )
    connection = {**_provider()["provider"], "name": "Local 2"}
    connection.pop("apiKey")
    assert (
        client.put(
            f"/api/v1/model-providers/{provider_id}/connection", json=connection
        ).status_code
        == 200
    )
    model = {
        "modelKey": "manual",
        "displayName": "Manual",
        "tagsJson": [],
        "contextWindow": None,
        "enabled": True,
        "description": "",
    }
    created = client.post(f"/api/v1/model-providers/{provider_id}/models", json=model)
    assert created.status_code == 201
    assert (
        client.put(
            f"/api/v1/models/{created.json()['id']}",
            json={**model, "displayName": "Edited"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/models/options").json()["total"] == 2
    assert client.delete(f"/api/v1/models/{model_id}").status_code == 204
    assert client.delete(f"/api/v1/model-providers/{provider_id}").status_code == 204


def test_auth_and_openapi_do_not_expose_secret_ref(tmp_path):
    client, _, _ = _client(tmp_path)
    unauthorized = TestClient(client.app).get("/api/v1/model-providers")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "SIDECAR_UNAUTHORIZED"
    schema = client.get("/openapi.json").json()
    assert "secretRef" not in str(schema)
    assert "/api/v1/model-providers" in schema["paths"]
    assert "post" not in schema["paths"]["/api/v1/model-providers"]


def test_zero_models_and_options_double_filter(tmp_path):
    client, _, _ = _client(tmp_path)
    provider = client.post("/api/v1/model-providers/connect", json=_provider()).json()
    assert provider["models"] == []
    item = {
        "modelKey": "manual",
        "displayName": "Manual",
        "tagsJson": [],
        "contextWindow": None,
        "enabled": True,
        "description": "",
    }
    client.post(f"/api/v1/model-providers/{provider['id']}/models", json=item)
    assert client.get("/api/v1/models/options").json()["total"] == 1
    client.put(
        f"/api/v1/model-providers/{provider['id']}",
        json={"name": "Local", "description": "", "enabled": False},
    )
    assert client.get("/api/v1/models/options").json()["items"] == []
