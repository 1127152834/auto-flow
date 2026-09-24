from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\nreal-image-bytes"


def _upload(client: TestClient, name: str = "示例.png", folder: str = "") -> dict:
    response = client.post(
        "/api/image-assets/upload",
        data={"folder": folder},
        files={"file": (name, PNG, "image/png")},
    )
    assert response.status_code == 200
    return response.json()["asset"]


def test_image_asset_upload_list_read_and_restart_persistence(
    client: TestClient,
) -> None:
    asset = _upload(client)
    assert asset["name"] == asset["originalName"] == "示例.png"
    assert asset["extension"] == "png"
    assert asset["size"] == len(PNG)
    assert asset["folder"] == ""
    assert Path(asset["path"]).is_file()

    assert client.get("/api/image-assets").json() == [asset]
    assert client.get(f"/api/image-assets/{asset['id']}").json() == asset
    for variant in ("thumbnail", "file"):
        response = client.get(f"/api/image-assets/{asset['id']}/{variant}")
        assert response.status_code == 200
        assert response.content == PNG
        assert response.headers["content-type"] == "image/png"

    reloaded = type(client.app.state.image_assets)(client.app.state.paths.workspace)
    assert reloaded.get(asset["id"])["originalName"] == "示例.png"


def test_image_folder_move_rename_and_recursive_delete(client: TestClient) -> None:
    root = client.post(
        "/api/image-assets/folders", json={"name": "页面截图"}
    )
    child = client.post(
        "/api/image-assets/folders",
        json={"name": "登录", "parentPath": "页面截图"},
    )
    assert root.json() == {"success": True, "path": "页面截图"}
    assert child.json() == {"success": True, "path": "页面截图/登录"}

    asset = _upload(client, folder="页面截图/登录")
    renamed = client.put(
        "/api/image-assets/folders/rename",
        json={"oldPath": "页面截图", "newName": "回归截图"},
    )
    assert renamed.json() == {"success": True, "newPath": "回归截图"}
    assert client.get(f"/api/image-assets/{asset['id']}").json()["folder"] == (
        "回归截图/登录"
    )

    moved = client.put(
        "/api/image-assets/move",
        json={"assetId": asset["id"], "targetFolder": "归档/成功"},
    )
    assert moved.json() == {"success": True, "newFolder": "归档/成功"}
    assert client.get("/api/image-assets/folders").json() == [
        "回归截图",
        "回归截图/登录",
        "归档",
        "归档/成功",
    ]

    deleted = client.request(
        "DELETE", "/api/image-assets/folders", json={"folderPath": "归档"}
    )
    assert deleted.json() == {"success": True, "deletedCount": 1}
    assert client.get(f"/api/image-assets/{asset['id']}").status_code == 404


def test_image_asset_rename_delete_and_validation(client: TestClient) -> None:
    first = _upload(client, "first.png")
    second = _upload(client, "second.png")
    renamed = client.put(
        f"/api/image-assets/{first['id']}/rename", params={"newName": "renamed.png"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["asset"]["name"] == "renamed.png"

    duplicate = client.put(
        f"/api/image-assets/{second['id']}/rename", params={"newName": "renamed.png"}
    )
    traversal = client.post(
        "/api/image-assets/folders", json={"name": "../escape"}
    )
    invalid = client.post(
        "/api/image-assets/upload",
        files={"file": ("payload.txt", b"not-image", "text/plain")},
    )
    assert duplicate.status_code == 409
    assert traversal.status_code == invalid.status_code == 422

    stored = Path(renamed.json()["asset"]["path"])
    assert client.delete(f"/api/image-assets/{first['id']}").json() == {
        "success": True
    }
    assert not stored.exists()
    assert client.delete(f"/api/image-assets/{first['id']}").status_code == 404
