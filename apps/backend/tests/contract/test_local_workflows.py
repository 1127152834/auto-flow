from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from autoflow.application.workflows.local_files import LocalWorkflowFiles


def _workflow(name: str = "本地流程") -> dict[str, object]:
    return {
        "name": name,
        "nodes": [{"id": "open", "type": "open_page"}],
        "edges": [],
        "variables": [],
    }


def test_local_workflow_round_trip_and_listing(client: TestClient) -> None:
    default = client.get("/api/local-workflows/default-folder")
    assert default.status_code == 200
    folder = Path(default.json()["folder"])
    assert folder == client.app.state.paths.workspace / "local-workflows"
    assert folder.is_absolute()

    saved = client.post(
        "/api/local-workflows/save-to-folder",
        json={"filename": "roundtrip", "content": _workflow()},
    )
    assert saved.status_code == 200
    assert saved.json() == {"success": True, "filename": "roundtrip.json"}

    loaded = client.get("/api/local-workflows/load/roundtrip.json")
    assert loaded.status_code == 200
    assert loaded.json() == {"success": True, "content": _workflow()}

    listed = client.post("/api/local-workflows/list", json={})
    assert listed.status_code == 200
    assert listed.json()["workflows"] == [
        {
            "filename": "roundtrip.json",
            "name": "本地流程",
            "modifiedTime": listed.json()["workflows"][0]["modifiedTime"],
            "size": (folder / "roundtrip.json").stat().st_size,
        }
    ]


def test_active_folder_persists_and_custom_folders_are_isolated(
    client: TestClient, tmp_path: Path
) -> None:
    first = tmp_path / "用户流程甲"
    second = tmp_path / "用户流程乙"
    changed = client.post(
        "/api/local-workflows/active-folder", json={"folder": str(first)}
    )
    assert changed.status_code == 200
    assert changed.json() == {"success": True, "folder": str(first.resolve())}

    assert client.post(
        "/api/local-workflows/save-to-folder",
        json={"filename": "same", "content": _workflow("甲")},
    ).status_code == 200
    assert client.post(
        "/api/local-workflows/save-to-folder",
        json={"filename": "same", "content": _workflow("乙"), "folder": str(second)},
    ).status_code == 200

    assert client.get("/api/local-workflows/active-folder").json()["folder"] == str(
        first.resolve()
    )
    assert client.get("/api/local-workflows/load/same.json").json()["content"][
        "name"
    ] == "甲"
    assert client.get(
        "/api/local-workflows/load/same.json", params={"folder": str(second)}
    ).json()["content"]["name"] == "乙"

    config = json.loads(
        (client.app.state.paths.workspace / "local-workflows.json").read_text("utf-8")
    )
    assert config == {"activeFolder": str(first.resolve())}
    assert LocalWorkflowFiles(client.app.state.paths.workspace).active_folder() == (
        first.resolve()
    )

    reset = client.post("/api/local-workflows/active-folder", json={"folder": ""})
    assert reset.json()["folder"] == client.get(
        "/api/local-workflows/default-folder"
    ).json()["folder"]


def test_invalid_save_does_not_replace_existing_file(client: TestClient) -> None:
    assert client.post(
        "/api/local-workflows/save-to-folder",
        json={"filename": "safe", "content": _workflow("保留")},
    ).status_code == 200

    invalid = client.post(
        "/api/local-workflows/save-to-folder",
        json={"filename": "safe", "content": {"name": "损坏"}},
    )
    assert invalid.status_code == 422
    assert client.get("/api/local-workflows/load/safe.json").json()["content"][
        "name"
    ] == "保留"


def test_filename_traversal_and_relative_folder_are_rejected(
    client: TestClient, tmp_path: Path
) -> None:
    traversal = client.post(
        "/api/local-workflows/save-to-folder",
        json={"filename": "../outside", "content": _workflow()},
    )
    relative = client.post(
        "/api/local-workflows/list", json={"folder": "relative/path"}
    )
    assert traversal.status_code == relative.status_code == 422
    assert not (client.app.state.paths.workspace / "outside.json").exists()
    assert not (tmp_path / "outside.json").exists()


def test_exists_self_heal_and_both_delete_contracts(client: TestClient) -> None:
    client.post(
        "/api/local-workflows/save-to-folder",
        json={"filename": "scheduled", "content": _workflow()},
    )
    assert client.post(
        "/api/local-workflows/check-exists", json={"filename": "scheduled"}
    ).json() == {"exists": True, "filename": "scheduled.json"}

    enabled = client.post(
        "/api/local-workflows/self-heal",
        json={"filename": "scheduled.json", "enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert client.get(
        "/api/local-workflows/self-heal/scheduled.json"
    ).json()["selfHeal"] == {"enabled": True}

    client.post(
        "/api/local-workflows/save-to-folder",
        json={"filename": "scheduled", "content": _workflow("更新后")},
    )
    assert client.get(
        "/api/local-workflows/load/scheduled.json"
    ).json()["content"]["selfHeal"] == {"enabled": True}

    deleted = client.delete("/api/local-workflows/scheduled.json")
    assert deleted.status_code == 200
    assert client.get("/api/local-workflows/load/scheduled.json").status_code == 404

    client.post(
        "/api/local-workflows/save-to-folder",
        json={"filename": "second", "content": _workflow()},
    )
    deleted = client.post(
        "/api/local-workflows/delete", params={"filename": "second.json"}
    )
    assert deleted.status_code == 200
    assert client.delete("/api/local-workflows/missing.json").status_code == 404


def test_import_export_and_open_folder_contract(client: TestClient) -> None:
    imported = client.post(
        "/api/local-workflows/import",
        json={"filename": "portable", "content": _workflow("可移植")},
    )
    assert imported.status_code == 200

    exported = client.get("/api/local-workflows/portable.json/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/json")
    assert json.loads(exported.content)["name"] == "可移植"

    opened = client.post("/api/local-workflows/open-folder", json={})
    assert opened.status_code == 200
    assert opened.json()["folder"] == client.get(
        "/api/local-workflows/active-folder"
    ).json()["folder"]
