from __future__ import annotations

import sqlite3
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from autoflow.domain.workflows.runtime import (
    CoreRun,
    PreparedContent,
    RunEvent,
    WorkflowRuntimeError,
    append_run_event,
    create_core_run,
    create_prepared_content,
    transition_core_run,
)
from autoflow.infrastructure.database.workflow_runtime import _is_sqlite_contention

NOW = datetime(2026, 9, 14, 9, 0, tzinfo=UTC)


def test_only_sqlite_busy_and_locked_operational_errors_are_contention():
    locked = OperationalError(
        "UPDATE", {}, sqlite3.OperationalError("database is locked")
    )
    table_locked = OperationalError(
        "UPDATE", {}, sqlite3.OperationalError("database table is locked")
    )
    busy = OperationalError("UPDATE", {}, sqlite3.OperationalError("database is busy"))
    io_failure = OperationalError(
        "UPDATE", {}, sqlite3.OperationalError("disk I/O error")
    )

    assert _is_sqlite_contention(locked)
    assert _is_sqlite_contention(table_locked)
    assert _is_sqlite_contention(busy)
    assert not _is_sqlite_contention(io_failure)


def test_direct_construction_freezes_nested_json_and_normalizes_all_times():
    nested = {"items": [{"value": 1}]}
    naive = datetime(2026, 9, 14, 10, 0)  # noqa: DTZ001 - legacy SQLite value
    prepared = PreparedContent(
        "content",
        "operation",
        "digest",
        "workflow",
        1,
        "checksum",
        nested,
        nested,
        "adapter",
        ("browser",),
        nested,
        naive,
    )
    run = CoreRun(
        "run",
        "request",
        "digest",
        "content",
        nested,
        nested,
        nested,
        (nested,),
        "failed",
        2,
        1,
        0,
        naive,
        naive,
        naive,
        naive,
        nested,
    )
    event = RunEvent("event", "run", 1, 1, "log", "node", None, None, naive, nested)

    nested["items"][0]["value"] = 2
    assert prepared.document["items"][0]["value"] == 1
    assert run.parameters["items"][0]["value"] == 1
    assert run.error is not None and run.error["items"][0]["value"] == 1
    assert event.payload["items"][0]["value"] == 1
    assert prepared.created_at.tzinfo is UTC
    assert run.completed_at is not None and run.completed_at.tzinfo is UTC
    assert event.occurred_at.tzinfo is UTC
    with pytest.raises(TypeError):
        prepared.document["items"][0]["value"] = 3  # type: ignore[index]


def _prepared_content():
    return create_prepared_content(
        prepared_content_id=str(uuid4()),
        prepare_operation_id=str(uuid4()),
        request_digest="a" * 64,
        workflow_id=str(uuid4()),
        source_revision=7,
        checksum="b" * 64,
        document={"source": "webrpa", "format": "autoflow.webrpa/v1", "nodes": []},
        execution_plan={
            "orderedNodeIds": ["open"],
            "moduleTypes": ["open_page"],
        },
        adapter_version="webrpa-chain/v1",
        capability_requirements=["browser.cloakbrowser"],
        provenance={"kind": "workflowRevision", "revision": 7},
        created_at=NOW,
    )


def _queued_run():
    return create_core_run(
        run_id=str(uuid4()),
        run_request_id=str(uuid4()),
        request_digest="c" * 64,
        prepared_content_id=str(uuid4()),
        parameters={"query": "温室", "limit": 0, "enabled": False},
        input_snapshot_ref=None,
        resource_request={"profileId": None, "proxy": {"mode": "sourceDefault"}},
        capability_bindings=[
            {"capability": "browser.cloakbrowser", "provider": "local"}
        ],
        created_at=NOW,
    )


def test_prepared_content_freezes_the_complete_request_and_defensively_copies_json():
    document = {
        "source": "webrpa",
        "format": "autoflow.webrpa/v1",
        "nodes": [{"id": "open", "data": {"moduleType": "open_url"}}],
    }
    requirements = ["browser.cloakbrowser"]
    execution_plan = {
        "orderedNodeIds": ["open"],
        "moduleTypes": ["open_page"],
        "nodes": [{"id": "open", "config": {"timeout": 60}}],
    }
    prepared = create_prepared_content(
        prepared_content_id=str(uuid4()),
        prepare_operation_id=str(uuid4()),
        request_digest="a" * 64,
        workflow_id=str(uuid4()),
        source_revision=4,
        checksum="b" * 64,
        document=document,
        execution_plan=execution_plan,
        adapter_version="webrpa-chain/v1",
        capability_requirements=requirements,
        provenance={"kind": "workflowRevision", "revision": 4},
        created_at=NOW,
    )

    document["nodes"][0]["data"]["moduleType"] = "click"
    execution_plan["orderedNodeIds"].append("late-node")
    execution_plan["nodes"][0]["config"]["timeout"] = 1
    requirements.append("browser.other")

    assert prepared.document["nodes"][0]["data"]["moduleType"] == "open_url"
    assert prepared.execution_plan["orderedNodeIds"] == ("open",)
    assert prepared.execution_plan["nodes"][0]["config"]["timeout"] == 60
    assert prepared.adapter_version == "webrpa-chain/v1"
    assert prepared.capability_requirements == ("browser.cloakbrowser",)
    assert prepared.source_revision == 4
    assert prepared.prepare_operation_id
    assert prepared.request_digest == "a" * 64
    with pytest.raises(FrozenInstanceError):
        prepared.checksum = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        prepared.document["nodes"][0]["data"]["moduleType"] = "click"  # type: ignore[index]
    with pytest.raises(TypeError):
        prepared.execution_plan["nodes"][0]["config"]["timeout"] = 1  # type: ignore[index]


def test_core_run_is_created_queued_with_the_complete_v2_identity_and_request():
    run = _queued_run()

    assert run.status == "queued"
    assert run.status_revision == 1
    assert run.execution_generation == 0
    assert run.last_sequence == 0
    assert run.started_at is None
    assert run.completed_at is None
    assert run.error is None
    assert run.parameters == {"query": "温室", "limit": 0, "enabled": False}
    assert run.input_snapshot_ref is None
    assert run.created_at == NOW
    assert run.updated_at == NOW
    with pytest.raises(TypeError):
        run.resource_request["proxy"]["mode"] = "none"  # type: ignore[index]


def test_run_state_machine_increments_ownership_and_keeps_terminal_state_irreversible():
    queued = _queued_run()
    running = transition_core_run(
        queued,
        target_status="running",
        expected_status_revision=1,
        expected_execution_generation=0,
        now=NOW + timedelta(seconds=1),
    )
    finishing = transition_core_run(
        running,
        target_status="finishing",
        expected_status_revision=2,
        expected_execution_generation=1,
        now=NOW + timedelta(seconds=2),
    )
    succeeded = transition_core_run(
        finishing,
        target_status="succeeded",
        expected_status_revision=3,
        expected_execution_generation=1,
        now=NOW + timedelta(seconds=3),
    )

    assert running.execution_generation == 1
    assert running.started_at == NOW + timedelta(seconds=1)
    assert succeeded.status_revision == 4
    assert succeeded.completed_at == NOW + timedelta(seconds=3)
    assert succeeded.error is None

    with pytest.raises(WorkflowRuntimeError) as caught:
        transition_core_run(
            succeeded,
            target_status="running",
            expected_status_revision=4,
            expected_execution_generation=1,
            now=NOW + timedelta(seconds=4),
        )
    assert caught.value.code == "RUN_TERMINAL"


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("queued", "stopping"),
        ("running", "stopping"),
        ("running", "reconciling"),
        ("stopping", "reconciling"),
    ],
)
def test_run_state_machine_allows_stop_and_reconciliation_paths(start, target):
    run = _queued_run()
    if start != "queued":
        run = transition_core_run(
            run,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW + timedelta(seconds=1),
        )
    if start == "stopping":
        run = transition_core_run(
            run,
            target_status="stopping",
            expected_status_revision=2,
            expected_execution_generation=1,
            now=NOW + timedelta(seconds=2),
        )

    changed = transition_core_run(
        run,
        target_status=target,
        expected_status_revision=run.status_revision,
        expected_execution_generation=run.execution_generation,
        now=NOW + timedelta(seconds=3),
    )
    assert changed.status == target


def test_stale_status_revision_and_revoked_generation_are_rejected():
    running = transition_core_run(
        _queued_run(),
        target_status="running",
        expected_status_revision=1,
        expected_execution_generation=0,
        now=NOW + timedelta(seconds=1),
    )

    with pytest.raises(WorkflowRuntimeError) as caught:
        transition_core_run(
            running,
            target_status="finishing",
            expected_status_revision=1,
            expected_execution_generation=1,
            now=NOW + timedelta(seconds=2),
        )
    assert caught.value.code == "RUN_STATUS_CONFLICT"

    with pytest.raises(WorkflowRuntimeError) as caught:
        transition_core_run(
            running,
            target_status="finishing",
            expected_status_revision=2,
            expected_execution_generation=0,
            now=NOW + timedelta(seconds=2),
        )
    assert caught.value.code == "EXECUTION_GENERATION_REVOKED"


def test_run_events_are_monotonic_deduplicated_and_generation_guarded():
    running = transition_core_run(
        _queued_run(),
        target_status="running",
        expected_status_revision=1,
        expected_execution_generation=0,
        now=NOW + timedelta(seconds=1),
    )
    event_id = str(uuid4())
    event = {
        "eventId": event_id,
        "runId": running.run_id,
        "executionGeneration": 1,
        "kind": "nodeAttempt",
        "nodeId": "open",
        "nodeVisitId": "visit-1",
        "attempt": 1,
        "occurredAt": (NOW + timedelta(seconds=2)).isoformat(),
        "payload": {"nodeId": "open", "status": "started"},
    }

    advanced, accepted = append_run_event(running, event)
    duplicate, accepted_again = append_run_event(advanced, event)

    assert accepted is True
    assert advanced.last_sequence == 1
    assert accepted_again is False
    assert duplicate == advanced
    assert advanced._event_identities  # immutable event identity evidence

    with pytest.raises(WorkflowRuntimeError) as caught:
        append_run_event(
            advanced,
            {**event, "eventId": str(uuid4()), "sequence": 3},
        )
    assert caught.value.code == "RUN_EVENT_SEQUENCE_CONFLICT"

    with pytest.raises(WorkflowRuntimeError) as caught:
        append_run_event(
            advanced,
            {
                **event,
                "eventId": str(uuid4()),
                "sequence": 2,
                "executionGeneration": 0,
            },
        )
    assert caught.value.code == "EXECUTION_GENERATION_REVOKED"
