"""Google Sheets route contract: auth, envelopes, DTO shape and refusals."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.sheets import (
    RENDERER_TOKEN,
    FakeSheetsTransport,
    FakeTokenTransport,
    authorize,
    binding_impact,
    connect,
    new_field,
    new_project,
    new_table,
    operation,
    sheets_app,
)

SPREADSHEET = "spreadsheet-1"
SHEET_ID = 1000


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


def prepared(tmp_path, *, grid=None):
    transport = FakeSheetsTransport(
        grid if grid is not None else {"数据": [["编号", "标题"], ["A-1", "第一行"]]}
    )
    app = sheets_app(tmp_path, transport, tokens=FakeTokenTransport())
    client = TestClient(app, headers={"x-autoflow-token": RENDERER_TOKEN})
    project = new_project(client)
    connection = connect(client, project, key())["result"]
    table = new_table(client, project)
    identity = new_field(
        client, project, table["tableId"], "code", "编号", expectedTableRevision=1
    )
    title = new_field(
        client, project, table["tableId"], "title", "标题", expectedTableRevision=2
    )
    return client, transport, project, connection, table, identity, title


def mapping(identity, title):
    return [
        {
            "fieldId": identity["ref"]["fieldId"],
            "columnId": "A",
            "direction": "both",
            "formula": False,
        },
        {
            "fieldId": title["ref"]["fieldId"],
            "columnId": "B",
            "direction": "both",
            "formula": False,
        },
    ]


def inspection_body(connection, identity, title):
    return {
        "connectionId": connection["connectionId"],
        "spreadsheetId": SPREADSHEET,
        "sheetId": SHEET_ID,
        "identityStrategy": {"kind": "column", "columnId": "A"},
        "mapping": mapping(identity, title),
    }


def base(client, project, table):
    return f"/api/v1/projects/{project}/tables/{table['tableId']}"


def test_host_handover_is_not_reachable_from_a_page(tmp_path):
    transport = FakeSheetsTransport({"数据": [["编号"], ["A-1"]]})
    app = sheets_app(tmp_path, transport)
    with TestClient(app, headers={"x-autoflow-token": RENDERER_TOKEN}) as client:
        project = new_project(client)
        body = {
            "projectId": project,
            "accountLabel": "账号",
            "authMethod": "oauth",
            "credential": {"authMethod": "oauth"},
        }
        anonymous = client.post("/internal/google-authorizations", json=body)
        assert anonymous.status_code == 401
        wrong = client.post(
            "/internal/google-authorizations",
            json=body,
            headers={"x-autoflow-host-token": "wrong"},
        )
        assert wrong.status_code == 401
        hidden = client.get("/openapi.json").json()["paths"]
        assert "/internal/google-authorizations" not in hidden


def test_connection_create_replays_and_list_reports_credential_state(tmp_path):
    transport = FakeSheetsTransport({"数据": [["编号"], ["A-1"]]})
    app = sheets_app(tmp_path, transport)
    with TestClient(app, headers={"x-autoflow-token": RENDERER_TOKEN}) as client:
        project = new_project(client)
        token = authorize(client, project, label="团队账号")
        identity = key()
        path = f"/api/v1/projects/{project}/sheets/connections"
        body = {"accountLabel": "团队账号", "authorizationToken": token}
        accepted = client.post(path, json=body, headers=identity)
        assert accepted.status_code == 202, accepted.text
        first = operation(client, project, identity)
        assert first["status"] == "succeeded", first
        assert first["result"]["accountLabel"] == "团队账号"
        assert first["result"]["credentialState"] == "available"
        assert first["result"]["writable"] is True

        replay = client.post(path, json=body, headers=identity)
        assert replay.status_code == 202 and replay.json() == accepted.json()

        directory = client.get(path).json()["items"]
        assert len(directory) == 1
        assert "credentialKey" not in directory[0]

        reused = client.post(
            path,
            json={"accountLabel": "团队账号", "authorizationToken": token},
            headers=key(),
        )
        assert reused.status_code == 410, reused.text


def test_inspection_reports_identity_gaps_and_overlap(tmp_path):
    grid = {"数据": [["编号", "标题"], ["A-1", "第一行"], ["", "缺编号"], ["A-1", "重复"]]}
    client, _unused, project, connection, table, identity, title = prepared(
        tmp_path, grid=grid
    )
    with client:
        response = client.post(
            f"{base(client, project, table)}/sheets/inspect",
            json=inspection_body(connection, identity, title),
            headers=key(),
        )
        assert response.status_code == 200, response.text
        inspection = response.json()["inspection"]
        assert inspection["identitySummary"] == {
            "unique": False,
            "missing": 1,
            "duplicates": 1,
        }
        codes = {issue["code"] for issue in inspection["issues"]}
        assert codes == {"SHEETS_IDENTITY_INCOMPLETE", "SHEETS_IDENTITY_DUPLICATE"}
        assert inspection["valid"] is False
        assert [column["columnId"] for column in inspection["columns"]] == ["A", "B"]


def test_binding_write_is_precondition_checked_and_epochs_forward(tmp_path):
    client, _unused, project, connection, table, identity, title = prepared(tmp_path)
    with client:
        url = f"{base(client, project, table)}/sheets/binding"
        body = {
            **inspection_body(connection, identity, title),
            "expectedTableRevision": 3,
        }
        assert client.get(url).json() is None
        identity_key = key()
        first = binding_impact(client, project, table["tableId"], body)
        accepted = client.put(url, json=first, headers=identity_key)
        assert accepted.status_code == 202, accepted.text
        result = operation(client, project, identity_key)
        assert result["status"] == "succeeded", result
        assert result["result"]["bindingEpoch"] == 1

        stored = client.get(url).json()
        assert stored["spreadsheetId"] == SPREADSHEET
        assert stored["sheetId"] == SHEET_ID
        assert stored["syncPaused"] is False

        table_path = f"/api/v1/projects/{project}/tables/{table['tableId']}"
        revision = client.get(table_path).json()["tableRevision"]
        assert revision == 4

        # Each attempt quotes a confirmation of its own, so what rejects them is
        # the binding channel rather than a stale impact report.
        stale = client.put(
            url,
            json=binding_impact(
                client, project, table["tableId"], {**body, "expectedTableRevision": revision}
            ),
            headers=key(),
        )
        assert stale.status_code == 412, stale.text
        assert stale.json()["error"]["details"]["reason"] == "bindingEpoch"

        wrong_revision = client.put(
            url,
            json=binding_impact(
                client,
                project,
                table["tableId"],
                {**body, "expectedTableRevision": 1, "expectedBindingEpoch": 1},
            ),
            headers=key(),
        )
        assert wrong_revision.status_code == 412
        assert wrong_revision.json()["error"]["details"]["reason"] == "tableRevision"

        # The confirmation the successful write consumed cannot be replayed once
        # the binding epoch it quoted has advanced underneath it.
        replay = client.put(url, json=first, headers=key())
        assert replay.status_code == 412, replay.text
        assert replay.json()["error"]["code"] == "PRECONDITION_FAILED"


def test_read_only_connection_cannot_bind_or_push(tmp_path):
    transport = FakeSheetsTransport({"数据": [["编号", "标题"], ["A-1", "第一行"]]})
    app = sheets_app(tmp_path, transport)
    with TestClient(app, headers={"x-autoflow-token": RENDERER_TOKEN}) as client:
        project = new_project(client)
        connection = connect(client, project, key(), writable=False)["result"]
        assert connection["writable"] is False
        table = new_table(client, project)
        identity = new_field(
            client, project, table["tableId"], "code", "编号", expectedTableRevision=1
        )
        title = new_field(
            client, project, table["tableId"], "title", "标题", expectedTableRevision=2
        )
        body = {
            **inspection_body(connection, identity, title),
            "impactRevision": 1,
            "expectedTableRevision": 3,
        }
        refused = client.put(
            f"{base(client, project, table)}/sheets/binding", json=body, headers=key()
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "GOOGLE_NOT_WRITABLE"


def test_unknown_project_and_table_are_not_found(tmp_path):
    transport = FakeSheetsTransport({"数据": [["编号"], ["A-1"]]})
    app = sheets_app(tmp_path, transport)
    with TestClient(app, headers={"x-autoflow-token": RENDERER_TOKEN}) as client:
        project = new_project(client)
        other = str(uuid4())
        assert client.get(f"/api/v1/projects/{other}/sheets/connections").status_code == 404
        table = new_table(client, project)
        missing = client.get(
            f"{base(client, project, table)}/sync-operations/{uuid4()}"
        )
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "SYNC_OPERATION_NOT_FOUND"


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"spreadsheetId": "a/b"}, "spreadsheetId"),
        ({"sheetId": -1}, "sheetId"),
        ({"identityStrategy": {"kind": "system"}}, "identityStrategy"),
    ],
)
def test_inspection_rejects_malformed_addressing(tmp_path, payload, field):
    client, _unused, project, connection, table, identity, title = prepared(tmp_path)
    with client:
        body = {**inspection_body(connection, identity, title), **payload}
        response = client.post(
            f"{base(client, project, table)}/sheets/inspect", json=body, headers=key()
        )
        assert response.status_code in {422, 501}, response.text
        error = response.json()["error"]
        assert (
            error.get("details", {}).get("field") == field
            or error["code"] == "SYNC_NOT_IMPLEMENTED"
        )


def test_api_failure_is_reported_as_unavailable_source(tmp_path):
    client, transport, project, connection, table, identity, title = prepared(tmp_path)
    from autoflow.providers.data.google_sheets import SheetsApiError

    with client:
        transport.fail_next = SheetsApiError(-1, "unreachable", "无法连接 Google Sheets。")
        response = client.post(
            f"{base(client, project, table)}/sheets/inspect",
            json=inspection_body(connection, identity, title),
            headers=key(),
        )
        assert response.status_code == 502, response.text
        assert response.json()["error"]["code"] == "SHEETS_API_FAILED"
        assert response.json()["error"]["details"]["retryable"] is True
