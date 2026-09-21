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


def test_remote_plain_value_change_preserves_local_content_and_revisions(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], 'local-owned')
        before = sheets.records()[0]
        transport.grid('数据')[1][1] = 'remote-edited'
        pull(sheets)
        after = sheets.records()[0]
        for field in ['ref', 'values', 'statusId', 'contentRevision', 'statusRevision']:
            assert after[field] == before[field], field
        assert transport.grid('数据')[1][1] == 'remote-edited'


def test_push_relocates_stable_identity_after_remote_sort_and_insert(tmp_path):
    transport = FakeSheetsTransport({'数据': [['编号', '标题'], ['A-1', 'first'], ['B-2', 'second']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        original = {row['ref']['recordKey']['value']: row for row in sheets.records()}
        edit_title(sheets, original['A-1'], 'local-A')
        edit_title(sheets, original['B-2'], 'local-B')
        transport.grid('数据')[1:] = [['X-0', 'untouched'], ['B-2', 'second'], ['A-1', 'first']]
        pull(sheets)
        assert {row['ref']['recordKey']['value'] for row in sheets.records()} == {'A-1', 'B-2', 'X-0'}
        response = push(sheets)
        assert response.status_code == 202, response.text
        assert response.json()['operation']['result']['summary']['unknownCount'] == 0
        assert transport.grid('数据')[1:] == [['X-0', 'untouched'], ['B-2', 'local-B'], ['A-1', 'local-A']]
        assert len(sync_operations(sheets, 'confirmed')) == 2


def test_two_projects_push_disjoint_fields_without_replacing_each_other(tmp_path):
    from tests.fixtures.sheets import (
        SheetsTable,
        binding_impact,
        connect,
        new_field,
        new_project,
        new_table,
    )
    columns = [*COLUMNS, ('note', '备注', 'string')]
    transport = FakeSheetsTransport({'数据': [['编号', '标题', '备注'], ['A-1', 'original', 'old-note']]})
    with open_sheets_table(tmp_path, transport, columns) as first:
        client = first.client
        project = new_project(client, 'Q')
        connection = connect(client, project, new_key())['result']['connectionId']
        table = new_table(client, project)['tableId']
        fields = {key: new_field(client, project, table, key, name, type=kind, expectedTableRevision=index + 1)
                  for index, (key, name, kind) in enumerate(columns)}
        body = {
            'connectionId': connection, 'spreadsheetId': transport.spreadsheet_id, 'sheetId': 1000,
            'identityStrategy': {'kind': 'column', 'columnId': 'A'},
            'mapping': [{'fieldId': fields[key]['ref']['fieldId'], 'columnId': chr(65 + i), 'direction': 'both', 'formula': False}
                        for i, (key, _, _) in enumerate(columns)],
            'expectedTableRevision': 4,
        }
        accepted = client.put(f'/api/v1/projects/{project}/tables/{table}/sheets/binding',
                              json=binding_impact(client, project, table, body), headers=new_key())
        assert accepted.status_code == 202, accepted.text
        second = SheetsTable(client, transport, project, table, connection, fields, accepted.json()['operation']['result'])
        pull(first)
        pull(second)
        edit_title(first, first.records()[0], 'P-title')
        record = second.records()[0]
        changed = client.patch(second.url('/records/QS0x'), headers=new_key(), json={
            'datasetGeneration': record['ref']['datasetGeneration'],
            'recordKeyType': record['ref']['recordKey']['type'],
            'expectedContentRevision': record['contentRevision'],
            'values': [{'fieldId': second.field_id('note'), 'value': 'Q-note'}],
        })
        assert changed.status_code == 200, changed.text
        assert push(first).status_code == 202
        assert push(second).status_code == 202
        assert transport.grid('数据')[1] == ['A-1', 'P-title', 'Q-note']
        assert len(sync_operations(first, 'confirmed')) == len(sync_operations(second, 'confirmed')) == 1
        assert first.records()[0]['contentRevision'] == second.records()[0]['contentRevision'] == 2


def test_unknown_send_reconciles_original_values_after_a_new_local_edit(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], 'version-2')
        transport.fail_writes.append(SheetsApiError(0, 'timeout', 'response lost'))
        assert push(sheets).status_code == 202
        original, = sync_operations(sheets, 'unknown')
        transport.grid('数据')[1][1] = 'version-2'  # Original send reached the server.
        edit_title(sheets, sheets.records()[0], 'version-3')
        writes = transport.changes()
        response = sheets.client.post(sheets.url(f"/sync-operations/{original['syncOperationId']}/reconcile"),
            headers=new_key(), json={'expectedStatusRevision': original['statusRevision']})
        assert response.status_code == 202, response.text
        assert response.json()['operation']['result']['evidence']['outcome'] == 'matched'
        confirmed, = sync_operations(sheets, 'confirmed')
        pending, = sync_operations(sheets, 'pending')
        assert confirmed['targetContentRevision'] == 2 and pending['targetContentRevision'] == 3
        assert transport.changes() == writes and transport.grid('数据')[1][1] == 'version-2'
        assert sheets.records()[0]['contentRevision'] == 3
        assert push(sheets).status_code == 202
        assert transport.grid('数据')[1][1] == 'version-3'
        assert len(sync_operations(sheets, 'confirmed')) == 2


def test_edit_during_send_keeps_new_revision_pending(tmp_path):
    class EditDuringSend(FakeSheetsTransport):
        edit = None
        def send(self, method, url, **kwargs):
            if url.endswith('/values:batchUpdate') and self.edit:
                edit, self.edit = self.edit, None
                edit()
            return super().send(method, url, **kwargs)
    transport = EditDuringSend(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], 'version-2')
        transport.edit = lambda: edit_title(sheets, sheets.records()[0], 'version-3')
        assert push(sheets).status_code == 202
        confirmed, = sync_operations(sheets, 'confirmed')
        pending, = sync_operations(sheets, 'pending')
        assert confirmed['targetContentRevision'] == 2 and pending['targetContentRevision'] == 3
        assert transport.grid('数据')[1][1] == 'version-2'
        assert push(sheets).status_code == 202
        assert transport.grid('数据')[1][1] == 'version-3'


def test_unsent_merge_preserves_field_mask_and_explicit_clear(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], 'temporary')
        before, = sync_operations(sheets, 'pending')
        edit_title(sheets, sheets.records()[0], None)
        after, = sync_operations(sheets, 'pending')
        assert after['syncOperationId'] == before['syncOperationId']
        assert after['statusRevision'] == before['statusRevision'] + 1
        assert after['targetContentRevision'] == 3
        assert push(sheets).status_code == 202
        assert transport.grid('数据')[1] == ['A-1', '']
        confirmed, = sync_operations(sheets, 'confirmed')
        assert confirmed['evidence']['fields'] == ['B']


def test_legacy_intent_without_field_snapshot_never_guesses_a_write(tmp_path):
    from autoflow.infrastructure.database.project_sync_models import SyncOperationRow
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], 'local')
        pending, = sync_operations(sheets, 'pending')
        with sheets.client.app.state.session_factory() as session:
            row = session.get(SyncOperationRow, pending['syncOperationId'])
            row.request = {key: value for key, value in row.request.items() if key != 'values'}
            session.commit()
        writes = transport.changes()
        assert push(sheets).status_code == 202
        failed, = sync_operations(sheets, 'failed')
        assert failed['error']['code'] == 'SYNC_SNAPSHOT_MISSING'
        assert transport.changes() == writes and transport.grid('数据')[1][1] == '第一行'
        with sheets.client.app.state.session_factory() as session:
            row = session.get(SyncOperationRow, pending['syncOperationId'])
            row.status = 'unknown'
            session.commit()
        response = sheets.client.post(sheets.url(f"/sync-operations/{pending['syncOperationId']}/reconcile"),
            headers=new_key(), json={'expectedStatusRevision': failed['statusRevision']})
        assert response.status_code == 409 and response.json()['error']['code'] == 'SYNC_SNAPSHOT_MISSING'
        assert transport.changes() == writes
