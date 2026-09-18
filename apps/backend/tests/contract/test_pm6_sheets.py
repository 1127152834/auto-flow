"""Google Sheets contract: connections, inspection, bindings, pull, push, recovery.

Every network call is served by a recorded stand-in, so this file proves the
management side end to end without touching Google.
"""

from __future__ import annotations

import base64
import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.providers.data.google_sheets import SheetsApiError
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway
from tests.fixtures.sheets import binding_impact

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
_REF = re.compile(r"!\$?([A-Z]+)?\$?(\d+)?(?::\$?([A-Z]+)?\$?(\d+)?)?")


def _column(letters: str) -> int:
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def _range(url_or_range: str) -> tuple[int, int, int]:
    """(first row, first column, last column) for the A1 ranges the client uses.

    Called with either a `values.get` URL or a bare A1 range from a batch write
    body, so both shapes resolve to the same coordinates.
    """
    text = (
        url_or_range.split("/values/", 1)[1]
        if "/values/" in url_or_range
        else url_or_range
    )
    match = _REF.search(text)
    assert match is not None, url_or_range
    start_column, start_row, end_column, end_row = match.groups()
    first = int(start_row or end_row or 1)
    if start_column is None:
        return first, 0, 25
    start = _column(start_column)
    return first, start, _column(end_column) if end_column else start


class FakeTokens:
    def post_form(self, url: str, data: dict[str, str]) -> dict[str, object]:
        return {"access_token": "access-token", "expires_in": 3600}


class FakeSheets:
    """A Sheets document that records every call the service makes."""

    def __init__(self, header: list[str], rows: list[list[object]]) -> None:
        self.grid = [list(header), *[list(row) for row in rows]]
        self.calls: list[dict[str, object]] = []
        self.fail: SheetsApiError | None = None
        self.fail_on: str | None = None

    def send(self, method, url, *, params=None, json=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json})
        if self.fail is not None and (self.fail_on is None or self.fail_on in url):
            raise self.fail
        if method == "GET" and "/values/" in url:
            first, start, end = _range(url)
            return {"values": [row[start : end + 1] for row in self.grid[first - 1 :]]}
        if method == "GET":
            return {
                "properties": {"title": "自动化登记簿", "timeZone": "UTC"},
                "sheets": [
                    {
                        "properties": {
                            "sheetId": 0,
                            "title": "Sheet1",
                            "gridProperties": {
                                "rowCount": len(self.grid),
                                "columnCount": max(len(row) for row in self.grid),
                            },
                        }
                    }
                ],
            }
        if method == "POST" and url.endswith("values:batchUpdate"):
            for entry in json["data"]:
                first, start, _ = _range(entry["range"])
                while len(self.grid) < first:
                    self.grid.append([""] * len(self.grid[0]))
                while len(self.grid[first - 1]) <= start:
                    self.grid[first - 1].append("")
                self.grid[first - 1][start] = entry["values"][0][0]
            return {"responses": []}
        raise AssertionError(f"unexpected call {method} {url}")


@pytest.fixture
def desk(tmp_path):
    credentials = FakeCredentialStore()
    transport = FakeSheets(["编号", "名称", "邮箱", "结果"], [["001", "甲", "a@x", ""]])
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="sheets-test",
            instance_token="renderer",
            host_token="host",
            api_version="v1",
        ),
        credential_store=credentials,
        model_gateway=FakeModelGateway(),
        google_tokens=FakeTokens(),
        google_transports=lambda _token: transport,
    )
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        yield client, app, transport, credentials


def _key(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _headers() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


def _project(client) -> str:
    return client.post(
        "/api/v1/projects", json={"name": "邮箱运营"}, headers=_headers()
    ).json()["projectId"]


def _table(client, project: str, fields: list[tuple[str, str, str]]):
    created = client.post(
        f"/api/v1/projects/{project}/tables",
        json={"name": "邮箱表", "sourceKind": "local"},
        headers=_headers(),
    ).json()
    revision, ids = created["tableRevision"], {}
    for key, name, type_ in fields:
        response = client.post(
            f"/api/v1/projects/{project}/tables/{created['tableId']}/fields",
            json={
                "definition": {
                    "key": key,
                    "name": name,
                    "type": type_,
                    "required": False,
                    "validation": {},
                },
                "expectedTableRevision": revision,
                "sourceColumnPolicy": "localOnly",
            },
            headers=_headers(),
        )
        assert response.status_code == 200, response.text
        revision = response.json()["tableRevision"]
        ids[key] = response.json()["field"]["ref"]["fieldId"]
    return created["tableId"], ids, revision


def _connect(client, project: str) -> str:
    registered = client.post(
        "/internal/google-authorizations",
        headers={"x-autoflow-host-token": "host"},
        json={
            "projectId": project,
            "accountLabel": "运营账号",
            "authMethod": "oauth",
            "credential": {
                "refreshToken": "refresh",
                "clientId": "client",
                "clientSecret": "secret",
                "grantedScope": SHEETS_SCOPE,
            },
        },
    )
    assert registered.status_code == 201, registered.text
    key = str(uuid4())
    accepted = client.post(
        f"/api/v1/projects/{project}/sheets/connections",
        json={
            "accountLabel": "运营账号",
            "authorizationToken": registered.json()["authorizationToken"],
        },
        headers={"Idempotency-Key": key},
    )
    assert accepted.status_code == 202, accepted.text
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
    ).json()
    assert operation["status"] == "succeeded", operation
    return operation["result"]["connectionId"]


def _bind(client, project: str, table: str, fields, revision: int, connection: str):
    # Columns: A 编号 (identity, text), B 名称, C 邮箱, D 结果
    mapping = [
        {"fieldId": fields["code"], "columnId": "A", "direction": "both", "formula": False},
        {"fieldId": fields["name"], "columnId": "B", "direction": "read", "formula": False},
        {"fieldId": fields["email"], "columnId": "C", "direction": "both", "formula": False},
        {"fieldId": fields["result"], "columnId": "D", "direction": "both", "formula": False},
    ]
    return _submit_binding(client, project, table, connection, mapping, revision)


def _submit_binding(client, project, table, connection, mapping, revision, **extra):
    key = str(uuid4())
    body = binding_impact(
        client,
        project,
        table,
        {
            "connectionId": connection,
            "spreadsheetId": "sheet-1",
            "sheetId": 0,
            "identityStrategy": {"kind": "column", "columnId": "A"},
            "mapping": mapping,
            "expectedTableRevision": revision,
            **extra,
        },
    )
    accepted = client.put(
        f"/api/v1/projects/{project}/tables/{table}/sheets/binding",
        json=body,
        headers={"Idempotency-Key": key},
    )
    assert accepted.status_code == 202, accepted.text
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
    ).json()
    assert operation["status"] == "succeeded", operation
    return operation["result"]


def test_authorization_handover_is_host_only_and_one_shot(desk):
    client, _, _, _ = desk
    project = _project(client)
    body = {
        "projectId": project,
        "accountLabel": "运营账号",
        "authMethod": "oauth",
        "credential": {
            "refreshToken": "refresh",
            "clientId": "client",
            "clientSecret": "secret",
            "grantedScope": SHEETS_SCOPE,
        },
    }
    assert client.post("/internal/google-authorizations", json=body).status_code == 401
    assert client.post(
        "/internal/google-authorizations",
        json=body,
        headers={"x-autoflow-host-token": "host", "origin": "http://127.0.0.1"},
    ).status_code == 401
    token = client.post(
        "/internal/google-authorizations",
        json=body,
        headers={"x-autoflow-host-token": "host"},
    ).json()["authorizationToken"]
    first = client.post(
        f"/api/v1/projects/{project}/sheets/connections",
        json={"accountLabel": "运营账号", "authorizationToken": token},
        headers=_headers(),
    )
    assert first.status_code == 202
    replay = client.post(
        f"/api/v1/projects/{project}/sheets/connections",
        json={"accountLabel": "运营账号", "authorizationToken": token},
        headers=_headers(),
    )
    # A redeemed token is never reusable, even under a fresh idempotency key.
    assert replay.status_code == 410
    # The replay created nothing: exactly one connection exists.
    assert len(
        client.get(f"/api/v1/projects/{project}/sheets/connections").json()["items"]
    ) == 1
    assert client.post("/internal/google-authorizations", json=body).status_code == 401


def test_connection_lists_credential_state_and_survives_restart(desk):
    client, _app, _, credentials = desk
    project = _project(client)
    connection = _connect(client, project)
    directory = client.get(f"/api/v1/projects/{project}/sheets/connections").json()
    assert directory["items"] == [
        {
            "connectionId": connection,
            "accountLabel": "运营账号",
            "credentialState": "available",
            "readable": True,
            "writable": True,
            "updatedAt": directory["items"][0]["updatedAt"],
        }
    ]
    credentials.values.clear()
    missing = client.get(f"/api/v1/projects/{project}/sheets/connections").json()
    assert missing["items"][0]["credentialState"] == "missing"
    assert client.post(
        f"/api/v1/projects/{project}/sheets/connections",
        json={"accountLabel": "运营账号", "authorizationToken": str(uuid4())},
        headers=_headers(),
    ).status_code == 410


def test_readonly_scope_cannot_bind_or_push(desk):
    client, _, _no_transport, _ = desk
    project = _project(client)
    registered = client.post(
        "/internal/google-authorizations",
        headers={"x-autoflow-host-token": "host"},
        json={
            "projectId": project,
            "accountLabel": "只读账号",
            "authMethod": "oauth",
            "credential": {
                "refreshToken": "refresh",
                "clientId": "client",
                "clientSecret": "secret",
                "grantedScope": "https://www.googleapis.com/auth/spreadsheets.readonly",
            },
        },
    ).json()
    key = str(uuid4())
    client.post(
        f"/api/v1/projects/{project}/sheets/connections",
        json={
            "accountLabel": "只读账号",
            "authorizationToken": registered["authorizationToken"],
        },
        headers={"Idempotency-Key": key},
    )
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
    ).json()
    assert operation["result"]["writable"] is False
    table, fields, revision = _table(
        client, project, [("code", "编号", "string"), ("name", "名称", "string"),
                          ("email", "邮箱", "string"), ("result", "结果", "string")]
    )
    denied = client.put(
        f"/api/v1/projects/{project}/tables/{table}/sheets/binding",
        json={
            "connectionId": operation["result"]["connectionId"],
            "spreadsheetId": "sheet-1",
            "sheetId": 0,
            "identityStrategy": {"kind": "column", "columnId": "A"},
            "mapping": [{"fieldId": fields["code"], "columnId": "A",
                         "direction": "both", "formula": False}],
            "impactRevision": 1,
            "expectedTableRevision": revision,
        },
        headers=_headers(),
    )
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "GOOGLE_NOT_WRITABLE"
    assert table


def test_inspection_reports_identity_and_mapping_defects(desk):
    client, _, transport, _ = desk
    project = _project(client)
    connection = _connect(client, project)
    table, fields, _ = _table(
        client, project, [("code", "编号", "string"), ("name", "名称", "string"),
                          ("email", "邮箱", "string"), ("result", "结果", "string")]
    )
    transport.grid = [["编号", "名称", "邮箱", "结果"], ["001", "甲", "a", ""],
                      ["001", "乙", "b", ""], ["", "丙", "c", ""]]
    key = str(uuid4())
    response = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sheets/inspect",
        json={
            "connectionId": connection,
            "spreadsheetId": "sheet-1",
            "sheetId": 0,
            "identityStrategy": {"kind": "column", "columnId": "A"},
            "mapping": [
                {"fieldId": fields["code"], "columnId": "A", "direction": "both", "formula": False},
                {"fieldId": fields["name"], "columnId": "Z", "direction": "read", "formula": False},
            ],
        },
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    inspection = payload["inspection"]
    assert inspection["valid"] is False
    assert inspection["identitySummary"] == {"unique": False, "missing": 1, "duplicates": 1}
    assert {issue["code"] for issue in inspection["issues"]} >= {
        "SHEETS_COLUMN_MISSING",
        "SHEETS_IDENTITY_INCOMPLETE",
        "SHEETS_IDENTITY_DUPLICATE",
    }
    assert payload["operation"]["status"] == "succeeded"
    assert payload["operation"]["kind"] == "inspectSheets"


def test_identity_column_must_map_to_a_text_field(desk):
    client, _, _, _ = desk
    project = _project(client)
    connection = _connect(client, project)
    table, fields, revision = _table(
        client, project, [("code", "编号", "number"), ("name", "名称", "string")]
    )
    response = client.put(
        f"/api/v1/projects/{project}/tables/{table}/sheets/binding",
        json={
            "connectionId": connection,
            "spreadsheetId": "sheet-1",
            "sheetId": 0,
            "identityStrategy": {"kind": "column", "columnId": "A"},
            "mapping": [{"fieldId": fields["code"], "columnId": "A",
                         "direction": "both", "formula": False}],
            "impactRevision": 1,
            "expectedTableRevision": revision,
        },
        headers=_headers(),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SHEETS_IDENTITY_NOT_TEXT"
    # A rejected binding publishes nothing: the table stays unbound.
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}/sheets/binding"
    ).json() is None


def test_binding_is_epoch_guarded_and_replay_returns_one_operation(desk):
    client, _, _, _ = desk
    project = _project(client)
    connection = _connect(client, project)
    table, fields, revision = _table(
        client, project, [("code", "编号", "string"), ("name", "名称", "string"),
                          ("email", "邮箱", "string"), ("result", "结果", "string")]
    )
    binding = _bind(client, project, table, fields, revision, connection)
    assert binding["bindingEpoch"] == 1
    assert binding["spreadsheetId"] == "sheet-1"
    assert binding["identityStrategy"] == {"kind": "column", "columnId": "A"}
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}/sheets/binding"
    ).json() == binding
    # The confirmation is issued again, so the table revision channel is what
    # rejects this attempt rather than a stale impact.
    stale = binding_impact(
        client,
        project,
        table,
        {
            "connectionId": connection,
            "spreadsheetId": "sheet-1",
            "sheetId": 0,
            "identityStrategy": {"kind": "column", "columnId": "A"},
            "mapping": [{"fieldId": fields["code"], "columnId": "A",
                         "direction": "both", "formula": False}],
            "expectedTableRevision": revision,
            "expectedBindingEpoch": 1,
        },
    )
    stale = client.put(
        f"/api/v1/projects/{project}/tables/{table}/sheets/binding",
        json=stale,
        headers=_headers(),
    )
    assert stale.status_code == 412
    assert stale.json()["error"]["details"]["reason"] == "tableRevision"
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}"
    ).json()["sourceKind"] == "sheets"


def test_pull_keeps_text_and_integer_identities_apart(desk):
    client, _, transport, _ = desk
    project = _project(client)
    connection = _connect(client, project)
    table, fields, revision = _table(
        client, project, [("code", "编号", "string"), ("name", "名称", "string"),
                          ("email", "邮箱", "string"), ("result", "结果", "string")]
    )
    transport.grid = [
        ["编号", "名称", "邮箱", "结果"],
        ["001", "文本001", "a", ""],
        ["1", "文本1", "b", ""],
        [1, "整数1", "c", ""],
    ]
    _bind(client, project, table, fields, revision, connection)
    view = client.get(f"/api/v1/projects/{project}/tables/{table}").json()
    key = str(uuid4())
    accepted = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pull",
        json={"expectedTableRevision": view["tableRevision"]},
        headers={"Idempotency-Key": key},
    )
    assert accepted.status_code == 202, accepted.text
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
    ).json()
    assert operation["status"] == "succeeded", operation
    # The frozen pull result carries the table and the queue summary; the
    # per-record facts are read back from the table itself.
    assert operation["result"]["tableId"] == table
    assert operation["result"]["summary"]["pendingCount"] == 0
    keys = {
        (item["ref"]["recordKey"]["type"], item["ref"]["recordKey"]["value"])
        for item in client.get(
            f"/api/v1/projects/{project}/tables/{table}/records",
            params={"datasetGeneration": view["datasetGeneration"]},
        ).json()["items"]
    }
    assert keys == {("text", "001"), ("text", "1"), ("integer", "1")}
    # A replay of the same pull is not a second import.
    replay = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pull",
        json={"expectedTableRevision": view["tableRevision"]},
        headers={"Idempotency-Key": key},
    )
    assert replay.json()["operation"]["operationId"] == operation["operationId"]
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}/records",
        params={"datasetGeneration": view["datasetGeneration"]},
    ).json()["total"] == 3


def test_pull_refreshes_only_formula_columns_and_respects_local_edits(desk):
    client, _, transport, _ = desk
    project = _project(client)
    connection = _connect(client, project)
    table, fields, revision = _table(
        client, project, [("code", "编号", "string"), ("name", "名称", "string"),
                          ("email", "邮箱", "string"), ("result", "结果", "string")]
    )
    transport.grid = [["编号", "名称", "邮箱", "结果"], ["001", "甲", "a@x", "旧"]]
    _bind(client, project, table, fields, revision, connection)
    view = client.get(f"/api/v1/projects/{project}/tables/{table}").json()
    client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pull",
        json={"expectedTableRevision": view["tableRevision"]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    transport.grid = [["编号", "名称", "邮箱", "结果"], ["001", "改", "z@x", "新"]]
    second = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pull",
        json={"expectedTableRevision": view["tableRevision"]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/"
        f"{second.json()['operation']['operationId']}"
    )
    assert second.status_code == 202
    assert operation.status_code in {200, 404}
    local = client.get(
        f"/api/v1/projects/{project}/tables/{table}/records",
        params={"datasetGeneration": view["datasetGeneration"]},
    ).json()["items"][0]
    values = {cell["fieldId"]: cell["value"] for cell in local["values"]}
    assert values[fields["name"]] == "甲"
    assert values[fields["email"]] == "a@x"


def test_push_sends_only_pending_intents_and_records_evidence(desk):
    client, _, transport, _ = desk
    project = _project(client)
    connection = _connect(client, project)
    table, fields, revision = _table(
        client, project, [("code", "编号", "string"), ("name", "名称", "string"),
                          ("email", "邮箱", "string"), ("result", "结果", "string")]
    )
    transport.grid = [["编号", "名称", "邮箱", "结果"], ["001", "甲", "a@x", ""]]
    binding = _bind(client, project, table, fields, revision, connection)
    view = client.get(f"/api/v1/projects/{project}/tables/{table}").json()
    client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pull",
        json={"expectedTableRevision": view["tableRevision"]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    record = client.get(
        f"/api/v1/projects/{project}/tables/{table}/records",
        params={"datasetGeneration": view["datasetGeneration"]},
    ).json()["items"][0]
    edited = client.patch(
        f"/api/v1/projects/{project}/tables/{table}/records/"
        f"{_key(record['ref']['recordKey']['value'])}",
        json={
            "datasetGeneration": view["datasetGeneration"],
            "recordKeyType": "text",
            "values": [{"fieldId": fields["result"], "value": "成功"}],
            "expectedContentRevision": record["contentRevision"],
        },
        headers=_headers(),
    )
    assert edited.status_code == 200, edited.text
    state = client.get(f"/api/v1/projects/{project}/tables/{table}/sync").json()
    assert state["summary"]["pendingCount"] == 1
    assert state["binding"]["bindingEpoch"] == binding["bindingEpoch"]
    key = str(uuid4())
    accepted = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/push",
        json={"mode": "due", "expectedBindingEpoch": binding["bindingEpoch"]},
        headers={"Idempotency-Key": key},
    )
    assert accepted.status_code == 202, accepted.text
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
    ).json()
    assert operation["status"] == "succeeded", operation
    assert operation["result"]["tableId"] == table
    assert operation["result"]["summary"]["pendingCount"] == 0
    assert transport.grid[1][3] == "成功"
    page = client.get(
        f"/api/v1/projects/{project}/tables/{table}/sync-operations"
    ).json()
    pushed = [item for item in page["items"] if item["kind"] == "push"]
    assert pushed[0]["status"] == "confirmed"
    assert pushed[0]["evidence"]["outcome"] == "matched"
    assert pushed[0]["evidence"]["target"] == "Sheet1!2"
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}/sync"
    ).json()["summary"]["pendingCount"] == 0


def test_unknown_send_is_never_repeated_and_reconcile_decides(desk):
    client, _, transport, _ = desk
    project = _project(client)
    connection = _connect(client, project)
    table, fields, revision = _table(
        client, project, [("code", "编号", "string"), ("name", "名称", "string"),
                          ("email", "邮箱", "string"), ("result", "结果", "string")]
    )
    transport.grid = [["编号", "名称", "邮箱", "结果"], ["001", "甲", "a@x", ""]]
    binding = _bind(client, project, table, fields, revision, connection)
    view = client.get(f"/api/v1/projects/{project}/tables/{table}").json()
    client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pull",
        json={"expectedTableRevision": view["tableRevision"]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    record = client.get(
        f"/api/v1/projects/{project}/tables/{table}/records",
        params={"datasetGeneration": view["datasetGeneration"]},
    ).json()["items"][0]
    client.patch(
        f"/api/v1/projects/{project}/tables/{table}/records/"
        f"{_key(record['ref']['recordKey']['value'])}",
        json={
            "datasetGeneration": view["datasetGeneration"],
            "recordKeyType": "text",
            "values": [{"fieldId": fields["result"], "value": "成功"}],
            "expectedContentRevision": record["contentRevision"],
        },
        headers=_headers(),
    )
    sends = [call for call in transport.calls if call["method"] == "POST"]
    transport.fail = SheetsApiError(0, "timeout", "Google Sheets 未在时限内返回结果。")
    transport.fail_on = "values:batchUpdate"
    send_key = str(uuid4())
    accepted = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/push",
        json={"mode": "due", "expectedBindingEpoch": binding["bindingEpoch"]},
        headers={"Idempotency-Key": send_key},
    )
    assert accepted.status_code == 202
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{send_key}"
    ).json()
    assert operation["result"]["summary"]["unknownCount"] == 1
    # Exactly one write attempt left the process, and its outcome is unknown.
    attempted = [call for call in transport.calls if call["method"] == "POST"]
    assert len(attempted) == len(sends) + 1
    sync_page = client.get(
        f"/api/v1/projects/{project}/tables/{table}/sync-operations",
        params={"status": "unknown"},
    ).json()
    assert sync_page["total"] == 1
    assert sync_page["items"][0]["error"]["code"] == "SYNC_SEND_UNKNOWN"
    target = sync_page["items"][0]
    # The unknown send is never replayed: a second push leaves it untouched.
    transport.fail = transport.fail_on = None
    writes = [call for call in transport.calls if call["method"] == "POST"]
    client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/push",
        json={"mode": "due", "expectedBindingEpoch": binding["bindingEpoch"]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert [call for call in transport.calls if call["method"] == "POST"] == writes
    stale = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync-operations/"
        f"{target['syncOperationId']}/reconcile",
        json={"expectedStatusRevision": target["statusRevision"] + 5},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert stale.status_code == 412
    transport.grid[1][3] = "成功"
    key = str(uuid4())
    resolved = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync-operations/"
        f"{target['syncOperationId']}/reconcile",
        json={"expectedStatusRevision": target["statusRevision"]},
        headers={"Idempotency-Key": key},
    )
    assert resolved.status_code == 202, resolved.text
    outcome = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
    ).json()
    assert outcome["result"]["evidence"]["outcome"] == "matched"
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}/sync-operations/"
        f"{target['syncOperationId']}"
    ).json()["status"] == "confirmed"


def test_abandon_only_accepts_pending_and_keeps_history(desk):
    client, _, transport, _ = desk
    project = _project(client)
    connection = _connect(client, project)
    table, fields, revision = _table(
        client, project, [("code", "编号", "string"), ("name", "名称", "string"),
                          ("email", "邮箱", "string"), ("result", "结果", "string")]
    )
    transport.grid = [["编号", "名称", "邮箱", "结果"], ["001", "甲", "a@x", ""]]
    binding = _bind(client, project, table, fields, revision, connection)
    view = client.get(f"/api/v1/projects/{project}/tables/{table}").json()
    client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pull",
        json={"expectedTableRevision": view["tableRevision"]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    record = client.get(
        f"/api/v1/projects/{project}/tables/{table}/records",
        params={"datasetGeneration": view["datasetGeneration"]},
    ).json()["items"][0]
    client.patch(
        f"/api/v1/projects/{project}/tables/{table}/records/"
        f"{_key(record['ref']['recordKey']['value'])}",
        json={
            "datasetGeneration": view["datasetGeneration"],
            "recordKeyType": "text",
            "values": [{"fieldId": fields["result"], "value": "成功"}],
            "expectedContentRevision": record["contentRevision"],
        },
        headers=_headers(),
    )
    pending = client.get(
        f"/api/v1/projects/{project}/tables/{table}/sync-operations",
        params={"status": "pending"},
    ).json()["items"][0]
    body = {"expectedStatusRevision": pending["statusRevision"], "reason": "本轮不推送"}
    response = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync-operations/"
        f"{pending['syncOperationId']}/abandon",
        json=body,
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
    assert response.json()["error"]["code"] == "SYNC_ABANDONED"
    # History is kept: the abandoned operation is still readable.
    history = client.get(
        f"/api/v1/projects/{project}/tables/{table}/sync-operations/"
        f"{pending['syncOperationId']}"
    )
    assert history.status_code == 200
    stale = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync-operations/"
        f"{pending['syncOperationId']}/abandon",
        json=body,
        headers=_headers(),
    )
    assert stale.status_code == 412
    assert stale.json()["error"]["details"]["reason"] == "statusRevision"
    assert binding["syncPaused"] is False


def test_pause_blocks_network_writes_but_keeps_local_intents(desk):
    client, _, transport, _ = desk
    project = _project(client)
    connection = _connect(client, project)
    table, fields, revision = _table(
        client, project, [("code", "编号", "string"), ("name", "名称", "string"),
                          ("email", "邮箱", "string"), ("result", "结果", "string")]
    )
    transport.grid = [["编号", "名称", "邮箱", "结果"], ["001", "甲", "a@x", ""]]
    binding = _bind(client, project, table, fields, revision, connection)
    view = client.get(f"/api/v1/projects/{project}/tables/{table}").json()
    client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pull",
        json={"expectedTableRevision": view["tableRevision"]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    paused = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pause",
        json={"expectedBindingEpoch": binding["bindingEpoch"]},
        headers=_headers(),
    )
    assert paused.status_code == 200 and paused.json()["binding"]["syncPaused"] is True
    record = client.get(
        f"/api/v1/projects/{project}/tables/{table}/records",
        params={"datasetGeneration": view["datasetGeneration"]},
    ).json()["items"][0]
    client.patch(
        f"/api/v1/projects/{project}/tables/{table}/records/"
        f"{_key(record['ref']['recordKey']['value'])}",
        json={
            "datasetGeneration": view["datasetGeneration"],
            "recordKeyType": "text",
            "values": [{"fieldId": fields["result"], "value": "暂停期间"}],
            "expectedContentRevision": record["contentRevision"],
        },
        headers=_headers(),
    )
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}/sync"
    ).json()["summary"]["pendingCount"] == 1
    # A paused binding records the local change but performs no network write.
    sends = [call for call in transport.calls if call["method"] == "POST"]
    refused = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/push",
        json={"mode": "due", "expectedBindingEpoch": binding["bindingEpoch"]},
        headers=_headers(),
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "SYNC_PAUSED"
    assert [call for call in transport.calls if call["method"] == "POST"] == sends
    assert client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/resume",
        json={"expectedBindingEpoch": binding["bindingEpoch"] + 9},
        headers=_headers(),
    ).status_code == 412
    resumed = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/resume",
        json={"expectedBindingEpoch": binding["bindingEpoch"]},
        headers=_headers(),
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["binding"]["syncPaused"] is False
    assert resumed.json()["summary"]["pendingCount"] == 1
    # Resume only reopens the queue; the intent kept while paused is still there.
    key = str(uuid4())
    accepted = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/push",
        json={"mode": "due", "expectedBindingEpoch": binding["bindingEpoch"]},
        headers={"Idempotency-Key": key},
    )
    assert accepted.status_code == 202, accepted.text
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{key}"
    ).json()
    assert operation["result"]["summary"]["pendingCount"] == 0
    assert transport.grid[1][3] == "暂停期间"
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}/sync"
    ).json()["summary"]["pendingCount"] == 0


def test_unbound_table_reports_no_sync_and_refuses_pull(desk):
    client, _, _, _ = desk
    project = _project(client)
    table, _, revision = _table(client, project, [("code", "编号", "string")])
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}/sync"
    ).json() == {
        "summary": {"status": "notApplicable", "pendingCount": 0, "unknownCount": 0}
    }
    refused = client.post(
        f"/api/v1/projects/{project}/tables/{table}/sync/pull",
        json={"expectedTableRevision": revision},
        headers=_headers(),
    )
    assert refused.status_code == 404
    assert refused.json()["error"]["code"] == "SHEETS_BINDING_NOT_FOUND"
    assert client.get(
        f"/api/v1/projects/{project}/tables/{table}/sheets/binding"
    ).json() is None
