"""Remediation M2 Task 1: ledger persistence, upgrade backfill and unknown-run gate on real SQLite."""

import json
import sqlite3
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.project_runs.ledger import LedgerError, scope_for
from autoflow.infrastructure.database import session as database_session
from autoflow.infrastructure.database.migrations.versions import rm2_record_ledger
from autoflow.infrastructure.database.record_ledger import (
    SqlAlchemyRecordLedger,
    processing_input_report,
)

NOW = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
PROJECT, AUTOMATION, OTHER = "p" * 36, "a" * 36, "b" * 36


def seed(connection: sqlite3.Connection, plan: dict, automation_id: str = AUTOMATION) -> None:
    connection.execute("PRAGMA foreign_keys=OFF")
    connection.execute(
        "INSERT OR IGNORE INTO projects (id, name, name_key, description, search_text, default_resources,"
        " management_revision, lifecycle_state, created_at, updated_at)"
        " VALUES (?, 'p', 'p', '', 'p', '{}', 1, 'active', '2026-01-01', '2026-01-01')",
        (PROJECT,),
    )
    connection.execute(
        "INSERT INTO project_automations (id, project_id, workflow_id, name, name_key, search_text, description,"
        " management_revision, input_plan, parameter_schema, environment_policy, run_policy, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, 'n', '', 1, ?, '[]', '{}', '{}', '2026-01-01', '2026-01-01')",
        (automation_id, PROJECT, automation_id, automation_id, automation_id, json.dumps(plan)),
    )


def data_input(input_id: str, required: bool = True) -> dict:
    return {"inputId": input_id, "required": required, "mode": "independent"}


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    database_session.migrate_database(path)
    return path


@pytest.fixture
def factory(database):
    return database_session.create_session_factory(database)


def ref(value="A-1", key_type="text"):
    return RecordRef(PROJECT, "t" * 36, "g" * 36, RecordKey(key_type, value))


def test_ensure_creates_one_pending_entry_per_complete_scope(factory, database):
    with sqlite3.connect(database) as connection:
        seed(connection, {"inputs": [data_input("i1")]})
    scope = scope_for(AUTOMATION, "i1", ref(), None)
    with factory() as session:
        ledger = SqlAlchemyRecordLedger(session)
        first = ledger.ensure(scope, NOW)
        again = ledger.ensure(scope, NOW)
        integer_scope = ledger.ensure(scope_for(AUTOMATION, "i1", ref("1", "integer"), None), NOW)
        text_scope = ledger.ensure(scope_for(AUTOMATION, "i1", ref("1", "text"), None), NOW)
        session.commit()
    assert first == again and first.state == "pending" and first.revision == 1
    assert integer_scope.scope != text_scope.scope
    with factory() as session:
        assert len(SqlAlchemyRecordLedger(session).list(AUTOMATION, limit=10)) == 3


def test_manual_commands_use_revision_and_keep_audit(factory, database):
    with sqlite3.connect(database) as connection:
        seed(connection, {"inputs": [data_input("i1")]})
    scope = scope_for(AUTOMATION, "i1", ref(), "ns-1")
    with factory() as session:
        ledger = SqlAlchemyRecordLedger(session)
        ledger.ensure(scope, NOW)
        skipped = ledger.skip(scope, expected_revision=1, reason="不处理", now=NOW)
        with pytest.raises(LedgerError) as stale:
            ledger.reset(scope, expected_revision=1, reason="x", now=NOW)
        reset = ledger.reset(scope, expected_revision=2, reason="重新处理", now=NOW)
        session.commit()
    assert stale.value.code == "LEDGER_REVISION_CONFLICT"
    assert skipped.state == "skipped" and reset.state == "pending" and reset.processing_cycle == 2
    with factory() as session:
        stored = SqlAlchemyRecordLedger(session).get(scope)
    assert stored == reset and stored.scope.identity_namespace == "ns-1"
    assert stored.review["action"] == "reset"


def test_list_pages_by_state_without_skipping_entries(factory, database):
    with sqlite3.connect(database) as connection:
        seed(connection, {"inputs": [data_input("i1")]})
    with factory() as session:
        ledger = SqlAlchemyRecordLedger(session)
        for index in range(5):
            ledger.ensure(scope_for(AUTOMATION, "i1", ref(f"K-{index}"), None), NOW)
        ledger.skip(scope_for(AUTOMATION, "i1", ref("K-0"), None), expected_revision=1, reason="x", now=NOW)
        session.commit()
    with factory() as session:
        ledger = SqlAlchemyRecordLedger(session)
        first = ledger.list(AUTOMATION, state="pending", limit=2)
        second = ledger.list(AUTOMATION, state="pending", after=first[-1].id, limit=10)
    keys = [item.entry.scope.key_value for item in first + second]
    assert sorted(keys) == ["K-1", "K-2", "K-3", "K-4"] and len(set(keys)) == 4


def test_upgrade_backfills_single_input_and_reports_ambiguity(database, factory):
    with sqlite3.connect(database) as connection:
        seed(connection, {"inputs": [data_input("i1"), data_input("i2", required=False)]})
        seed(connection, {"inputs": [data_input("i1"), data_input("i2")]}, automation_id=OTHER)
    with factory() as session:
        rm2_record_ledger.backfill_processing_inputs(session.connection())
        rm2_record_ledger.backfill_processing_inputs(session.connection())  # re-entrant
        session.commit()
        plans = dict(session.execute(text("SELECT id, input_plan FROM project_automations")).all())
        report = processing_input_report(session)
    assert json.loads(plans[AUTOMATION])["processingInputId"] == "i1"
    assert "processingInputId" not in json.loads(plans[OTHER])
    assert [item["automationId"] for item in report] == [OTHER]


def test_upgrade_turns_unknown_runs_into_needs_review(database, factory):
    plan = {"inputs": [data_input("i1"), data_input("fixed", required=False)]}
    record = {"projectId": PROJECT, "tableId": "t" * 36, "datasetGeneration": "g" * 36,
              "recordKey": {"type": "text", "value": "A-1"}}
    sheets_key = json.dumps({"source": "sheets", "identityNamespace": "ns-9", "recordKey": record["recordKey"]})
    with sqlite3.connect(database) as connection:
        seed(connection, plan)
        connection.execute(
            "INSERT INTO project_batches (id, project_id, automation_id, start_operation_id, prepared_content_id,"
            " automation_revision, workflow_revision, status, status_revision, frozen_request, created_at)"
            " VALUES ('batch', ?, ?, 'op', 'pc', 1, 1, 'completed', 1, ?, '2026-01-01')",
            (PROJECT, AUTOMATION, json.dumps({"automation": {"inputPlan": plan}})),
        )
        for task, status, code in (("task-u", "interrupted", "WORKFLOW_RESULT_UNKNOWN"),
                                   ("task-f", "failed", "WORKFLOW_NODE_FAILED")):
            connection.execute(
                "INSERT INTO project_workflow_runs (id, run_request_id, request_digest, prepared_content_id,"
                " parameters, resource_request, capability_bindings, status, status_revision,"
                " execution_generation, last_sequence, created_at, updated_at, error)"
                " VALUES (?, ?, 'd', 'pc', '{}', '{}', '[]', ?, 1, 1, 0, '2026-01-01', '2026-01-01', ?)",
                (f"run-{task}", f"req-{task}", status, json.dumps({"code": code})),
            )
            connection.execute(
                "INSERT INTO project_tasks (id, project_id, batch_id, run_id, run_request_id, ordinal, created_at)"
                " VALUES (?, ?, 'batch', ?, ?, ?, '2026-01-01')",
                (task, PROJECT, f"run-{task}", f"req-{task}", 1 if task == "task-u" else 2),
            )
            connection.execute(
                "INSERT INTO project_task_input_snapshots (id, task_id, batch_id, parameters, inputs, captured_at)"
                " VALUES (?, ?, 'batch', '{}', ?, '2026-01-01')",
                (f"snap-{task}", task, json.dumps([
                    {"inputId": "i1", "leaseId": f"lease-{task}", "recordRef": record},
                    {"inputId": "fixed", "leaseId": None, "recordRef": {**record, "recordKey": {"type": "text", "value": "ACC"}}},
                ])),
            )
            connection.execute(
                "INSERT INTO project_record_leases (id, lease_key, project_id, batch_id, task_id, run_id, record_ref,"
                " lease_generation, state, created_at, updated_at) VALUES (?, ?, ?, 'batch', ?, ?, ?, 1, 'released',"
                " '2026-01-01', '2026-01-01')",
                (f"lease-{task}", sheets_key, PROJECT, task, f"run-{task}", json.dumps(record)),
            )
    with factory() as session:
        rm2_record_ledger.gate_unknown_runs(session.connection(), NOW)
        rm2_record_ledger.gate_unknown_runs(session.connection(), NOW)  # re-entrant
        session.commit()
        entries = SqlAlchemyRecordLedger(session).list(AUTOMATION, limit=10)
    assert len(entries) == 1
    entry = entries[0].entry
    assert entry.state == "needs_review" and entry.scope.key_value == "A-1"
    assert entry.scope.processing_input_id == "i1"
    assert entry.scope.identity_namespace == "ns-9"
    assert entry.review["unknown"]["taskId"] == "task-u"
