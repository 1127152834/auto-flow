"""Pull and push keep local values authoritative and never guess an outcome."""

import base64

import pytest
from sqlalchemy import select

from autoflow.infrastructure.database.project_data_models import DataFieldRow
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
    class TrimEmptyRead(FakeSheetsTransport):
        def _read(self, text, render):
            rows = super()._read(text, render)
            return [] if rows == [['']] else rows  # Google omits trailing empty cells.
    transport = TrimEmptyRead(GRID)
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


@pytest.mark.parametrize("winner", ["send", "abandon"])
def test_abandon_and_send_compete_for_the_same_revision(tmp_path, monkeypatch, winner):
    from autoflow.infrastructure.database.project_sync import SqlAlchemyProjectSync
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path / winner, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], 'local-owned')
        pending, = sync_operations(sheets, 'pending')
        def abandon():
            return sheets.client.post(sheets.url(f"/sync-operations/{pending['syncOperationId']}/abandon"),
                headers=new_key(), json={'expectedStatusRevision': pending['statusRevision'], 'reason': 'keep local'})
        original = SqlAlchemyProjectSync.transition
        competing = []
        def transition(repository, operation_id, **kwargs):
            intercept = 'failed' if winner == 'send' else 'sending'
            if operation_id == pending['syncOperationId'] and kwargs['status'] == intercept and not competing:
                competing.append(True)
                response = push(sheets) if winner == 'send' else abandon()
                assert response.status_code in {200, 202}, response.text
            return original(repository, operation_id, **kwargs)
        with monkeypatch.context() as scoped:
            scoped.setattr(SqlAlchemyProjectSync, 'transition', transition)
            response = abandon() if winner == 'send' else push(sheets)
        assert response.status_code == (412 if winner == 'send' else 202), response.text
        operation, = sync_operations(sheets)
        assert operation['status'] == ('confirmed' if winner == 'send' else 'failed')
        assert transport.grid('数据')[1][1] == ('local-owned' if winner == 'send' else '第一行')
        if winner == 'abandon':
            assert operation['error']['code'] == 'SYNC_ABANDONED'
            writes = transport.changes()
            pull(sheets)
            assert sheets.records()[0]['contentRevision'] == 2
            assert {cell['fieldId']: cell['value'] for cell in sheets.records()[0]['values']}[sheets.field_id('title')] == 'local-owned'
            assert transport.changes() == writes


@pytest.mark.parametrize("formula", [False, True])
def test_pull_never_revives_a_locally_deleted_remote_record(tmp_path, formula):
    transport = FakeSheetsTransport(
        GRID, formulas={"数据": [["编号", "标题"], ["A-1", "=1+1"]]} if formula else None
    )
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        record = sheets.records()[0]
        preview = sheets.client.post(
            f"/api/v1/projects/{sheets.project}/mutation-impact",
            json={"action": "deleteRecord", "target": {"type": "record", "recordRef": record["ref"]}},
        )
        assert preview.status_code == 200, preview.text
        deleted = sheets.client.request(
            "DELETE", sheets.url("/records/QS0x"), headers=new_key(),
            json={
                "datasetGeneration": record["ref"]["datasetGeneration"],
                "recordKeyType": "text",
                "expectedContentRevision": record["contentRevision"],
                "expectedStatusRevision": record["statusRevision"],
                "expectedLinkRevision": record["linkRevision"],
                "impactRevision": preview.json()["impactRevision"],
            },
        )
        assert deleted.status_code == 202, deleted.text
        assert sheets.records() == []
        writes = transport.changes()
        transport.grids[1000].insert(1, ["B-2", "新记录"])
        if formula:
            transport.formulas[1000] = [["编号", "标题"], ["B-2", "=3+3"], ["A-1", "=2+2"]]
        pull(sheets)
        pull(sheets)
        assert [item["ref"]["recordKey"]["value"] for item in sheets.records()] == ["B-2"]
        assert transport.grid("数据")[2] == ["A-1", "第一行"]
        assert transport.changes() == writes
        assert sync_operations(sheets) == []


@pytest.mark.parametrize("outcome", ["confirmed", "failed", "unknown"])
@pytest.mark.parametrize("assigned", [False, True])
def test_sync_outcomes_preserve_explicit_business_status(tmp_path, outcome, assigned):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        record = sheets.records()[0]
        status_id = None
        if assigned:
            status = sheets.client.post(
                sheets.url("/statuses"), headers=new_key(),
                json={"name": "可用", "color": "#abcdef", "order": 0,
                      "expectedTableRevision": sheets.table_revision()},
            )
            assert status.status_code == 201, status.text
            status_id = status.json()["statusId"]
        changed = sheets.client.put(
            sheets.url("/records/QS0x/status"), headers=new_key(),
            json={"datasetGeneration": record["ref"]["datasetGeneration"],
                  "recordKeyType": "text", "statusId": status_id,
                  "expectedFromStatusId": None, "expectedStatusRevision": record["statusRevision"]},
        )
        assert changed.status_code == 200, changed.text
        status_revision = changed.json()["statusRevision"]
        edit_title(sheets, changed.json(), "本地修改")
        assert sync_operations(sheets)[0]["status"] == "pending"
        if outcome != "confirmed":
            transport.fail_writes.append(SheetsApiError(
                0 if outcome == "unknown" else 403,
                "timeout" if outcome == "unknown" else "forbidden", "受控网络失败",
            ))
        accepted = push(sheets)
        assert accepted.status_code == 202, accepted.text
        assert sync_operations(sheets)[0]["status"] == outcome
        transport.grids[1000].insert(1, ["B-2", "插在前面的新行"])
        pull(sheets)
        current = {item["ref"]["recordKey"]["value"]: item for item in sheets.records()}
        assert set(current) == {"A-1", "B-2"}
        assert current["B-2"]["statusId"] is None
        assert current["B-2"]["statusRevision"] == 1
        after = current["A-1"]
        assert after["ref"] == record["ref"]
        assert after["statusId"] == status_id
        assert after["statusRevision"] == status_revision
        assert after["contentRevision"] == 2
        assert {v["fieldId"]: v["value"] for v in after["values"]}[sheets.field_id("title")] == "本地修改"


def test_partial_verification_read_loss_preserves_original_commands(tmp_path):
    class LoseSecondVerification(FakeSheetsTransport):
        verifying = False
        reads = 0

        def send(self, method, url, **kwargs):
            if self.verifying and method == "GET":
                self.reads += 1
                if self.reads == 2:
                    raise SheetsApiError(0, "timeout", "核验读取响应丢失")
            result = super().send(method, url, **kwargs)
            if url.endswith("/values:batchUpdate"):
                self.verifying = True
            return result

    transport = LoseSecondVerification({"数据": [["编号", "标题"], ["A-1", "a"], ["B-2", "b"]]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        for record in sheets.records():
            edit_title(sheets, record, record["ref"]["recordKey"]["value"] + "-v2")
        identity = new_key()
        body = {"mode": "due", "expectedBindingEpoch": sheets.binding["bindingEpoch"]}
        response = sheets.client.post(sheets.url("/sync/push"), headers=identity, json=body)
        assert response.status_code == 202, response.text
        assert len(sync_operations(sheets, "confirmed")) == 1
        unknown, = sync_operations(sheets, "unknown")
        assert unknown["record"]["recordKey"]["value"] == "B-2"
        writes = transport.changes()
        assert transport.grid("数据")[1:] == [["A-1", "A-1-v2"], ["B-2", "B-2-v2"]]
        replay = sheets.client.post(sheets.url("/sync/push"), headers=identity, json=body)
        assert replay.status_code == 202 and replay.json() == response.json()
        assert transport.changes() == writes
        current = next(r for r in sheets.records() if r["ref"]["recordKey"]["value"] == "B-2")
        edit_title(sheets, current, "B-2-v3")
        recovered = sheets.client.post(
            sheets.url(f"/sync-operations/{unknown['syncOperationId']}/reconcile"),
            headers=new_key(), json={"expectedStatusRevision": unknown["statusRevision"]},
        )
        assert recovered.status_code == 202, recovered.text
        assert recovered.json()["operation"]["result"]["targetContentRevision"] == 2
        assert len(sync_operations(sheets, "confirmed")) == 2
        pending, = sync_operations(sheets, "pending")
        assert pending["targetContentRevision"] == 3
        assert transport.changes() == writes


@pytest.mark.parametrize("fail_cell_read", [False, True])
def test_failed_reconciliation_settles_read_command_and_preserves_unknown_write(tmp_path, fail_cell_read):
    class LoseReconcileRead(FakeSheetsTransport):
        fail_read = False

        def send(self, method, url, **kwargs):
            if self.fail_read and method == "GET" and (not fail_cell_read or url.endswith("$B$2")):
                self.fail_read = False
                raise SheetsApiError(0, "timeout", "原操作核验读取失败")
            return super().send(method, url, **kwargs)

    transport = LoseReconcileRead(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], "原写入")
        transport.fail_writes.append(SheetsApiError(0, "timeout", "发送响应丢失"))
        assert push(sheets).status_code == 202
        unknown, = sync_operations(sheets, "unknown")
        transport.grids[1000][1][1] = "原写入"  # The remote write may have succeeded.
        writes = transport.changes()
        path = sheets.url(f"/sync-operations/{unknown['syncOperationId']}/reconcile")
        body = {"expectedStatusRevision": unknown["statusRevision"]}
        identity = new_key()
        transport.fail_read = True
        response = sheets.client.post(path, headers=identity, json=body)
        assert response.status_code == 502, response.text
        operation = sheets.client.get(
            f"/api/v1/projects/{sheets.project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
        )
        assert operation.status_code == 200, operation.text
        assert operation.json()["status"] == "failed"
        assert operation.json()["error"]["code"] == "SHEETS_API_FAILED"
        assert sync_operations(sheets, "unknown") == [unknown]
        calls = len(transport.calls)
        replay = sheets.client.post(path, headers=identity, json=body)
        assert replay.status_code == 202 and replay.json()["operation"] == operation.json()
        assert len(transport.calls) == calls
        recovered = sheets.client.post(path, headers=new_key(), json=body)
        assert recovered.status_code == 202, recovered.text
        assert recovered.json()["operation"]["result"]["status"] == "confirmed"
        assert transport.changes() == writes


@pytest.mark.parametrize("action", ["pull", "push"])
def test_access_failure_after_accept_settles_the_sync_command(tmp_path, monkeypatch, action):
    from autoflow.domain.projects.models import ProjectError

    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        record = sheets.records()[0]
        edit_title(sheets, record, "仍在本地")
        pending = sync_operations(sheets, "pending")
        identity = new_key()
        body = ({"expectedTableRevision": sheets.table_revision()} if action == "pull" else
                {"mode": "due", "expectedBindingEpoch": sheets.binding["bindingEpoch"]})
        calls = len(transport.calls)

        def unavailable(*_args):
            raise ProjectError("CREDENTIAL_NOT_AVAILABLE", "受控凭据不可用", 422)

        monkeypatch.setattr(sheets.client.app.state.sheets_sync._access, "client", unavailable)
        response = sheets.client.post(sheets.url(f"/sync/{action}"), headers=identity, json=body)
        assert response.status_code == 422, response.text
        operation = sheets.client.get(
            f"/api/v1/projects/{sheets.project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
        ).json()
        assert operation["status"] == "failed"
        assert operation["error"]["code"] == "CREDENTIAL_NOT_AVAILABLE"
        assert sync_operations(sheets, "pending") == pending
        assert len(transport.calls) == calls


def test_confirmed_push_block_survives_next_failure_and_later_edit(tmp_path, monkeypatch):
    from autoflow.application.project_sync import outbound

    monkeypatch.setattr(outbound, "MAX_PUSH_RECORDS", 1)
    transport = FakeSheetsTransport({"数据": [["编号", "标题"], ["A-1", "a"], ["B-2", "b"]]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        for record in sheets.records():
            edit_title(sheets, record, record["ref"]["recordKey"]["value"] + "-v2")
        assert push(sheets).status_code == 202
        confirmed, = sync_operations(sheets, "confirmed")
        assert confirmed["record"]["recordKey"]["value"] == "A-1"
        assert len(sync_operations(sheets, "pending")) == 1
        transport.fail_writes.append(SheetsApiError(403, "forbidden", "第二块发送失败"))
        assert push(sheets).status_code == 202
        failed, = sync_operations(sheets, "failed")
        assert failed["record"]["recordKey"]["value"] == "B-2"
        assert sync_operations(sheets, "confirmed") == [confirmed]
        record = next(r for r in sheets.records() if r["ref"]["recordKey"]["value"] == "B-2")
        assert record["contentRevision"] == 2
        edit_title(sheets, record, "B-2-v3")
        assert push(sheets).status_code == 202
        assert sync_operations(sheets, "failed") == [failed]
        assert len(sync_operations(sheets, "confirmed")) == 2
        assert sync_operations(sheets, "pending") == []
        assert transport.grid("数据")[1:] == [["A-1", "A-1-v2"], ["B-2", "B-2-v3"]]
        assert transport.changes() == 3  # Two commits and the explicitly failed request.


@pytest.mark.parametrize('scope', ['foreign-project', 'structural-operation'])
def test_generic_abandon_is_scoped_to_owned_content_intents(tmp_path, scope):
    from uuid import uuid4

    from autoflow.infrastructure.database.project_sync_models import SyncOperationRow

    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        edit_title(sheets, sheets.records()[0], 'local-owned')
        pending, = sync_operations(sheets, 'pending')
        url = sheets.url(f"/sync-operations/{pending['syncOperationId']}/abandon")
        if scope == 'foreign-project':
            url = url.replace(sheets.project, str(uuid4()))
        else:
            with sheets.client.app.state.session_factory() as session:
                row = session.get(SyncOperationRow, pending['syncOperationId'])
                row.kind = 'column'
                session.commit()
        response = sheets.client.post(url, headers=new_key(), json={
            'expectedStatusRevision': pending['statusRevision'], 'reason': 'cancel',
        })
        assert response.status_code == (404 if scope == 'foreign-project' else 409), response.text
        with sheets.client.app.state.session_factory() as session:
            row = session.get(SyncOperationRow, pending['syncOperationId'])
            assert row.status == 'pending' and row.status_revision == pending['statusRevision']
        assert transport.changes() == 0


@pytest.mark.parametrize('last_writer', ['P', 'Q'])
def test_overlapping_project_writes_keep_historical_confirmation_and_local_values(tmp_path, last_writer):
    from tests.integration.test_project_sheets_claims import shared_tables
    from tests.integration.test_project_sheets_observations import observations

    with shared_tables(tmp_path) as (first, second):
        bounds = {'P':first, 'Q':second}
        local = {name:edit_title(bound, bound.records()[0], name+'-value') for name, bound in bounds.items()}
        earlier = 'Q' if last_writer == 'P' else 'P'
        assert push(bounds[earlier]).status_code == 202
        confirmed, = sync_operations(bounds[earlier], 'confirmed')
        assert confirmed['evidence']['outcome'] == 'matched'
        assert first.transport.grid('数据')[1][1] == earlier+'-value'
        assert push(bounds[last_writer]).status_code == 202
        last, = sync_operations(bounds[last_writer], 'confirmed')
        assert last['evidence']['outcome'] == 'matched'
        assert last['syncOperationId'] != confirmed['syncOperationId']
        assert first.transport.grid('数据')[1][1] == last_writer+'-value'
        writes = first.transport.changes()
        for name, bound in bounds.items():
            pull(bound)
            assert bound.records()[0] == local[name]
            observed = next(item for item in observations(bound, local[name]).json()['items'] if item['fieldId'] == bound.field_id('title'))
            assert observed['remoteValue'] == last_writer+'-value'
            assert observed['localValue'] == name+'-value'
            assert observed['differs'] is (name != last_writer)
        assert sync_operations(bounds[earlier], 'confirmed') == [confirmed]
        assert sync_operations(bounds[last_writer], 'confirmed') == [last]
        assert first.transport.changes() == writes == 2


def test_pull_preserves_safe_business_format_error_for_status_and_diagnosis(tmp_path):
    transport = FakeSheetsTransport({'数据': [['编号', '标题', '金额'], ['A-1', 'valid', 'not-a-number']]})
    with open_sheets_table(tmp_path, transport, [*COLUMNS, ('amount', '金额', 'number')]) as sheets:
        operation = pull(sheets)
        assert operation['status'] == 'succeeded'
        record = sheets.records()[0]
        assert next(cell['value'] for cell in record['values'] if cell['fieldId'] == sheets.field_id('amount')) == 'not-a-number'
        issue = next(item for item in record['validationIssues'] if item['fieldId'] == sheets.field_id('amount'))
        assert issue['rule'] == 'type' and issue['code'] == 'INVALID_PROJECT_DATA'
        assert record['contentRevision'] == record['statusRevision'] == record['linkRevision'] == 1
        assert sync_operations(sheets) == [] and transport.changes() == 0


def test_pull_keeps_missing_required_source_cell_absent_with_diagnosis(tmp_path):
    transport = FakeSheetsTransport({'数据': [['编号', '标题', '金额'], ['A-1', 'valid', None]]})
    with open_sheets_table(tmp_path, transport, [*COLUMNS, ('amount', '金额', 'number')]) as sheets:
        with sheets.client.app.state.session_factory.begin() as session:
            field = session.scalars(select(DataFieldRow).where(
                DataFieldRow.id == sheets.field_id('amount'),
                DataFieldRow.dataset_generation == sheets.dataset_generation(),
            )).one()
            field.required = True
        operation = pull(sheets)
        assert operation['status'] == 'succeeded'
        record = sheets.records()[0]
        amount_id = sheets.field_id('amount')
        assert all(cell['fieldId'] != amount_id for cell in record['values'])
        issue = next(item for item in record['validationIssues'] if item['fieldId'] == amount_id)
        assert issue['rule'] == 'required' and issue['code'] == 'REQUIRED_FIELD_MISSING'


def test_pull_rejects_late_invalid_identity_without_partial_materialization(tmp_path):
    transport = FakeSheetsTransport({'数据': [['编号', '金额'], ['A-1', 1], ['BAD', 2]]})
    with open_sheets_table(
        tmp_path,
        transport,
        [('code', '编号', 'string'), ('amount', '金额', 'number')],
    ) as sheets:
        with sheets.client.app.state.session_factory.begin() as session:
            field = session.scalars(select(DataFieldRow).where(
                DataFieldRow.id == sheets.field_id('code'),
                DataFieldRow.dataset_generation == sheets.dataset_generation(),
            )).one()
            field.validation = {'pattern': '^[A-Z]-\\d+$'}
        response = sheets.client.post(
            sheets.url('/sync/pull'),
            json={'expectedTableRevision': sheets.table_revision()},
            headers=new_key(),
        )
        assert response.status_code == 422, response.text
        assert response.json()['error']['code'] == 'INVALID_PROJECT_DATA'
        assert sheets.records() == []


def test_source_read_time_survives_push_and_failed_pull_and_excludes_retired_binding(tmp_path):
    from autoflow.infrastructure.database.project_sync_models import SheetsBindingRow

    with open_sheets_table(tmp_path, FakeSheetsTransport(GRID), COLUMNS) as sheets:
        pull(sheets)
        source_time = sheets.client.get(sheets.url("/sync")).json()["summary"]["lastPulledAt"]
        edit_title(sheets, sheets.records()[0], "local edit")
        assert push(sheets).status_code == 202
        sheets.transport.fail_next = SheetsApiError(-1, "offline", "controlled source outage")
        failed = sheets.client.post(sheets.url("/sync/pull"), headers=new_key(), json={
            "expectedTableRevision": sheets.table_revision(),
        })
        assert failed.status_code == 502, failed.text
        summary = sheets.client.get(sheets.url("/sync")).json()["summary"]
        assert summary["lastPulledAt"] == source_time
        assert summary["lastConfirmedAt"] > source_time
        assert sheets.client.get(sheets.url("")).json()["syncSummary"]["lastPulledAt"] == source_time
        latest = sheets.client.get(sheets.url("/sync")).json()["latestPull"]
        assert (latest["kind"], latest["status"], latest["error"]["code"]) == ("pull", "failed", "SHEETS_API_FAILED")
        # Isolate the summary query's epoch boundary; public rebind has its own tests.
        with sheets.client.app.state.session_factory.begin() as session:
            session.get(SheetsBindingRow, sheets.table).binding_epoch += 1
        retired = sheets.client.get(sheets.url("/sync")).json()
        assert "lastPulledAt" not in retired["summary"] and "latestPull" not in retired
