from __future__ import annotations

from fastapi.testclient import TestClient


def _workflow(name: str = "真实流程") -> dict[str, object]:
    return {
        "id": "workflow-contract",
        "name": name,
        "nodes": [
            {
                "id": "open",
                "type": "open_page",
                "position": {"x": 80, "y": 120},
                "selected": True,
                "data": {
                    "moduleType": "open_page",
                    "config": {"url": "https://example.test"},
                },
            }
        ],
        "edges": [],
        "variables": [],
    }


def test_workflow_crud_is_idempotent_revisioned_and_strips_editor_state(
    client: TestClient,
) -> None:
    payload = {**_workflow(), "clientRequestId": "create-request"}
    created = client.post("/api/workflows", json=payload)
    repeated = client.post("/api/workflows", json=payload)

    assert created.status_code == repeated.status_code == 201
    assert repeated.json() == created.json()
    body = created.json()
    assert body["id"] == "workflow-contract"
    assert body["revision"] == 1
    assert body["nodes"][0]["position"] == {"x": 80, "y": 120}
    assert "selected" not in body["nodes"][0]

    listed = client.get("/api/workflows")
    loaded = client.get("/api/workflows/workflow-contract")
    assert listed.status_code == loaded.status_code == 200
    assert listed.json() == [body]
    assert loaded.json() == body

    update = client.put(
        "/api/workflows/workflow-contract",
        json={
            **_workflow("已更新"),
            "expectedRevision": 1,
            "clientRequestId": "update-request",
        },
    )
    assert update.status_code == 200
    assert update.json()["name"] == "已更新"
    assert update.json()["revision"] == 2

    stale = client.put(
        "/api/workflows/workflow-contract",
        json={
            **_workflow("旧窗口"),
            "expectedRevision": 1,
            "clientRequestId": "stale-request",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "WORKFLOW_REVISION_CONFLICT"
    assert stale.json()["error"]["details"] == {
        "expectedRevision": 1,
        "currentRevision": 2,
    }


def test_workflow_contract_requires_stable_write_identity_and_authentication(
    client: TestClient,
) -> None:
    missing_id = client.post("/api/workflows", json=_workflow())
    unauthenticated = client.get("/api/workflows", headers={"x-autoflow-token": ""})

    assert missing_id.status_code == 422
    assert missing_id.json()["error"]["code"] == "VALIDATION_ERROR"
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "SIDECAR_UNAUTHORIZED"


def test_static_workflow_routes_are_not_captured_as_document_ids(
    client: TestClient,
) -> None:
    latest = client.get("/api/workflows/data-latest/full")
    globals_response = client.get("/api/workflows/global-variables")

    assert latest.status_code == 501
    assert latest.json()["error"]["code"] == "WORKFLOW_CAPABILITY_PENDING"
    assert globals_response.status_code == 501
    assert globals_response.json()["error"]["code"] == "WORKFLOW_CAPABILITY_PENDING"
