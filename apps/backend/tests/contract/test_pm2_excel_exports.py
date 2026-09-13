from datetime import UTC, datetime, timedelta
from time import monotonic, sleep
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from tests.contract.test_pm2_excel_imports import import_first
from tests.contract.test_settings_dashboard import _app


def lookup(client, project, key):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        response = client.get(
            f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
        )
        assert response.status_code == 200, response.text
        if response.json()["status"] in ("failed", "succeeded"):
            return response.json()
        sleep(0.01)
    raise AssertionError("export did not settle")


def test_export_real_file_and_replay_original_identity(tmp_path):
    with TestClient(_app(tmp_path), headers={"x-autoflow-token": "renderer"}) as client:
        project, proof, _, table = import_first(client, tmp_path)
        base = f"/api/v1/projects/{project}/tables/{table['tableId']}"
        fields = client.get(base + "/fields").json()["items"]
        target, token, key = tmp_path / "result.xlsx", str(uuid4()), str(uuid4())
        selected = client.post(
            "/internal/project-files/selections",
            headers={
                "x-autoflow-host-token": "host",
                "x-autoflow-file-window-token": proof["x-autoflow-file-window-token"],
            },
            json={
                "selectionToken": token,
                "path": str(target),
                "projectId": project,
                "windowId": 7,
                "purpose": "exportXlsx",
                "expiresAt": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            },
        )
        assert selected.status_code == 204, selected.text
        request = {
            "selectionToken": token,
            "datasetGeneration": table["datasetGeneration"],
            "scope": "all",
            "fieldIds": [field["ref"]["fieldId"] for field in fields],
            "includeStatus": True,
        }
        headers = {**proof, "Idempotency-Key": key}
        response = client.post(base + "/exports/xlsx", json=request, headers=headers)
        assert response.status_code == 202, response.text
        result = lookup(client, project, key)
        assert result["status"] == "succeeded", result
        assert (
            result["result"]["filename"] == target.name
            and result["result"]["recordCount"] == 1
        )
        assert str(tmp_path) not in str(result)
        book = load_workbook(target)
        assert list(book.active.values)[1][0] == "001"
        before = target.read_bytes()
        replay = client.post(base + "/exports/xlsx", json=request, headers=headers)
        assert replay.status_code == 202, replay.text
        assert replay.json()["operation"]["operationId"] == result["operationId"]
        assert target.read_bytes() == before
        wrong = client.post(
            base + "/exports/xlsx",
            json={**request, "includeStatus": False},
            headers=headers,
        )
        assert wrong.status_code == 409
