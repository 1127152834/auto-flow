"""Pull and push keep local values authoritative and never guess an outcome."""

import base64

from autoflow.providers.data.google_sheets import SheetsApiError
from tests.fixtures.sheets import FakeSheetsTransport, new_key, open_sheets_table

GRID = {"数据": [["编号", "标题"], ["A-1", "第一行"]]}
COLUMNS = [("code", "编号", "string"), ("title", "标题", "string")]


def pull(sheets, revision=None):
    response = sheets.client.post(
        sheets.url("/sync/pull"),
        json={"expectedTableRevision": revision or sheets.table_revision()},
        headers=new_key(),
    )
    assert response.status_code == 202, response.text
    return response.json()["operation"]


def push(sheets, mode="due", epoch=None):
    response = sheets.client.post(
        sheets.url("/sync/push"),
        json={
            "mode": mode,
            "expectedBindingEpoch": epoch or sheets.binding["bindingEpoch"],
        },
        headers=new_key(),
    )
    return response


def edit_title(sheets, record, value):
    raw = record["ref"]["recordKey"]["value"]
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    response = sheets.client.patch(
        sheets.url(f"/records/{encoded}"),
        headers=new_key(),
        json={
            "datasetGeneration": record["ref"]["datasetGeneration"],
            "recordKeyType": record["ref"]["recordKey"]["type"],
            "expectedContentRevision": record["contentRevision"],
            "values": [{"fieldId": sheets.field_id("title"), "value": value}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def sync_operations(sheets, status=None):
    params = {"pageSize": 100}
    if status:
        params["status"] = status
    response = sheets.client.get(sheets.url("/sync-operations"), params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_local_edit_pushes_and_records_evidence(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        record = sheets.records()[0]
        edited = edit_title(sheets, record, "本地改过")
        assert edited["contentRevision"] == 2

        before = transport.changes()
        accepted = push(sheets)
        assert accepted.status_code == 202, accepted.text
        result = accepted.json()["operation"]["result"]
        # The frozen push result names the table and the queue summary; the
        # per-record outcome is read back from its own sync operation.
        assert result["tableId"] == sheets.table
        assert result["summary"]["pendingCount"] == 0, result
        assert result["summary"]["unknownCount"] == 0, result
        assert transport.changes() == before + 1
        assert transport.grid("数据")[1][1] == "本地改过"

        stored = sync_operations(sheets, "confirmed")
        assert len(stored) == 1
        assert stored[0]["evidence"]["outcome"] == "matched"
        assert stored[0]["kind"] == "push"
        assert stored[0]["record"]["recordKey"] == record["ref"]["recordKey"]
        assert stored[0]["targetContentRevision"] == 2


def test_push_replays_the_original_operation_without_a_second_write(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], "只发一次")
        body = {
            "mode": "due",
            "expectedBindingEpoch": sheets.binding["bindingEpoch"],
        }
        identity = new_key()
        first = sheets.client.post(sheets.url("/sync/push"), json=body, headers=identity)
        assert first.status_code == 202
        writes = transport.changes()
        replay = sheets.client.post(sheets.url("/sync/push"), json=body, headers=identity)
        assert replay.status_code == 202
        assert replay.json() == first.json()
        assert transport.changes() == writes
        assert transport.grid("数据")[1][1] == "只发一次"


def test_timeout_stays_unknown_and_is_never_resent_blindly(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], "未确认")
        transport.fail_writes.append(SheetsApiError(0, "timeout", "Google Sheets 未在时限内返回结果。"))

        first = push(sheets)
        assert first.status_code == 202, first.text
        result = first.json()["operation"]["result"]
        assert result["summary"]["unknownCount"] == 1, result
        assert result["summary"]["pendingCount"] == 0, result
        assert transport.grid("数据")[1][1] == "第一行"

        unknown = sync_operations(sheets, "unknown")
        assert len(unknown) == 1
        revision = unknown[0]["statusRevision"]

        writes = transport.changes()
        again = push(sheets, mode="allPending").json()["operation"]["result"]
        assert again["summary"]["unknownCount"] == 1, again
        assert transport.changes() == writes, "an unknown send must not be repeated"
        assert transport.grid("数据")[1][1] == "第一行"

        reconciled = sheets.client.post(
            sheets.url(f"/sync-operations/{unknown[0]['syncOperationId']}/reconcile"),
            json={"expectedStatusRevision": revision},
            headers=new_key(),
        )
        assert reconciled.status_code == 202, reconciled.text
        assert (
            reconciled.json()["operation"]["result"]["evidence"]["outcome"]
            == "notMatched"
        )
        after = sync_operations(sheets)
        assert {item["status"] for item in after} == {"failed"}


def test_pull_refreshes_formula_values_only(tmp_path):
    transport = FakeSheetsTransport(
        {"数据": [["编号", "标题"], ["A-1", "第一行"]]},
        formulas={"数据": [["编号", "标题"], ["A-1", "=1+1"]]},
    )
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        # 标题 maps a column that carries a formula, so binding marks the field
        # read-only and the first pull stores the formula text itself.
        bound = sheets.client.get(sheets.url("/sheets/binding")).json()
        title = next(
            item
            for item in bound["mapping"]
            if item["fieldId"] == sheets.field_id("title")
        )
        assert title["formula"] is True and title["direction"] == "read"
        first = pull(sheets)["result"]
        assert first["tableId"] == sheets.table, first
        record = sheets.records()[0]
        assert {item["fieldId"]: item["value"] for item in record["values"]}[
            sheets.field_id("title")
        ] == "=1+1"

        transport.formulas[1000][1][1] = "=2+2"
        refreshed_run = pull(sheets)["result"]
        assert refreshed_run["tableId"] == sheets.table, refreshed_run
        refreshed = {item["fieldId"]: item["value"] for item in sheets.records()[0]["values"]}
        assert refreshed[sheets.field_id("title")] == "=2+2"
        assert refreshed[sheets.field_id("code")] == record["values"][0]["value"]

        # A local write to a formula column is refused instead of replacing it.
        refused = sheets.client.patch(
            sheets.url(
                f"/records/{base64.urlsafe_b64encode(b'A-1').decode().rstrip('=')}"
            ),
            headers=new_key(),
            json={
                "datasetGeneration": record["ref"]["datasetGeneration"],
                "recordKeyType": "text",
                "expectedContentRevision": sheets.records()[0]["contentRevision"],
                "values": [{"fieldId": sheets.field_id("title"), "value": "手改"}],
            },
        )
        assert refused.status_code == 422, refused.text
        assert sheets.records()[0]["values"][1]["value"] == "=2+2"


def test_pull_reports_a_stale_table_revision(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        response = sheets.client.post(
            sheets.url("/sync/pull"),
            json={"expectedTableRevision": 1},
            headers=new_key(),
        )
        assert response.status_code == 412, response.text
        assert response.json()["error"]["details"]["reason"] == "tableRevision"


def test_push_reports_a_stale_binding_epoch(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        response = push(sheets, epoch=99)
        assert response.status_code == 412, response.text
        assert response.json()["error"]["details"]["reason"] == "bindingEpoch"


def test_push_fails_when_the_remote_row_disappeared(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], "行没了")
        transport.grids[1000] = [["编号", "标题"], ["B-9", "换了一行"]]
        result = push(sheets).json()["operation"]["result"]
        assert result["summary"]["pendingCount"] == 0, result
        assert result["summary"]["unknownCount"] == 0, result
        failed = sync_operations(sheets, "failed")
        assert failed[0]["error"]["code"] == "SYNC_REMOTE_ROW_MISSING"
        assert transport.grid("数据")[1][1] == "换了一行"


def test_sync_state_and_pause_resume_are_readable(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        state = sheets.client.get(sheets.url("/sync")).json()
        assert state["summary"] == {
            "status": "idle",
            "pendingCount": 0,
            "unknownCount": 0,
        }
        epoch = sheets.binding["bindingEpoch"]
        paused = sheets.client.post(
            sheets.url("/sync/pause"),
            json={"expectedBindingEpoch": epoch},
            headers=new_key(),
        )
        assert paused.status_code == 200, paused.text
        assert paused.json()["binding"]["syncPaused"] is True

        sheets.client.post(
            sheets.url("/sync/resume"),
            json={"expectedBindingEpoch": epoch},
            headers=new_key(),
        )
        assert sheets.client.get(sheets.url("/sync")).json()["binding"]["syncPaused"] is False
