from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select

from autoflow.application.project_data import excel
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_excel_models import (
    ProjectExcelInspectionJobRow,
)
from tests.contract.test_settings_dashboard import _app


def prepare(client, tmp_path):
    source = tmp_path / "source.xlsx"
    book = Workbook()
    book.active.append(["编号"])
    book.active.append(["001"])
    book.save(source)
    project = client.post(
        "/api/v1/projects",
        json={"name": str(uuid4())[:12]},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()["projectId"]
    proof, token, key = str(uuid4()), str(uuid4()), str(uuid4())
    body = {
        "projectId": project,
        "path": str(source),
        "windowId": 7,
        "purpose": "inspectExcel",
        "selectionToken": token,
        "expiresAt": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    }
    assert (
        client.post(
            "/internal/project-files/selections",
            json=body,
            headers={
                "x-autoflow-host-token": "host",
                "x-autoflow-file-window-token": proof,
            },
        ).status_code
        == 204
    )
    return (
        project,
        token,
        {
            "Idempotency-Key": key,
            "x-autoflow-file-window-id": "7",
            "x-autoflow-file-window-token": proof,
        },
    )


def test_same_identity_during_parsing_finds_original_and_blocks_workspace_switch(
    tmp_path, monkeypatch
):
    app = _app(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        project, token, headers = prepare(client, tmp_path)
        entered, release = Event(), Event()
        original = excel.inspect_workbook

        def slow(path):
            entered.set()
            assert release.wait(5)
            return original(path)

        monkeypatch.setattr(excel, "inspect_workbook", slow)
        path = f"/api/v1/projects/{project}/table-imports/excel/inspect"
        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(
                client.post, path, json={"selectionToken": token}, headers=headers
            )
            try:
                assert entered.wait(5)
                replay = client.post(
                    path, json={"selectionToken": token}, headers=headers
                )
                assert replay.status_code == 202, replay.text
                assert replay.json()["operation"]["status"] in ("accepted", "running")
                assert app.state.project_excel_service.pending_operations()
                gate = client.post(
                    "/internal/settings/quiesce",
                    headers={"x-autoflow-host-token": "host"},
                )
                assert gate.status_code == 409, gate.text
                assert (
                    "project_excel_operation_active"
                    in gate.json()["error"]["details"]["blockers"]
                )
            finally:
                release.set()
            result = first.result(5)
        assert result.status_code == 200, result.text
        assert (
            result.json()["operation"]["operationId"]
            == replay.json()["operation"]["operationId"]
        )


def test_interrupted_inspection_recovers_failed_fact_without_reading_source(
    tmp_path, monkeypatch
):
    app = _app(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        project, token, headers = prepare(client, tmp_path)
        service = app.state.project_excel_service
        monkeypatch.setattr(service._inspections, "claim", lambda _: None)
        accepted = client.post(
            f"/api/v1/projects/{project}/table-imports/excel/inspect",
            json={"selectionToken": token},
            headers=headers,
        )
        assert accepted.status_code == 202
    monkeypatch.setattr(
        excel,
        "inspect_workbook",
        lambda _: (_ for _ in ()).throw(AssertionError("must not reread")),
    )
    restored = _app(tmp_path)
    with TestClient(restored, headers={"x-autoflow-token": "renderer"}) as client:
        response = client.get(
            f"/api/v1/projects/{project}/operations/by-idempotency-key/{headers['Idempotency-Key']}"
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "failed"
        assert response.json()["error"]["code"] == "EXCEL_INSPECTION_INTERRUPTED"
        assert restored.state.project_excel_service.pending_operations() == []
        with restored.state.session_factory() as session:
            assert (
                len(
                    list(
                        session.scalars(
                            select(ProjectOperationRow).where(
                                ProjectOperationRow.kind == "inspectExcel"
                            )
                        )
                    )
                )
                == 1
            )
            assert len(list(session.scalars(select(ProjectExcelInspectionJobRow)))) == 1
