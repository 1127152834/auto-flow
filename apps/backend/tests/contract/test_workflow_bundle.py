from __future__ import annotations

from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\nbundle-image"


def test_workflow_bundle_round_trips_module_and_image_dependencies(
    client: TestClient,
) -> None:
    module = client.post(
        "/api/custom-modules",
        json={
            "clientRequestId": "bundle-module-create",
            "name": "bundle_module",
            "display_name": "整包模块",
            "workflow": {
                    "nodes": [
                        {"id": "inside", "type": "set_variable", "data": {}}
                    ],
                "edges": [],
            },
        },
    )
    assert module.status_code == 201, module.text
    module = module.json()
    image = client.post(
        "/api/image-assets/upload",
        files={"file": ("bundle.png", PNG, "image/png")},
    ).json()["asset"]
    workflow = {
        "nodes": [
            {
                "id": "call",
                "type": "custom_module",
                "data": {
                    "customModuleId": module["id"],
                    "config": {"imageAssetId": image["id"]},
                },
            }
        ],
        "edges": [],
        "variables": [],
    }

    exported = client.post(
        "/api/workflow-bundle/export",
        json={"name": "可移植整包", "content": workflow},
    )
    assert exported.status_code == 200
    bundle = exported.json()["bundle"]
    assert bundle["type"] == "webrpa-workflow-bundle"
    assert bundle["version"] == 1
    assert [item["id"] for item in bundle["customModules"]] == [module["id"]]
    assert bundle["images"][0]["id"] == image["id"]
    assert bundle["images"][0]["dataB64"]

    assert client.delete(f"/api/image-assets/{image['id']}").status_code == 200
    assert client.delete(
        f"/api/custom-modules/{module['id']}",
        params={
            "expectedRevision": module["revision"],
            "clientRequestId": "bundle-module-delete",
        },
    ).status_code == 200

    imported = client.post("/api/workflow-bundle/import", json={"bundle": bundle})
    assert imported.status_code == 200
    body = imported.json()
    assert body["success"] is True
    assert body["restored"] == {"customModules": 1, "images": 1}
    restored_module_id = body["workflow"]["nodes"][0]["data"]["customModuleId"]
    assert restored_module_id != module["id"]
    assert client.get(f"/api/custom-modules/{restored_module_id}").status_code == 200
    assert client.get(f"/api/image-assets/{image['id']}/file").content == PNG


def test_workflow_bundle_rejects_invalid_and_missing_dependencies(
    client: TestClient,
) -> None:
    invalid = client.post("/api/workflow-bundle/import", json={"bundle": {}})
    missing = client.post(
        "/api/workflow-bundle/export",
        json={
            "name": "缺依赖",
            "content": {
                "nodes": [
                        {
                            "id": "call",
                            "type": "custom_module",
                            "data": {"customModuleId": "not-found"},
                        }
                ],
                "edges": [],
            },
        },
    )
    assert invalid.status_code == 422
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CUSTOM_MODULE_NOT_FOUND"
