from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings


def test_health_returns_instance_metadata():
    client = TestClient(create_app(Settings(data_dir="/tmp/autoflow-test", instance_id="test")))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "apiVersion": "v1",
        "instanceId": "test",
    }
