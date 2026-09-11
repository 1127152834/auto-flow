from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway


def test_merged_domains_keep_routes_validation_and_host_isolation(tmp_path):
    app = create_app(
        Settings(data_dir=str(tmp_path), instance_id="merged", instance_token="renderer", host_token="host"),
        credential_store=FakeCredentialStore(), model_gateway=FakeModelGateway(),
    )
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        for path in ("/profiles", "/proxy-panel/connections", "/proxy-groups", "/model-providers", "/kernels/installed"):
            assert client.get(f"/api/v1{path}").status_code == 200, path
        model_error = client.post("/api/v1/model-providers/connection-preview", json={
            "name": "OpenAI", "presetId": "openai", "providerKind": "openai", "baseUrl": "https://example.invalid/v1", "apiKey": "",
        })
        assert model_error.status_code == 422
        assert model_error.json()["error"]["code"] == "MODEL_PROVIDER_API_KEY_REQUIRED"
        proxy_error = client.post("/api/v1/proxy-panel/connections", json={"api_key": "synthetic-key", "name": ""})
        assert proxy_error.status_code == 422
        assert "field_errors" in proxy_error.json()["error"]
        assert "synthetic-key" not in proxy_error.text
        unauthorized = client.get("/api/v1/model-providers", headers={"x-autoflow-token": "invalid"})
        assert unauthorized.status_code == 401
        assert unauthorized.json()["error"]["code"] == "SIDECAR_UNAUTHORIZED"
        assert client.post("/internal/kernels/resolve", json={}).status_code == 401
        assert client.post("/internal/kernels/resolve", json={}, headers={"x-autoflow-host-token": "host", "origin": "null"}).status_code == 401
        paths = client.get("/openapi.json").json()["paths"]
        assert not any(path.startswith("/internal/") for path in paths)
