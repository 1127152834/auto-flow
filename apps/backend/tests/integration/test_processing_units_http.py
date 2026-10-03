"""Remediation M2 R2-06: processing units are listed and changed only by explicit, audited commands."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.processing_units import processing_units_router
from autoflow.application.project_runs.processing_units import ProcessingUnitService
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.project_runs.ledger import TaskOutcome, scope_for
from autoflow.infrastructure.database.record_ledger import SqlAlchemyRecordLedger
from tests.integration.test_project_run_data_start import _setup

NOW = datetime(2026, 10, 2, tzinfo=UTC)


@pytest.fixture
def api(tmp_path):
    factory, project_id, automation, _ = _setup(tmp_path)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(processing_units_router(ProcessingUnitService(factory)))
    chosen = automation.input_plan["processingInputId"]
    table = automation.input_plan["inputs"][0]["tableId"]
    generation = automation.input_plan["inputs"][0]["datasetGeneration"]

    def unit(value, kind=None):
        scope = scope_for(automation.automation_id, chosen, RecordRef(project_id, table, generation, RecordKey("text", value)), None)
        with factory.begin() as session:
            ledger = SqlAlchemyRecordLedger(session)
            ledger.ensure(scope, NOW)
            if kind:
                ledger.project(scope, TaskOutcome(kind, "task-1", "run-1", {"code": "E", "message": "m"}),
                               budget=3, backoff=(60,), now=NOW)
        return scope

    base = f"/api/v1/projects/{project_id}/automations/{automation.automation_id}/processing-units"
    yield TestClient(app), base, unit
    factory.dispose()


def command(client, base, unit_id, action, body, key=None):
    return client.post(f"{base}/{unit_id}/{action}", headers={"Idempotency-Key": key or str(uuid4())}, json=body)


def test_list_filters_by_state_and_pages(api):
    client, base, unit = api
    for value in ("A", "B", "C"):
        unit(value)
    unit("D", "unknown")
    first = client.get(base, params={"state": "pending", "limit": 2}).json()
    assert len(first["items"]) == 2 and first["nextAfter"]
    rest = client.get(base, params={"state": "pending", "after": first["nextAfter"]}).json()
    keys = {item["recordRef"]["recordKey"]["value"] for item in first["items"] + rest["items"]}
    assert keys == {"A", "B", "C"} and rest["nextAfter"] is None
    review = client.get(base, params={"state": "needs_review"}).json()["items"]
    assert [item["state"] for item in review] == ["needs_review"]
    assert review[0]["review"]["unknown"]["taskId"] == "task-1"


def test_skip_then_reset_with_revision_and_idempotent_replay(api):
    client, base, unit = api
    unit("A")
    unit_id = client.get(base).json()["items"][0]["unitId"]
    key = str(uuid4())
    skipped = command(client, base, unit_id, "skip", {"expectedRevision": 1, "reason": "不需要处理"}, key)
    assert skipped.status_code == 200, skipped.text
    assert skipped.json()["unit"]["state"] == "skipped" and skipped.json()["operation"]["status"] == "succeeded"
    replay = command(client, base, unit_id, "skip", {"expectedRevision": 1, "reason": "不需要处理"}, key)
    assert replay.status_code == 200 and replay.json()["operation"] == skipped.json()["operation"]
    mismatch = command(client, base, unit_id, "skip", {"expectedRevision": 1, "reason": "别的"}, key)
    assert mismatch.status_code == 409 and mismatch.json()["error"]["code"] == "OPERATION_PAYLOAD_MISMATCH"
    stale = command(client, base, unit_id, "reset", {"expectedRevision": 1, "reason": "重试"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "LEDGER_REVISION_CONFLICT"
    reset = command(client, base, unit_id, "reset", {"expectedRevision": 2, "reason": "重试"})
    assert reset.status_code == 200 and reset.json()["unit"]["state"] == "pending"


def test_needs_review_only_leaves_through_resolve(api):
    client, base, unit = api
    unit("A", "unknown")
    current = client.get(base).json()["items"][0]
    for action in ("reset", "skip"):
        refused = command(client, base, current["unitId"], action, {"expectedRevision": current["revision"], "reason": "x"})
        assert refused.status_code == 409 and refused.json()["error"]["code"] == "LEDGER_NEEDS_REVIEW"
    resolved = command(client, base, current["unitId"], "resolve", {
        "expectedRevision": current["revision"], "reason": "已确认对方系统没有收到", "decision": "confirmedNotPerformed",
    })
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["unit"]["state"] == "pending"
    assert resolved.json()["unit"]["review"]["unknown"]["taskId"] == "task-1"


def test_unknown_unit_and_bad_request_are_rejected(api):
    client, base, unit = api
    assert command(client, base, str(uuid4()), "skip", {"expectedRevision": 1, "reason": "x"}).status_code == 404
    unit("A")
    unit_id = client.get(base).json()["items"][0]["unitId"]
    assert command(client, base, unit_id, "skip", {"expectedRevision": 1, "reason": ""}).status_code == 422
    assert command(client, base, unit_id, "resolve", {"expectedRevision": 1, "reason": "x", "decision": "maybe"}).status_code == 422
