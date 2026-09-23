"""Real application routing/auth/gate contract; no renderer or automation execution."""
from uuid import uuid4

from fastapi.testclient import TestClient


def test_project_interaction_routes_require_auth_and_share_quiesce_gate(client: TestClient):
    base = f"/api/v1/projects/{uuid4()}/tasks/{uuid4()}/interactions"
    command = {"commandId": str(uuid4()), "executionGeneration": 1,
               "event": "input_prompt_result", "data": {"requestId": str(uuid4()), "value": "test"}}
    for method, path, kwargs in [
        ("GET", "/api/v1/project-run-interactions", {}),
        ("GET", f"{base}/requests/{uuid4()}", {}),
        ("GET", f"{base}/commands/{uuid4()}", {}),
        ("POST", f"{base}/commands", {"json": command}),
    ]:
        response = client.request(method, path, headers={"x-autoflow-token": "invalid"}, **kwargs)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "SIDECAR_UNAUTHORIZED"
    pending = client.get("/api/v1/project-run-interactions")
    assert pending.status_code == 200 and pending.json() == []
    assert pending.headers["cache-control"] == "no-store"
    assert client.get(f"{base}/requests/{uuid4()}").status_code == 404
    gate = client.app.state.settings_runtime.gate
    assert gate.pause(list) == []
    try:
        denied = client.post(f"{base}/commands", json=command)
        assert denied.status_code == 409
        assert denied.json()["error"]["code"] == "SERVICE_QUIESCED"
        assert client.get("/api/v1/project-run-interactions").status_code == 200
    finally:
        gate.resume()
