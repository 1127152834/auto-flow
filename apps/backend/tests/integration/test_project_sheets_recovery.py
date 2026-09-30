"""What the sync chain keeps across a restart, a rebind, an unbind and a revoke.

Everything here runs against the real database, the real operation envelope and
the real transactions; only the Sheets REST surface is a recorded stand-in. The
cases are the ones where a wrong answer silently damages data: a queue entry
that outlives the target it was raised for, a restart that loses an unknown

outcome, and a confirmation that is reused after the facts moved.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataGenerationRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.providers.data.google_sheets import SheetsApiError
from tests.fixtures.model_management import FakeCredentialStore
from tests.fixtures.sheets import (
    RENDERER_TOKEN,
    FakeSheetsTransport,
    binding_impact,
    open_sheets_table,
    sheets_app,
)

GRID = {"数据": [["编号", "标题"], ["A-1", "第一行"]]}
SECOND = [["编号", "标题"], ["B-9", "另一张表"]]
COLUMNS = [("code", "编号", "string"), ("title", "标题", "string")]


def new_key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


def url(project: str, table: str, suffix: str = "") -> str:
    return f"/api/v1/projects/{project}/tables/{table}{suffix}"


def pull_response(client: Any, project: str, table: str, revision: int) -> Any:
    return client.post(
        url(project, table, "/sync/pull"),
        json={"expectedTableRevision": revision},
        headers=new_key(),
    )


def pull(client: Any, project: str, table: str, revision: int) -> dict[str, Any]:
    response = pull_response(client, project, table, revision)
    assert response.status_code == 202, response.text
    return response.json()["operation"]


def push_response(
    client: Any, project: str, table: str, epoch: int, mode: str = "due", key: Any = None
) -> Any:
    return client.post(
        url(project, table, "/sync/push"),
        json={"mode": mode, "expectedBindingEpoch": epoch},
        headers=key or new_key(),
    )


def push(client: Any, project: str, table: str, epoch: int, mode: str = "due") -> dict[str, Any]:
    return push_response(client, project, table, epoch, mode).json()["operation"]


def state(client: Any, project: str, table: str) -> dict[str, Any]:
    response = client.get(url(project, table, "/sync"))
    assert response.status_code == 200, response.text
    return response.json()


def operations(
    client: Any, project: str, table: str, status: str | None = None
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"pageSize": 100}
    if status:
        params["status"] = status
    response = client.get(url(project, table, "/sync-operations"), params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def table_detail(client: Any, project: str, table: str) -> dict[str, Any]:
    response = client.get(url(project, table))
    assert response.status_code == 200, response.text
    return response.json()


def records(client: Any, project: str, table: str, generation: str) -> list[dict[str, Any]]:
    response = client.get(
        url(project, table, "/records"),
        params={"datasetGeneration": generation, "pageSize": 100},
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


def edit_title(
    client: Any, project: str, table: str, record: dict[str, Any], field_id: str, value: str
) -> dict[str, Any]:
    raw = str(record["ref"]["recordKey"]["value"])
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    response = client.patch(
        url(project, table, f"/records/{encoded}"),
        headers=new_key(),
        json={
            "datasetGeneration": record["ref"]["datasetGeneration"],
            "recordKeyType": record["ref"]["recordKey"]["type"],
            "expectedContentRevision": record["contentRevision"],
            "values": [{"fieldId": field_id, "value": value}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def replacement_generation(
    app: Any,
    project: str,
    table: str,
    source_generation: str,
    rows: list[tuple[str, str, dict[str, Any]]],
) -> str:
    """Publish a replacement the way a re-import does.

    ``SqlAlchemyProjectExcelImports.publish`` keeps the table and its binding
    and only moves ``current_generation``, so this moves the same three facts: a
    new generation row, copied field definitions and the new records. Keeping
    the binding is the point of the test, not an artefact of the shortcut.
    """
    replacement = str(uuid4())
    now = datetime.now(UTC)
    with app.state.session_factory() as session:
        table_row = session.get(DataTableRow, table)
        assert table_row is not None
        fields = list(
            session.scalars(
                select(DataFieldRow).where(
                    DataFieldRow.table_id == table,
                    DataFieldRow.dataset_generation == source_generation,
                )
            )
        )
        session.add(
            DataGenerationRow(
                id=replacement,
                project_id=project,
                table_id=table,
                identity=dict(table_row.identity),
                source={"kind": "excel"},
                created_at=now,
            )
        )
        session.flush()
        for field in fields:
            session.add(
                DataFieldRow(
                    id=field.id,
                    project_id=project,
                    table_id=table,
                    dataset_generation=replacement,
                    key=field.key,
                    name=field.name,
                    type=field.type,
                    required=field.required,
                    writable=field.writable,
                    formula=field.formula,
                    validation=field.validation,
                    field_revision=field.field_revision,
                    position=field.position,
                )
            )
        for key_type, key_value, values in rows:
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=table,
                    dataset_generation=replacement,
                    key_type=key_type,
                    key_value=key_value,
                    values_json=values,
                    record_slots=[],
                    status_id=None,
                    current_environment_id=None,
                    content_revision=1,
                    status_revision=1,
                    link_revision=1,
                    deleted=False,
                    created_at=now,
                    updated_at=now,
                )
            )
        table_row.current_generation = replacement
        table_row.table_revision += 1
        session.commit()
    return replacement


def reconnect(tmp_path: Path, transport: FakeSheetsTransport, credentials: Any) -> Any:
    """A fresh process over the same workspace, credential store and source."""
    return sheets_app(tmp_path, transport, credentials=credentials)


def restarted(app: Any) -> TestClient:
    return TestClient(app, headers={"x-autoflow-token": RENDERER_TOKEN})


def impact(
    client: Any, project: str, action: str, target: dict[str, Any], change: dict[str, Any]
) -> Any:
    """Quote the shared confirmation the way a command has to."""
    return client.post(
        f"/api/v1/projects/{project}/mutation-impact",
        json={"action": action, "target": target, "change": change},
    )


def test_a_pending_intent_survives_a_restart_and_is_sent_once(tmp_path):
    credentials = FakeCredentialStore()
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS, credentials=credentials) as sheets:
        client, project, table = sheets.client, sheets.project, sheets.table
        pull(client, project, table, sheets.table_revision())
        edit_title(client, project, table, sheets.records()[0], sheets.field_id("title"), "重启前改的")
        before = state(client, project, table)
        assert before["summary"]["pendingCount"] == 1, before
        epoch = before["binding"]["bindingEpoch"]

    with restarted(reconnect(tmp_path, transport, credentials)) as client:
        after = state(client, project, table)
        assert after["summary"]["pendingCount"] == 1, after
        assert after["summary"]["status"] == "pending", after
        assert after["binding"]["bindingEpoch"] == epoch

        writes = transport.changes()
        identity = new_key()
        accepted = push_response(client, project, table, epoch, key=identity)
        assert accepted.status_code == 202, accepted.text
        operation = accepted.json()["operation"]
        assert operation["status"] == "succeeded", operation
        assert operation["result"]["tableId"] == table
        assert operation["result"]["summary"]["pendingCount"] == 0
        assert transport.changes() == writes + 1
        assert transport.grid("数据")[1] == ["A-1", "重启前改的"]

        replay = push_response(client, project, table, epoch, key=identity)
        assert replay.json() == accepted.json()
        assert transport.changes() == writes + 1
        confirmed = operations(client, project, table, "confirmed")
        assert [item["evidence"]["outcome"] for item in confirmed] == ["matched"]


def test_an_unknown_send_stays_unknown_across_a_restart(tmp_path):
    credentials = FakeCredentialStore()
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS, credentials=credentials) as sheets:
        client, project, table = sheets.client, sheets.project, sheets.table
        pull(client, project, table, sheets.table_revision())
        edit_title(client, project, table, sheets.records()[0], sheets.field_id("title"), "结果不明")
        epoch = state(client, project, table)["binding"]["bindingEpoch"]
        transport.fail_writes.append(
            SheetsApiError(0, "timeout", "Google Sheets 未在时限内返回结果。")
        )
        first = push(client, project, table, epoch)
        assert first["result"]["summary"]["unknownCount"] == 1, first
        unknown = operations(client, project, table, "unknown")
        assert len(unknown) == 1
        identity = unknown[0]["syncOperationId"]
        revision = unknown[0]["statusRevision"]

    with restarted(reconnect(tmp_path, transport, credentials)) as client:
        still = operations(client, project, table, "unknown")
        assert [item["syncOperationId"] for item in still] == [identity]
        assert still[0]["statusRevision"] == revision
        assert state(client, project, table)["summary"]["unknownCount"] == 1

        # A restart is not a reason to send again, not even with allPending.
        writes = transport.changes()
        again = push(client, project, table, epoch, mode="allPending")
        assert again["result"]["summary"]["unknownCount"] == 1, again
        assert transport.changes() == writes
        assert transport.grid("数据")[1] == ["A-1", "第一行"]

        path = url(project, table, f"/sync-operations/{identity}/reconcile")
        key = new_key()
        body = {"expectedStatusRevision": revision}
        reconciled = client.post(path, json=body, headers=key)
        assert reconciled.status_code == 202, reconciled.text
        decided = reconciled.json()["operation"]
        assert decided["result"]["evidence"]["outcome"] == "notMatched", decided
        assert client.post(path, json=body, headers=key).json() == reconciled.json()
        assert {item["status"] for item in operations(client, project, table)} == {"failed"}


@pytest.mark.parametrize('action', ['changeSheetsBinding', 'removeSheetsBinding'])
@pytest.mark.parametrize('preview_before_send', [True, False])
def test_unknown_value_send_blocks_binding_change_and_unbind(
    tmp_path, action, preview_before_send,
):
    transport = FakeSheetsTransport({'数据': GRID['数据'], '第二表': SECOND})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        client, project, table = sheets.client, sheets.project, sheets.table
        pull(client, project, table, sheets.table_revision())
        edit_title(client, project, table, sheets.records()[0], sheets.field_id('title'), 'old unknown')
        change = {'mode': 'remove'} if action == 'removeSheetsBinding' else {
            'connectionId': sheets.connection,
            'spreadsheetId': transport.spreadsheet_id,
            'sheetId': transport.ids['数据'],
            'identityStrategy': {'kind': 'column', 'columnId': 'A'},
            'mapping': [{'fieldId': sheets.field_id(key), 'columnId': column, 'direction': 'both', 'formula': False}
                        for key, column in [('code', 'A'), ('title', 'B')]],
        }
        payload = {'action': action, 'target': {'type': 'table', 'projectId': project, 'tableId': table}, 'change': change}
        if preview_before_send:
            preview = client.post(f'/api/v1/projects/{project}/mutation-impact', json=payload)
            assert preview.status_code == 200, preview.text
        transport.fail_writes.append(SheetsApiError(0, 'timeout', 'response lost'))
        push(client, project, table, sheets.binding['bindingEpoch'])
        unknown, = operations(client, project, table, 'unknown')
        before_rows, before_table = sheets.records(), table_detail(client, project, table)
        before_binding = client.get(url(project, table, '/sheets/binding')).json()
        before_writes = transport.changes()
        if preview_before_send:
            body = {'impactRevision': preview.json()['impactRevision'], 'expectedTableRevision': sheets.table_revision()}
            if action == 'changeSheetsBinding':
                body.update(change, expectedBindingEpoch=sheets.binding['bindingEpoch'])
            rejected = client.request('PUT' if action == 'changeSheetsBinding' else 'DELETE',
                url(project, table, '/sheets/binding'), json=body, headers=new_key())
        else:
            rejected = client.post(f'/api/v1/projects/{project}/mutation-impact', json=payload)
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()['error']['code'] == 'SHEETS_SOURCE_SEND_IN_PROGRESS'
        assert sheets.records() == before_rows
        assert table_detail(client, project, table) == before_table
        assert client.get(url(project, table, '/sheets/binding')).json() == before_binding
        assert operations(client, project, table, 'unknown') == [unknown]
        assert transport.changes() == before_writes
        assert transport.grid('数据')[1] == ['A-1', '第一行']


def test_a_rebind_retires_the_previous_epochs_intent(tmp_path):
    transport = FakeSheetsTransport({"数据": GRID["数据"], "第二表": SECOND})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        client, project, table = sheets.client, sheets.project, sheets.table
        pull(client, project, table, sheets.table_revision())
        edit_title(client, project, table, sheets.records()[0], sheets.field_id("title"), "旧目标上的改")
        epoch = sheets.binding["bindingEpoch"]
        assert state(client, project, table)["summary"]["pendingCount"] == 1

        body = {
            "connectionId": sheets.connection,
            "spreadsheetId": transport.spreadsheet_id,
            "sheetId": transport.ids["第二表"],
            "identityStrategy": {"kind": "column", "columnId": "A"},
            "mapping": [
                {
                    "fieldId": sheets.field_id(key),
                    "columnId": column,
                    "direction": "both",
                    "formula": False,
                }
                for key, column in (("code", "A"), ("title", "B"))
            ],
            "expectedTableRevision": sheets.table_revision(),
            "expectedBindingEpoch": epoch,
        }
        body["impactRevision"] = binding_impact(client, project, table, body)["impactRevision"]
        accepted = client.put(url(project, table, "/sheets/binding"), json=body, headers=new_key())
        assert accepted.status_code == 202, accepted.text
        rebound = accepted.json()["operation"]["result"]
        assert rebound["bindingEpoch"] == epoch + 1
        assert rebound["sheetName"] == "第二表"

        # The retired intent is history with a reason, not work still waiting.
        after = state(client, project, table)
        assert after["summary"]["pendingCount"] == 0, after
        retired = operations(client, project, table, "failed")
        assert [item["error"]["code"] for item in retired] == ["SYNC_BINDING_CHANGED"]

        writes = transport.changes()
        stale = push_response(client, project, table, epoch)
        assert stale.status_code == 412, stale.text
        assert stale.json()["error"]["details"]["reason"] == "bindingEpoch"
        assert transport.changes() == writes

        sent = push(client, project, table, epoch + 1)
        assert sent["result"]["summary"]["pendingCount"] == 0, sent
        assert transport.changes() == writes
        assert transport.grid("第二表")[1] == ["B-9", "另一张表"]
        assert transport.grid("数据")[1] == ["A-1", "第一行"]

        detail = table_detail(client, project, table)
        pulled = pull(client, project, table, detail["tableRevision"])
        assert pulled["result"]["tableId"] == table
        rows = records(client, project, table, detail["datasetGeneration"])
        assert [row["ref"]["recordKey"]["value"] for row in rows] == ["B-9"]


def test_a_dataset_replacement_stops_an_intent_from_the_old_generation(tmp_path):
    credentials = FakeCredentialStore()
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(
        tmp_path, transport, COLUMNS, credentials=credentials
    ) as sheets:
        client, project, table = sheets.client, sheets.project, sheets.table
        pull(client, project, table, sheets.table_revision())
        edit_title(client, project, table, sheets.records()[0], sheets.field_id("title"), "旧代次的改")
        generation = sheets.dataset_generation()
        epoch = sheets.binding["bindingEpoch"]
        fields = {key: sheets.field_id(key) for key in sheets.fields}

    app = reconnect(tmp_path, transport, credentials)
    with restarted(app) as client:
        # A re-import replaces the data; the binding survives, so the queue still
        # holds a local change whose row is no longer part of the table.
        replacement_generation(
            app,
            project,
            table,
            generation,
            [("text", "A-1", {fields["code"]: "A-1", fields["title"]: "新代次的内容"})],
        )
        after = state(client, project, table)
        assert after["summary"]["pendingCount"] == 1, after

        writes = transport.changes()
        sent = push(client, project, table, epoch)
        assert sent["result"]["summary"]["pendingCount"] == 0, sent
        assert sent["result"]["summary"]["unknownCount"] == 0, sent
        assert transport.changes() == writes, "a retired intent must not reach the source"
        assert transport.grid("数据")[1] == ["A-1", "第一行"]
        retired = operations(client, project, table, "failed")
        assert [item["error"]["code"] for item in retired] == ["SYNC_GENERATION_CHANGED"]


def test_unbind_keeps_the_local_copy_and_stops_unsent_writes(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        client, project, table = sheets.client, sheets.project, sheets.table
        pull(client, project, table, sheets.table_revision())
        edit_title(client, project, table, sheets.records()[0], sheets.field_id("title"), "还没发出去")
        revision = sheets.table_revision()
        assert state(client, project, table)["summary"]["pendingCount"] == 1

        preview = impact(
            client,
            project,
            "removeSheetsBinding",
            {"type": "table", "projectId": project, "tableId": table},
            {"mode": "remove"},
        )
        assert preview.status_code == 200, preview.text
        report = preview.json()
        assert report["blockers"] == []
        assert {item["code"] for item in report["impacts"]} == {
            "SHEETS_LOCAL_COPY_KEPT",
            "SHEETS_UNSENT_INTENTS_STOPPED",
        }

        writes = transport.changes()
        removed = client.request(
            "DELETE",
            url(project, table, "/sheets/binding"),
            json={"impactRevision": report["impactRevision"], "expectedTableRevision": revision},
            headers=new_key(),
        )
        assert removed.status_code == 202, removed.text
        result = removed.json()["operation"]["result"]
        assert result["unbound"] is True
        assert result["table"]["sourceKind"] == "unconfigured"

        # An unbound table answers with no binding rather than an error.
        unbound = client.get(url(project, table, "/sheets/binding"))
        assert unbound.status_code == 200, unbound.text
        assert unbound.json() is None
        assert state(client, project, table)["summary"]["status"] == "notApplicable"
        assert transport.changes() == writes
        assert transport.grid("数据")[1] == ["A-1", "第一行"]
        refused = push_response(client, project, table, 1)
        assert refused.status_code == 404, refused.text

        # The local copy is still there to read and to export.
        detail = table_detail(client, project, table)
        rows = records(client, project, table, detail["datasetGeneration"])
        assert len(rows) == 1
        assert {item["value"] for item in rows[0]["values"]} == {"A-1", "还没发出去"}


def test_disconnect_is_blocked_while_bound_and_forgets_the_credential(tmp_path):
    credentials = FakeCredentialStore()
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS, credentials=credentials) as sheets:
        client, project, table, connection = (
            sheets.client,
            sheets.project,
            sheets.table,
            sheets.connection,
        )
        locator = {"type": "sheetsConnection", "projectId": project, "connectionId": connection}

        def disconnect(mode: str, revision: int) -> Any:
            return client.request(
                "DELETE",
                f"/api/v1/projects/{project}/sheets/connections/{connection}",
                json={"impactRevision": revision, "mode": mode},
                headers=new_key(),
            )

        blocked = impact(client, project, "disconnectSheets", locator, {"mode": "disconnect"})
        assert blocked.status_code == 200, blocked.text
        report = blocked.json()
        assert [item["code"] for item in report["blockers"]] == ["SHEETS_CONNECTION_IN_USE"]
        assert disconnect("disconnect", report["impactRevision"]).status_code == 412

        detail = table_detail(client, project, table)
        unbind = impact(
            client,
            project,
            "removeSheetsBinding",
            {"type": "table", "projectId": project, "tableId": table},
            {"mode": "remove"},
        ).json()
        removed = client.request(
            "DELETE",
            url(project, table, "/sheets/binding"),
            json={
                "impactRevision": unbind["impactRevision"],
                "expectedTableRevision": detail["tableRevision"],
            },
            headers=new_key(),
        )
        assert removed.status_code == 202, removed.text

        # The same confirmation is refused once the facts it quoted moved.
        assert disconnect("disconnect", report["impactRevision"]).status_code == 412

        fresh = impact(
            client, project, "disconnectSheets", locator, {"mode": "forgetCredential"}
        ).json()
        assert fresh["blockers"] == []
        assert [item["code"] for item in fresh["impacts"]] == ["SHEETS_CREDENTIAL_REMOVED"]
        revoked = disconnect("forgetCredential", fresh["impactRevision"])
        assert revoked.status_code == 202, revoked.text
        assert revoked.json()["operation"]["result"] == {
            "connectionId": connection,
            "mode": "forgetCredential",
            "disconnected": True,
        }
        assert credentials.values == {}
        assert client.get(f"/api/v1/projects/{project}/sheets/connections").json()["items"] == []
        # The connection is gone, so the confirmation has nothing to authorise;
        # an invented revision is still refused before that.
        assert disconnect("forgetCredential", fresh["impactRevision"]).status_code == 404
        assert disconnect("forgetCredential", 999_999).status_code == 412

        rebind = impact(
            client,
            project,
            "changeSheetsBinding",
            {"type": "table", "projectId": project, "tableId": table},
            {
                "connectionId": connection,
                "spreadsheetId": transport.spreadsheet_id,
                "sheetId": next(iter(transport.ids.values())),
                "identityStrategy": {"kind": "column", "columnId": "A"},
                "mapping": [],
            },
        )
        assert rebind.status_code == 404, rebind.text
        assert rebind.json()["error"]["code"] == "SHEETS_CONNECTION_NOT_FOUND"


def test_a_stale_impact_confirmation_is_refused_after_the_table_moves(tmp_path):
    transport = FakeSheetsTransport({"数据": GRID["数据"], "第二表": SECOND})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        client, project, table = sheets.client, sheets.project, sheets.table
        body = {
            "connectionId": sheets.connection,
            "spreadsheetId": transport.spreadsheet_id,
            "sheetId": transport.ids["第二表"],
            "identityStrategy": {"kind": "column", "columnId": "A"},
            "mapping": [
                {
                    "fieldId": sheets.field_id(key),
                    "columnId": column,
                    "direction": "both",
                    "formula": False,
                }
                for key, column in (("code", "A"), ("title", "B"))
            ],
            "expectedTableRevision": sheets.table_revision(),
            "expectedBindingEpoch": sheets.binding["bindingEpoch"],
        }
        report = impact(
            client,
            project,
            "changeSheetsBinding",
            {"type": "table", "projectId": project, "tableId": table},
            {
                key: body[key]
                for key in body
                if key not in {"expectedTableRevision", "expectedBindingEpoch"}
            },
        )
        assert report.status_code == 200, report.text
        revision = report.json()["impactRevision"]

        # A field added after the preview moves the table revision.
        added = client.post(
            url(project, table, "/fields"),
            json={
                "definition": {
                    "key": "note",
                    "name": "备注",
                    "type": "string",
                    "required": False,
                    "validation": {},
                },
                "expectedTableRevision": body["expectedTableRevision"],
                "sourceColumnPolicy": "localOnly",
            },
            headers=new_key(),
        )
        assert added.status_code == 200, added.text
        moved = table_detail(client, project, table)
        assert moved["tableRevision"] > body["expectedTableRevision"]

        stale = client.put(
            url(project, table, "/sheets/binding"),
            json={**body, "impactRevision": revision},
            headers=new_key(),
        )
        assert stale.status_code == 412, stale.text
        assert stale.json()["error"]["code"] == "PRECONDITION_FAILED"

        # The same confirmation cannot be re-aimed at another target either.
        retargeted = client.put(
            url(project, table, "/sheets/binding"),
            json={**body, "impactRevision": revision, "sheetId": transport.ids["数据"]},
            headers=new_key(),
        )
        assert retargeted.status_code == 412, retargeted.text


def test_archive_preserves_unsent_local_data_and_refuses_new_source_writes(tmp_path):
    from tests.integration.test_project_sheets_sync import (
        edit_title as edit_local_title,
    )
    from tests.integration.test_project_sheets_sync import (
        pull as pull_table,
    )
    from tests.integration.test_project_sheets_sync import (
        push as push_table,
    )
    from tests.integration.test_project_sheets_sync import (
        sync_operations,
    )

    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull_table(sheets)
        local = edit_local_title(sheets, sheets.records()[0], 'preserved after archive')
        pending, = sync_operations(sheets, 'pending')
        base = f'/api/v1/projects/{sheets.project}'
        project = sheets.client.get(base).json()
        preview = sheets.client.get(base+'/lifecycle-impact', params={'action':'archive'})
        assert preview.status_code == 200 and preview.json()['unsyncedCount'] == 1
        assert preview.json()['blockers'] == []
        response = sheets.client.post(base+'/archive', headers=new_key(), json={
            'expectedManagementRevision':project['managementRevision'],
            'impactRevision':preview.json()['impactRevision'],
        })
        assert response.status_code in {200, 202}, response.text
        sheets.client.app.state.project_lifecycle.repository.advance(sheets.project)
        assert sheets.client.get(base).json()['lifecycleState'] == 'archived'
        writes = transport.changes()
        refused = push_table(sheets)
        assert refused.status_code == 409, refused.text
        assert sheets.records()[0] == local
        assert sync_operations(sheets, 'pending') == [pending]
        assert transport.changes() == writes
        assert transport.grid('数据')[1] == ['A-1', '第一行']


def test_archive_waits_for_unknown_value_send_and_allows_original_reconciliation(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        client, project, table = sheets.client, sheets.project, sheets.table
        pull(client, project, table, sheets.table_revision())
        edit_title(client, project, table, sheets.records()[0], sheets.field_id('title'), 'unconfirmed')
        epoch = state(client, project, table)['binding']['bindingEpoch']
        transport.fail_writes.append(SheetsApiError(0, 'timeout', 'lost response'))
        push(client, project, table, epoch)
        unknown, = operations(client, project, table, 'unknown')
        base = f'/api/v1/projects/{project}'
        preview = client.get(base + '/lifecycle-impact', params={'action': 'archive'}).json()
        assert any(item['code'] == 'SYNC_UNCONFIRMED' for item in preview['blockers']), preview
        accepted = client.post(base + '/archive', headers=new_key(), json={
            'expectedManagementRevision': client.get(base).json()['managementRevision'],
            'impactRevision': preview['impactRevision'],
        })
        assert accepted.status_code == 202, accepted.text
        archive = accepted.json()['operation']['operationId']
        repository = client.app.state.project_lifecycle.repository
        repository.advance(project)
        assert client.get(base).json()['lifecycleState'] == 'closing'
        assert client.get(base + f'/operations/{archive}').json()['status'] == 'running'
        assert push_response(client, project, table, epoch).status_code == 423
        writes = transport.changes()
        target = url(project, table, f"/sync-operations/{unknown['syncOperationId']}/reconcile")
        key = new_key()
        body = {'expectedStatusRevision': unknown['statusRevision']}
        reconciled = client.post(target, headers=key, json=body)
        assert reconciled.status_code == 202, reconciled.text
        assert reconciled.json()['operation']['result']['evidence']['outcome'] == 'notMatched'
        repository.advance(project)
        assert client.get(base).json()['lifecycleState'] == 'archived'
        assert client.get(base + f'/operations/{archive}').json()['status'] == 'succeeded'
        assert client.post(target, headers=key, json=body).json() == reconciled.json()
        assert transport.changes() == writes
