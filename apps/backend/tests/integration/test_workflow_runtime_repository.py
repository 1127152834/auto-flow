from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.runtime import WorkflowRuntimeError, thaw_json
from autoflow.infrastructure.database import session as database_session
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunRow,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload

NOW = datetime(2026, 9, 14, 10, 0, tzinfo=UTC)


def _migration_config(database: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def _seed_one_legacy_run(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO workflow_documents VALUES (?,?,?,?,?,?,?)",
            (
                "legacy-workflow",
                "旧工作流",
                json.dumps({"legacy": True}),
                "{}",
                1,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        connection.execute(
            "INSERT INTO workflow_runs VALUES (?,?,?,?,?,?)",
            (
                "legacy-run",
                "legacy-workflow",
                "a" * 64,
                NOW.isoformat(),
                None,
                json.dumps(
                    {
                        "runId": "legacy-run",
                        "workflowId": "legacy-workflow",
                        "state": "succeeded",
                        "startedAt": NOW.isoformat(),
                        "finishedAt": NOW.isoformat(),
                        "nodeOrder": [],
                    }
                ),
            ),
        )


def _repository(session):
    repository = SqlAlchemyWorkflowRuntimeRepository(session)
    assert not hasattr(repository, "commit")
    return repository


def _prepare_content(repository, session, *, operation_id=None, digest="a" * 64):
    workflow_id = str(uuid4())
    session.add(
        WorkflowDocumentRow(
            id=workflow_id,
            name="运行时测试工作流",
            document={"source": "webrpa", "format": "autoflow.webrpa/v1"},
            layout={},
            revision=3,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.flush()
    return repository.prepare_content(
        prepared_content_id=str(uuid4()),
        prepare_operation_id=operation_id or str(uuid4()),
        request_digest=digest,
        workflow_id=workflow_id,
        source_revision=3,
        checksum="b" * 64,
        document={"source": "webrpa", "format": "autoflow.webrpa/v1", "nodes": []},
        execution_plan={
            "orderedNodeIds": ["open"],
            "moduleTypes": ["open_page"],
        },
        adapter_version="webrpa-chain/v1",
        capability_requirements=["browser.cloakbrowser"],
        provenance={"kind": "workflowRevision", "revision": 3},
        created_at=NOW,
    )


def _prepare_run(repository, prepared_content_id, *, request_id=None, digest="c" * 64):
    return repository.prepare_run(
        run_id=str(uuid4()),
        run_request_id=request_id or str(uuid4()),
        request_digest=digest,
        prepared_content_id=prepared_content_id,
        parameters={"query": "温室", "count": 0, "enabled": False},
        input_snapshot_ref=None,
        resource_request={"profileId": None, "proxy": {"mode": "sourceDefault"}},
        capability_bindings=[
            {"capability": "browser.cloakbrowser", "provider": "local"}
        ],
        created_at=NOW,
    )


def test_repository_joins_the_callers_transaction_and_never_commits_it(tmp_path):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)

    with factory() as session:
        repository = _repository(session)
        prepared = _prepare_content(repository, session)
        run = _prepare_run(repository, prepared.prepared_content_id)
        session.flush()
        assert repository.get_run(run_id=run.run_id) == run
        session.rollback()

    with factory() as session:
        repository = _repository(session)
        assert repository.get_run(run_id=run.run_id) is None

        prepared = _prepare_content(repository, session)
        run = _prepare_run(repository, prepared.prepared_content_id)
        session.commit()

    with factory() as session:
        repository = _repository(session)
        persisted_content = repository.get_prepared_content(
            prepared_content_id=prepared.prepared_content_id
        )
        persisted = repository.get_run(run_id=run.run_id)
        assert thaw_json(persisted_content.execution_plan) == {
            "orderedNodeIds": ["open"],
            "moduleTypes": ["open_page"],
        }
        assert persisted_content.adapter_version == "webrpa-chain/v1"
        assert persisted == run
        assert persisted.status == "queued"
    factory.dispose()


def test_prepare_run_does_not_commit_an_outer_uow_started_by_a_read(tmp_path):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    with factory() as setup:
        repository = _repository(setup)
        prepared = _prepare_content(repository, setup)
        setup.commit()

    with factory() as session:
        session.scalar(select(WorkflowDocumentRow.id).limit(1))
        run = _prepare_run(_repository(session), prepared.prepared_content_id)
        session.rollback()

    with factory() as verify:
        assert _repository(verify).get_run(run_id=run.run_id) is None
    factory.dispose()


def test_prepare_content_and_run_are_idempotent_by_operation_identity_and_digest(
    tmp_path,
):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)

    with factory() as session:
        repository = _repository(session)
        operation_id = str(uuid4())
        prepared = _prepare_content(repository, session, operation_id=operation_id)
        replay = repository.prepare_content(
            prepared_content_id=str(uuid4()),
            prepare_operation_id=operation_id,
            request_digest="a" * 64,
            workflow_id=prepared.workflow_id,
            source_revision=prepared.source_revision,
            checksum=prepared.checksum,
            document=dict(prepared.document),
            execution_plan=dict(prepared.execution_plan),
            adapter_version=prepared.adapter_version,
            capability_requirements=list(prepared.capability_requirements),
            provenance=dict(prepared.provenance),
            created_at=NOW + timedelta(seconds=1),
        )
        assert replay == prepared
        assert (
            repository.get_prepared_content(prepare_operation_id=operation_id)
            == prepared
        )

        with pytest.raises(WorkflowRuntimeError) as caught:
            repository.prepare_content(
                prepared_content_id=str(uuid4()),
                prepare_operation_id=operation_id,
                request_digest="f" * 64,
                workflow_id=prepared.workflow_id,
                source_revision=prepared.source_revision,
                checksum=prepared.checksum,
                document=dict(prepared.document),
                execution_plan={"orderedNodeIds": ["different"]},
                adapter_version=prepared.adapter_version,
                capability_requirements=list(prepared.capability_requirements),
                provenance=dict(prepared.provenance),
                created_at=NOW,
            )
        assert caught.value.code == "OPERATION_PAYLOAD_MISMATCH"

        request_id = str(uuid4())
        run = _prepare_run(
            repository, prepared.prepared_content_id, request_id=request_id
        )
        replay_run = repository.prepare_run(
            run_id=str(uuid4()),
            run_request_id=request_id,
            request_digest="c" * 64,
            prepared_content_id=prepared.prepared_content_id,
            parameters={"query": "温室", "count": 0, "enabled": False},
            input_snapshot_ref=None,
            resource_request={"profileId": None, "proxy": {"mode": "sourceDefault"}},
            capability_bindings=[
                {"capability": "browser.cloakbrowser", "provider": "local"}
            ],
            created_at=NOW + timedelta(seconds=1),
        )
        assert replay_run == run
        assert repository.get_run(run_request_id=request_id) == run

        with pytest.raises(WorkflowRuntimeError) as caught:
            repository.prepare_run(
                run_id=str(uuid4()),
                run_request_id=request_id,
                request_digest="d" * 64,
                prepared_content_id=prepared.prepared_content_id,
                parameters={},
                input_snapshot_ref=None,
                resource_request={},
                capability_bindings=[],
                created_at=NOW,
            )
        assert caught.value.code == "RUN_REQUEST_CONFLICT"
        session.commit()
    factory.dispose()


def test_repository_enforces_cas_generation_event_order_and_duplicate_identity(
    tmp_path,
):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)

    with factory() as session:
        repository = _repository(session)
        prepared = _prepare_content(repository, session)
        queued = _prepare_run(repository, prepared.prepared_content_id)
        running = repository.transition_run(
            queued.run_id,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW + timedelta(seconds=1),
        )
        event = {
            "eventId": str(uuid4()),
            "runId": running.run_id,
            "executionGeneration": running.execution_generation,
            "kind": "log",
            "nodeId": "open",
            "nodeVisitId": "visit-1",
            "attempt": 1,
            "occurredAt": (NOW + timedelta(seconds=2)).isoformat(),
            "payload": {"level": "info", "message": "started"},
        }
        first = repository.append_event(event)
        duplicate = repository.append_event(event)
        assert first == duplicate
        assert first.sequence == 1
        assert first.node_id == "open"
        with pytest.raises(TypeError):
            first.payload["message"] = "changed"  # type: ignore[index]
        assert repository.get_run(run_id=running.run_id).last_sequence == 1
        assert repository.list_events(running.run_id, after_sequence=0, limit=20) == [
            first
        ]

        with pytest.raises(WorkflowRuntimeError) as caught:
            repository.transition_run(
                running.run_id,
                target_status="finishing",
                expected_status_revision=1,
                expected_execution_generation=running.execution_generation,
                now=NOW + timedelta(seconds=3),
            )
        assert caught.value.code == "RUN_STATUS_CONFLICT"

        with pytest.raises(WorkflowRuntimeError) as caught:
            repository.append_event(
                {
                    **event,
                    "eventId": str(uuid4()),
                    "sequence": 2,
                    "executionGeneration": running.execution_generation - 1,
                }
            )
        assert caught.value.code == "EXECUTION_GENERATION_REVOKED"

        with pytest.raises(WorkflowRuntimeError) as caught:
            repository.append_event(
                {
                    **event,
                    "eventId": str(uuid4()),
                    "sequence": 1,
                    "payload": {"level": "warning", "message": "competitor"},
                }
            )
        assert caught.value.code == "RUN_EVENT_SEQUENCE_CONFLICT"
        session.commit()
    factory.dispose()


def test_legacy_readonly_prepared_content_cannot_create_or_dispatch_a_run(tmp_path):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    with factory() as session:
        repository = _repository(session)
        legacy = _prepare_content(repository, session)
        prepared_row = session.get(
            WorkflowPreparedContentRow, legacy.prepared_content_id
        )
        assert prepared_row is not None
        prepared_row.adapter_version = "legacy-readonly/v1"
        prepared_row.execution_plan = {"replayable": False}
        session.flush()
        with pytest.raises(WorkflowRuntimeError) as caught:
            _prepare_run(repository, legacy.prepared_content_id)
        assert caught.value.code == "PREPARED_CONTENT_NOT_EXECUTABLE"

        current = _prepare_content(repository, session)
        queued = _prepare_run(repository, current.prepared_content_id)
        run_row = session.get(WorkflowRunRow, queued.run_id)
        assert run_row is not None
        run_row.prepared_content_id = legacy.prepared_content_id
        session.flush()
        with pytest.raises(WorkflowRuntimeError) as caught:
            repository.transition_run(
                queued.run_id,
                target_status="running",
                expected_status_revision=1,
                expected_execution_generation=0,
                now=NOW,
            )
        assert caught.value.code == "PREPARED_CONTENT_NOT_EXECUTABLE"
    factory.dispose()


def test_migrated_legacy_content_is_queryable_but_cannot_prepare_a_new_run(tmp_path):
    database = tmp_path / "legacy-runtime.sqlite3"
    config = _migration_config(database)
    command.upgrade(config, "0008_workflow_debug")
    _seed_one_legacy_run(database)
    command.upgrade(config, "head")
    factory = create_session_factory(database)
    runtime = WorkflowRuntimeService(factory)

    migrated_run = runtime.query_run(run_id="legacy-run")
    assert migrated_run is not None
    with factory() as session:
        prepared = _repository(session).get_prepared_content(
            prepared_content_id=migrated_run.prepared_content_id
        )
        assert prepared is not None
        assert prepared.adapter_version == "legacy-readonly/v1"
        assert prepared.execution_plan["replayable"] is False
        with pytest.raises(WorkflowRuntimeError) as caught:
            runtime.prepare_run(
                run_request_id=str(uuid4()),
                prepared_content_id=prepared.prepared_content_id,
                parameters={},
                input_snapshot_ref=None,
                resource_request={},
                capability_bindings=[],
                uow=session,
                created_at=NOW,
            )
        assert caught.value.code == "PREPARED_CONTENT_NOT_EXECUTABLE"
        with pytest.raises(WorkflowRuntimeError) as caught:
            runtime.dispatch_run(
                migrated_run.run_id,
                expected_status_revision=migrated_run.status_revision,
                execution_generation=migrated_run.execution_generation,
            )
        assert caught.value.code in {
            "PREPARED_CONTENT_NOT_EXECUTABLE",
            "RUN_TERMINAL",
        }
    factory.dispose()


def test_reconciliation_revokes_old_worker_and_offset_equivalent_retry_is_idempotent(
    tmp_path,
):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    with factory() as session:
        repository = _repository(session)
        prepared = _prepare_content(repository, session)
        queued = _prepare_run(repository, prepared.prepared_content_id)
        running = repository.transition_run(
            queued.run_id,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW,
        )
        event_id = str(uuid4())
        event = repository.append_event(
            {
                "eventId": event_id,
                "runId": running.run_id,
                "executionGeneration": 1,
                "kind": "log",
                "nodeId": "open",
                "occurredAt": "2026-09-14T18:00:00+08:00",
                "payload": {"message": "same instant"},
            }
        )
        retry = repository.append_event(
            {
                "eventId": event_id,
                "runId": running.run_id,
                "executionGeneration": 1,
                "kind": "log",
                "nodeId": "open",
                "occurredAt": "2026-09-14T10:00:00+00:00",
                "payload": {"message": "same instant"},
            }
        )
        assert retry == event
        assert event.occurred_at == NOW

        reconciling = repository.transition_run(
            running.run_id,
            target_status="reconciling",
            expected_status_revision=2,
            expected_execution_generation=1,
            now=NOW + timedelta(seconds=1),
        )
        assert reconciling.execution_generation == 2
        with pytest.raises(WorkflowRuntimeError) as caught:
            repository.append_event(
                {
                    "eventId": str(uuid4()),
                    "runId": running.run_id,
                    "executionGeneration": 1,
                    "kind": "output",
                    "occurredAt": NOW.isoformat(),
                    "payload": {"value": "late"},
                }
            )
        assert caught.value.code == "EXECUTION_GENERATION_REVOKED"
        session.commit()
    factory.dispose()


def test_transition_does_not_overwrite_a_concurrently_allocated_event_sequence(
    tmp_path,
):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    with factory() as setup:
        repository = _repository(setup)
        prepared = _prepare_content(repository, setup)
        queued = _prepare_run(repository, prepared.prepared_content_id)
        running = repository.transition_run(
            queued.run_id,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW,
        )
        setup.commit()

    with factory() as transition_session, factory() as event_session:
        transition_repository = _repository(transition_session)
        stale = transition_repository.get_run(run_id=running.run_id)
        assert stale.last_sequence == 0
        event_repository = _repository(event_session)
        event_repository.append_event(
            {
                "eventId": str(uuid4()),
                "runId": running.run_id,
                "executionGeneration": 1,
                "kind": "log",
                "occurredAt": NOW.isoformat(),
                "payload": {"message": "allocated concurrently"},
            }
        )
        event_session.commit()
        changed = transition_repository.transition_run(
            running.run_id,
            target_status="finishing",
            expected_status_revision=2,
            expected_execution_generation=1,
            now=NOW + timedelta(seconds=1),
        )
        transition_session.commit()
        assert changed.last_sequence == 1

    assert (
        WorkflowRuntimeService(factory).query_run(run_id=running.run_id).last_sequence
        == 1
    )
    factory.dispose()


def test_application_prepares_content_from_the_current_server_document_and_recovers_old_operation(
    tmp_path,
):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    workflows = SqlAlchemyWorkflowRepository(factory)
    documents = WorkflowService(workflows, clock=lambda: NOW)
    payload = workflow_payload()
    record = documents.create(payload, str(uuid4()))
    runtime = WorkflowRuntimeService(factory, workflows)
    operation_id = str(uuid4())

    prepared = runtime.prepare_content(
        prepare_operation_id=operation_id,
        workflow_id=record.workflow_id,
        source_revision=record.revision,
        available_capabilities=["browser.cloakbrowser"],
        created_at=NOW,
    )
    plan = thaw_json(prepared.execution_plan)
    assert prepared.adapter_version == "webrpa-chain/v1"
    assert plan["orderedNodeIds"] == ["open", "input", "click", "read"]
    assert plan["nodes"][0]["data"]["timeout"] == 60
    assert prepared.checksum

    changed = deepcopy(payload)
    changed["content"]["name"] = "工作流已在准备后修改"
    documents.save(record.workflow_id, changed, 1, str(uuid4()))
    recovered = runtime.prepare_content(
        prepare_operation_id=operation_id,
        workflow_id=record.workflow_id,
        source_revision=1,
        available_capabilities=["browser.cloakbrowser"],
    )
    assert recovered == prepared

    with pytest.raises(WorkflowRuntimeError) as caught:
        runtime.prepare_content(
            prepare_operation_id=operation_id,
            workflow_id=record.workflow_id,
            source_revision=2,
            available_capabilities=["browser.cloakbrowser"],
        )
    assert caught.value.code == "OPERATION_PAYLOAD_MISMATCH"
    factory.dispose()


def test_application_core_run_port_generates_identity_digest_and_obeys_caller_uow(
    tmp_path,
):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    workflows = SqlAlchemyWorkflowRepository(factory)
    record = WorkflowService(workflows, clock=lambda: NOW).create(
        workflow_payload(), str(uuid4())
    )
    runtime = WorkflowRuntimeService(factory, workflows)
    prepared = runtime.prepare_content(
        prepare_operation_id=str(uuid4()),
        workflow_id=record.workflow_id,
        source_revision=1,
        available_capabilities=["browser.cloakbrowser"],
        created_at=NOW,
    )
    request_id = str(uuid4())
    request = {
        "run_request_id": request_id,
        "prepared_content_id": prepared.prepared_content_id,
        "parameters": {"query": "温室"},
        "input_snapshot_ref": None,
        "resource_request": {"profileId": None},
        "capability_bindings": [
            {"capability": "browser.cloakbrowser", "provider": "local"}
        ],
        "created_at": NOW,
    }
    with factory() as session:
        run = runtime.prepare_run(**request, uow=session)
        assert run.run_id != request_id
        assert len(run.request_digest) == 64
        session.rollback()
    assert runtime.query_run(run_request_id=request_id) is None

    with factory() as session:
        run = runtime.prepare_run(**request, uow=session)
        session.commit()
    with factory() as session:
        replay = runtime.prepare_run(**request, uow=session)
        assert replay == run
        with pytest.raises(WorkflowRuntimeError) as caught:
            runtime.prepare_run(
                **{**request, "parameters": {"query": "另一请求"}},
                uow=session,
            )
        assert caught.value.code == "RUN_REQUEST_CONFLICT"
    factory.dispose()


def test_concurrent_prepare_content_and_run_recover_the_same_persisted_fact(tmp_path):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    workflows = SqlAlchemyWorkflowRepository(factory)
    record = WorkflowService(workflows, clock=lambda: NOW).create(
        workflow_payload(), str(uuid4())
    )
    runtime = WorkflowRuntimeService(factory, workflows)
    operation_id = str(uuid4())

    def prepare_content():
        return runtime.prepare_content(
            prepare_operation_id=operation_id,
            workflow_id=record.workflow_id,
            source_revision=1,
            available_capabilities=["browser.cloakbrowser"],
            created_at=NOW,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        contents = list(pool.map(lambda _: prepare_content(), range(2)))
    assert contents[0] == contents[1]

    request_id = str(uuid4())

    def prepare_run():
        with factory() as session:
            run = runtime.prepare_run(
                run_request_id=request_id,
                prepared_content_id=contents[0].prepared_content_id,
                parameters={"query": "温室"},
                input_snapshot_ref=None,
                resource_request={"profileId": None},
                capability_bindings=[],
                uow=session,
                created_at=NOW,
            )
            session.commit()
            return run

    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = list(pool.map(lambda _: prepare_run(), range(2)))
    assert runs[0] == runs[1]
    factory.dispose()


def test_concurrent_event_competition_never_leaks_a_database_error(tmp_path):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    with factory() as setup:
        repository = _repository(setup)
        prepared = _prepare_content(repository, setup)
        queued = _prepare_run(repository, prepared.prepared_content_id)
        running = repository.transition_run(
            queued.run_id,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW,
        )
        setup.commit()

    def append(index: int):
        with factory() as session:
            try:
                event = _repository(session).append_event(
                    {
                        "eventId": str(uuid4()),
                        "runId": running.run_id,
                        "executionGeneration": 1,
                        "kind": "log",
                        "occurredAt": NOW.isoformat(),
                        "payload": {"index": index},
                    }
                )
                session.commit()
                return event
            except WorkflowRuntimeError as error:
                session.rollback()
                return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        events = list(pool.map(append, range(2)))
    persisted = [
        event for event in events if not isinstance(event, WorkflowRuntimeError)
    ]
    conflicts = [event for event in events if isinstance(event, WorkflowRuntimeError)]
    assert sorted(event.sequence for event in persisted) == list(
        range(1, len(persisted) + 1)
    )
    assert persisted
    assert all(error.code == "RUN_EVENT_SEQUENCE_CONFLICT" for error in conflicts)
    with factory() as verify:
        assert _repository(verify).get_run(run_id=running.run_id).last_sequence == len(
            persisted
        )
    factory.dispose()


def test_force_stop_commit_revokes_a_concurrent_old_generation_event(tmp_path):
    database = tmp_path / "runtime.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    with factory() as setup:
        repository = _repository(setup)
        prepared = _prepare_content(repository, setup)
        queued = _prepare_run(repository, prepared.prepared_content_id)
        running = repository.transition_run(
            queued.run_id,
            target_status="running",
            expected_status_revision=1,
            expected_execution_generation=0,
            now=NOW,
        )
        setup.commit()

    started = Barrier(2)
    revoked = Barrier(2)

    def force_stop():
        with factory() as session:
            started.wait()
            changed = _repository(session).transition_run(
                running.run_id,
                target_status="reconciling",
                expected_status_revision=2,
                expected_execution_generation=1,
                now=NOW + timedelta(seconds=1),
            )
            session.commit()
            revoked.wait()
            return changed

    def append_old_event():
        with factory() as session:
            started.wait()
            revoked.wait()
            with pytest.raises(WorkflowRuntimeError) as caught:
                _repository(session).append_event(
                    {
                        "eventId": str(uuid4()),
                        "runId": running.run_id,
                        "executionGeneration": 1,
                        "kind": "log",
                        "occurredAt": NOW.isoformat(),
                        "payload": {"message": "late"},
                    }
                )
            return caught.value.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        stopped = pool.submit(force_stop)
        rejected = pool.submit(append_old_event)
        assert stopped.result().execution_generation == 2
        assert rejected.result() == "EXECUTION_GENERATION_REVOKED"
    factory.dispose()
