from __future__ import annotations

import time

from fastapi.testclient import TestClient


def _module(name: str, *, dependency_id: str | None = None) -> dict[str, object]:
    nodes: list[dict[str, object]] = [
        {
            "id": "value",
            "type": "set_variable",
            "position": {"x": 10, "y": 20},
            "data": {"moduleType": "set_variable", "variableName": "result"},
        }
    ]
    if dependency_id is not None:
        nodes.append(
            {
                "id": "dependency",
                "type": "custom_module",
                "position": {"x": 30, "y": 40},
                "data": {
                    "moduleType": "custom_module",
                    "customModuleId": dependency_id,
                },
            }
        )
    return {
        "name": name,
        "display_name": name.replace("_", " ").title(),
        "description": "HTTP contract fixture",
        "icon": "📦",
        "color": "#8B5CF6",
        "category": "contract",
        "parameters": [],
        "outputs": [],
        "workflow": {"nodes": nodes, "edges": [], "variables": []},
        "tags": ["contract"],
    }


def test_all_eight_frontend_custom_module_routes_use_revisioned_contract(
    client: TestClient,
) -> None:
    create_payload = {
        **_module("route_source"),
        "clientRequestId": "route-create",
    }
    created = client.post("/api/custom-modules", json=create_payload)
    repeated = client.post("/api/custom-modules", json=create_payload)
    assert created.status_code == repeated.status_code == 201
    assert repeated.json() == created.json()
    source = created.json()
    assert source["revision"] == 1

    loaded = client.get(f"/api/custom-modules/{source['id']}")
    listed = client.get(
        "/api/custom-modules", params={"search": "ROUTE", "category": "contract"}
    )
    assert loaded.status_code == listed.status_code == 200
    assert loaded.json() == source
    assert listed.json()["total"] == 1
    assert listed.json()["modules"] == [source]

    updated = client.put(
        f"/api/custom-modules/{source['id']}",
        json={
            "description": "updated through HTTP",
            "expectedRevision": 1,
            "clientRequestId": "route-update",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["name"] == "route_source"

    usage = client.post(f"/api/custom-modules/{source['id']}/increment-usage")
    assert usage.status_code == 200
    assert usage.json() == {"success": True, "usage_count": 1}

    duplicated = client.post(
        f"/api/custom-modules/{source['id']}/duplicate",
        json={"new_name": "route_copy", "clientRequestId": "route-duplicate"},
    )
    assert duplicated.status_code == 201
    assert duplicated.json()["name"] == "route_copy"
    assert duplicated.json()["revision"] == 1

    imported = client.post(
        "/api/custom-modules/import",
        json={**_module("route_import"), "clientRequestId": "route-import"},
    )
    assert imported.status_code == 201
    assert imported.json()["name"] == "route_import"
    assert imported.json()["revision"] == 1

    deleted = client.delete(
        f"/api/custom-modules/{source['id']}",
        params={"expectedRevision": 2, "clientRequestId": "route-delete"},
    )
    repeated_delete = client.delete(
        f"/api/custom-modules/{source['id']}",
        params={"expectedRevision": 2, "clientRequestId": "route-delete"},
    )
    assert deleted.status_code == repeated_delete.status_code == 200
    assert deleted.json() == repeated_delete.json() == {"success": True}


def test_custom_module_http_errors_keep_machine_readable_codes(
    client: TestClient,
) -> None:
    first = client.post(
        "/api/custom-modules",
        json={**_module("unique_name"), "clientRequestId": "error-create"},
    )
    assert first.status_code == 201

    name_conflict = client.post(
        "/api/custom-modules",
        json={**_module("unique_name"), "clientRequestId": "error-name-conflict"},
    )
    stale = client.put(
        f"/api/custom-modules/{first.json()['id']}",
        json={
            "description": "stale",
            "expectedRevision": 9,
            "clientRequestId": "error-stale",
        },
    )
    reused = client.post(
        "/api/custom-modules",
        json={**_module("different"), "clientRequestId": "error-create"},
    )

    assert name_conflict.status_code == 409
    assert name_conflict.json()["error"]["code"] == "CUSTOM_MODULE_NAME_CONFLICT"
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CUSTOM_MODULE_REVISION_CONFLICT"
    assert stale.json()["error"]["details"] == {
        "expectedRevision": 9,
        "currentRevision": 1,
    }
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_workflow_run_freezes_custom_module_revision_and_executes_outputs(
    client: TestClient, profile_payload: dict[str, object]
) -> None:
    module = client.post(
        "/api/custom-modules",
        json={
            **_module("runtime_module"),
            "outputs": [{"name": "result", "label": "结果"}],
            "workflow": {
                "nodes": [
                    {
                        "id": "value",
                        "type": "moduleNode",
                        "position": {"x": 10, "y": 20},
                        "data": {
                            "moduleType": "set_variable",
                            "config": {
                                "variableName": "result",
                                "variableValue": "frozen",
                            },
                        },
                    }
                ],
                "edges": [],
                "variables": [],
            },
            "clientRequestId": "runtime-module-create",
        },
    ).json()
    workflow = client.post(
        "/api/workflows",
        json={
            "id": "custom-module-http-flow",
            "name": "自定义模块 HTTP 闭环",
            "nodes": [
                {
                    "id": "call",
                    "type": "moduleNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "custom_module",
                        "customModuleId": module["id"],
                        "parameterValues": {},
                    },
                }
            ],
            "edges": [],
            "variables": [],
            "clientRequestId": "runtime-module-workflow-create",
        },
    ).json()
    profile = client.post("/api/v1/profiles", json=profile_payload).json()
    execute = client.post(
        f"/api/workflows/{workflow['id']}/execute",
        json={
            "runId": "custom-module-http-run",
            "documentId": workflow["id"],
            "profileId": profile["id"],
        },
    )
    assert execute.status_code == 202, execute.text

    updated = client.put(
        f"/api/custom-modules/{module['id']}",
        json={
            "description": "edited after run start",
            "expectedRevision": 1,
            "clientRequestId": "runtime-module-update",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2

    state = None
    for _ in range(200):
        state = client.get("/api/workflow-runs/custom-module-http-run").json()
        if state["status"] in {"completed", "failed", "stopped", "interrupted"}:
            break
        time.sleep(0.01)
    assert state is not None
    assert state["status"] == "completed"
    run_detail = client.get("/api/workflow-runs/custom-module-http-run")
    assert run_detail.status_code == 200
    snapshot = run_detail.json()["customModuleSnapshots"][module["id"]]
    assert snapshot["revision"] == 1
    assert snapshot["description"] == "HTTP contract fixture"
    assert len(snapshot["snapshotDigest"]) == 64

    results = client.get(
        "/api/workflow-runs/custom-module-http-run/results",
        params={"cursor": 0, "limit": 100},
    ).json()["items"]
    custom_result = next(item for item in results if item["nodeId"] == "call")
    assert custom_result["values"]["outputs"] == {"result": "frozen"}


def test_workflow_save_rejects_missing_custom_module_without_writing_document(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/workflows",
        json={
            "id": "missing-custom-module-flow",
            "name": "缺失自定义模块",
            "nodes": [
                {
                    "id": "missing",
                    "type": "moduleNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "custom_module",
                        "config": {"customModuleId": "does-not-exist"},
                    },
                }
            ],
            "edges": [],
            "variables": [],
            "clientRequestId": "missing-custom-module-create",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CUSTOM_MODULE_DEPENDENCY_MISSING"
    assert client.get("/api/workflows/missing-custom-module-flow").status_code == 404


def test_custom_module_delete_is_blocked_while_saved_workflow_references_it(
    client: TestClient,
) -> None:
    module = client.post(
        "/api/custom-modules",
        json={**_module("referenced_module"), "clientRequestId": "reference-create"},
    ).json()
    workflow = client.post(
        "/api/workflows",
        json={
            "id": "module-reference-flow",
            "name": "模块引用保护",
            "nodes": [
                {
                    "id": "call",
                    "type": "moduleNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "custom_module",
                        "customModuleId": module["id"],
                    },
                }
            ],
            "edges": [],
            "variables": [],
            "clientRequestId": "reference-workflow-create",
        },
    )
    assert workflow.status_code == 201

    blocked = client.delete(
        f"/api/custom-modules/{module['id']}",
        params={
            "expectedRevision": module["revision"],
            "clientRequestId": "reference-delete",
        },
    )

    assert blocked.status_code == 409
    error = blocked.json()["error"]
    assert error["code"] == "CUSTOM_MODULE_IN_USE"
    assert error["message"] == "模块仍被工作流或其他自定义模块引用"
    assert error["details"] == {
        "moduleId": module["id"],
        "dependentModuleIds": [],
        "dependentWorkflowIds": ["module-reference-flow"],
    }
