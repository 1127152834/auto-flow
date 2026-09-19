"""Record identity across the Sheets boundary keeps project, generation and type."""

from tests.fixtures.sheets import FakeSheetsTransport, new_key, open_sheets_table

GRID = {
    "数据": [
        ["编号", "标题"],
        ["001", "前导零"],
        ["1", "文本一"],
        [1, "整数一"],
        ["", "空身份"],
    ]
}
COLUMNS = [("code", "编号", "string"), ("title", "标题", "string")]


def pull(sheets):
    response = sheets.client.post(
        sheets.url("/sync/pull"),
        json={"expectedTableRevision": sheets.table_revision()},
        headers=new_key(),
    )
    assert response.status_code == 202, response.text
    return response.json()["operation"]


def keyed(sheets) -> dict[tuple[str, str], dict]:
    found = {}
    for record in sheets.records():
        key = record["ref"]["recordKey"]
        found[(key["type"], key["value"])] = {
            entry["fieldId"]: entry["value"] for entry in record["values"]
        }
    return found


def test_text_and_integer_keys_stay_distinct(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        imported = pull(sheets)
        # The frozen pull result names the table and the queue summary; the
        # per-record facts are read back from the table itself.
        assert imported["result"]["tableId"] == sheets.table
        assert imported["result"]["summary"]["unknownCount"] == 0
        records = keyed(sheets)
        assert set(records) == {("text", "001"), ("text", "1"), ("integer", "1")}
        assert records[("text", "001")][sheets.field_id("title")] == "前导零"
        assert records[("text", "1")][sheets.field_id("title")] == "文本一"
        assert records[("integer", "1")][sheets.field_id("title")] == "整数一"


def test_second_pull_is_idempotent_and_blank_identity_is_skipped(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        first = len(sheets.records())
        again = pull(sheets)["result"]
        assert again["tableId"] == sheets.table
        assert again["summary"]["pendingCount"] == 0
        assert len(sheets.records()) == first == 3


def test_pulled_records_start_without_status_or_links(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        generation = sheets.dataset_generation()
        for record in sheets.records():
            assert record["ref"]["datasetGeneration"] == generation
            assert record["statusId"] is None
            assert record["currentEnvironmentId"] is None
            assert record["recordSlots"] == []


def test_identity_column_must_map_to_a_text_field(tmp_path):
    from fastapi.testclient import TestClient

    from tests.fixtures.sheets import (
        RENDERER_TOKEN,
        connect,
        new_field,
        new_project,
        new_table,
        sheets_app,
    )

    transport = FakeSheetsTransport({"数据": [["编号", "标题"], ["1", "x"]]})
    app = sheets_app(tmp_path, transport)
    with TestClient(app, headers={"x-autoflow-token": RENDERER_TOKEN}) as client:
        project = new_project(client)
        connection = connect(client, project, new_key())["result"]
        table = new_table(client, project)
        number = new_field(
            client,
            project,
            table["tableId"],
            "code",
            "编号",
            type="number",
            expectedTableRevision=1,
        )
        response = client.put(
            f"/api/v1/projects/{project}/tables/{table['tableId']}/sheets/binding",
            json={
                "connectionId": connection["connectionId"],
                "spreadsheetId": transport.spreadsheet_id,
                "sheetId": 1000,
                "identityStrategy": {"kind": "column", "columnId": "A"},
                "mapping": [
                    {
                        "fieldId": number["ref"]["fieldId"],
                        "columnId": "A",
                        "direction": "both",
                        "formula": False,
                    }
                ],
                "impactRevision": 1,
                "expectedTableRevision": 2,
            },
            headers=new_key(),
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "SHEETS_IDENTITY_NOT_TEXT"
