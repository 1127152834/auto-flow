from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings


def test_api_v1_requires_matching_token(tmp_path):
    client = TestClient(
        create_app(
            Settings(data_dir=str(tmp_path), instance_id="test", instance_token="secret")
        )
    )
    assert client.get("/api/v1/example").status_code == 401
    assert client.get("/api/v1/example", headers={"x-autoflow-token": "wrong"}).status_code == 401
    assert client.get("/api/v1/example", headers={"x-autoflow-token": "secret"}).status_code == 404


def test_api_v1_rejects_missing_configured_token(tmp_path):
    client = TestClient(create_app(Settings(data_dir=str(tmp_path), instance_id="test")))
    assert client.get("/api/v1/example").status_code == 401
    assert client.get("/api/v1/example", headers={"x-autoflow-token": "anything"}).status_code == 401
