"""Source observations are scoped read-only facts, never local writes."""
import base64

from tests.fixtures.sheets import FakeSheetsTransport, open_sheets_table
from tests.integration.test_project_sheets_sync import (
    COLUMNS,
    GRID,
    edit_title,
    pull,
    push,
    sync_operations,
)


def observations(sheets, record, **overrides):
    key = record["ref"]["recordKey"]
    encoded = base64.urlsafe_b64encode(key["value"].encode()).decode().rstrip("=")
    return sheets.client.get(sheets.url(f"/records/{encoded}/source-observations"), params={
        "datasetGeneration": record["ref"]["datasetGeneration"], "recordKeyType": key["type"], **overrides,
    })


def test_source_observation_keeps_local_values_revisions_and_pending_intent(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        record = edit_title(sheets, sheets.records()[0], "本地新值")
        pending = sync_operations(sheets, "pending")
        transport.grids[1000][1][1] = "远端新值"
        writes = transport.changes()
        pull(sheets)
        response = observations(sheets, record)
        assert response.status_code == 200, response.text
        observed = next(item for item in response.json()["items"] if item["fieldId"] == sheets.field_id("title"))
        assert observed["remoteValue"] == "远端新值"
        assert observed["localValue"] == "本地新值"
        assert observed["localContentRevision"] == record["contentRevision"]
        assert observed["differs"] is True
        assert observed["observedAt"]
        assert sheets.records()[0] == record
        assert sync_operations(sheets, "pending") == pending
        assert transport.changes() == writes
        assert push(sheets).status_code == 202
        assert observations(sheets, record).json() == response.json(), "push evidence must not overwrite observation"
        assert sync_operations(sheets, "confirmed")[0]["evidence"]["outcome"] == "matched"
        pull(sheets)
        latest = observations(sheets, record).json()["items"]
        assert all(not item["differs"] for item in latest)
        assert len(latest) == 2, "only latest field observations are retained"
        assert sheets.records()[0] == record


def test_observations_hide_old_generation_epoch_unbound_and_deleted_records(tmp_path):
    from uuid import uuid4

    from autoflow.domain.project_data.identity import RecordKey
    from autoflow.infrastructure.database.project_data_models import DataRecordRow
    from autoflow.infrastructure.database.project_sync import SqlAlchemyProjectSync
    from autoflow.infrastructure.database.project_sync_models import (
        SheetsBindingRow,
        SyncRecordMarkRow,
    )

    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        record = sheets.records()[0]
        factory = sheets.client.app.state.session_factory
        assert observations(sheets, record).json()["items"]
        assert observations(sheets, record, datasetGeneration=str(uuid4())).status_code == 410
        with factory.begin() as session:
            binding = session.get(SheetsBindingRow, sheets.table)
            binding.binding_epoch += 1
        assert observations(sheets, record).json()["items"] == []
        SqlAlchemyProjectSync(factory).observe_source(sheets.project, sheets.table, record["ref"]["datasetGeneration"], sheets.binding["bindingEpoch"], RecordKey("text", "A-1"), {sheets.field_id("title"): "late"})
        with factory() as session:
            mark = session.get(SyncRecordMarkRow, (sheets.table, "text", "A-1"))
            assert mark.observed["inboundObservation"]["items"][1]["remoteValue"] != "late"
        with factory.begin() as session:
            session.delete(session.get(SheetsBindingRow, sheets.table))
        assert observations(sheets, record).json()["items"] == []
        with factory.begin() as session:
            session.get(DataRecordRow, (record["ref"]["datasetGeneration"], "text", "A-1")).deleted = True
        assert observations(sheets, record).status_code == 404
        assert transport.changes() == 0


def test_formula_refresh_remains_separate_from_ordinary_observations(tmp_path):
    transport = FakeSheetsTransport(GRID, formulas={"数据": [["编号", "标题"], ["A-1", "=1+1"]]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        record = sheets.records()[0]
        transport.formulas[1000][1][1] = "=2+2"
        pull(sheets)
        refreshed = sheets.records()[0]
        assert refreshed["contentRevision"] == record["contentRevision"] + 1
        assert next(cell["value"] for cell in refreshed["values"] if cell["fieldId"] == sheets.field_id("title")) == "=2+2"
        assert [item["fieldId"] for item in observations(sheets, record).json()["items"]] == [sheets.field_id("code")]
        assert sync_operations(sheets, "pending") == []
        assert transport.changes() == 0


def test_ambiguous_source_identity_does_not_replace_trusted_observation(tmp_path):
    transport = FakeSheetsTransport(GRID)
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        record = sheets.records()[0]
        before = observations(sheets, record).json()
        transport.grids[1000].extend([["A-1", "重复身份"]])
        pull(sheets)
        assert observations(sheets, record).json() == before
        assert transport.changes() == 0
