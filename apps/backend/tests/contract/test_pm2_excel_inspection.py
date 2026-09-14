from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook

from tests.contract.test_settings_dashboard import _app


def test_controlled_excel_inspection_and_scope_recovery(tmp_path):
    source = tmp_path / "资料.xlsx"
    workbook = Workbook()
    workbook.active.append(["编号", "姓名"])
    workbook.active.append(["001", "林一"])
    workbook.save(source)
    original = source.read_bytes()
    with TestClient(_app(tmp_path), headers={"x-autoflow-token": "renderer"}) as client:
        project = client.post(
            "/api/v1/projects",
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": "文件验收"},
        ).json()["projectId"]
        token, key = str(uuid4()), str(uuid4())
        body = {
            "selectionToken": token,
            "path": str(source),
            "projectId": project,
            "windowId": 7,
            "purpose": "inspectExcel",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        assert (
            client.post("/internal/project-files/selections", json=body).status_code
            == 401
        )
        registered = client.post(
            "/internal/project-files/selections",
            json=body,
            headers={
                "x-autoflow-host-token": "host",
                "x-autoflow-file-window-token": "test-proof-012345678901234567890123456789",
            },
        )
        assert registered.status_code == 204, registered.text
        path = f"/api/v1/projects/{project}/table-imports/excel/inspect"
        headers = {
            "Idempotency-Key": key,
            "x-autoflow-file-window-id": "7",
            "x-autoflow-file-window-token": "test-proof-012345678901234567890123456789",
        }
        wrong = client.post(
            path,
            json={"selectionToken": token},
            headers={**headers, "x-autoflow-file-window-token": "wrong-proof"},
        )
        assert wrong.status_code in (401, 403, 422), wrong.text
        inspected = client.post(path, json={"selectionToken": token}, headers=headers)
        assert inspected.status_code == 200, inspected.text
        result = inspected.json()
        assert result["inspection"]["sheets"][0]["sample"] == [["001", "林一"]]
        assert result["operation"]["status"] == "succeeded"
        assert result["operation"]["resource"] == {
            "type": "project",
            "projectId": project,
        }
        recovered = client.get(
            f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["result"] == result["inspection"]
        assert (
            str(source) not in recovered.text
            and "test-proof-012345678901234567890123456789" not in recovered.text
        )
        replay = client.post(path, json={"selectionToken": token}, headers=headers)
        assert replay.status_code == 200 and replay.json() == result
        assert source.read_bytes() == original
