"""Private credential replies in the actual project worker, with durable events."""
from __future__ import annotations

import asyncio
import json
from threading import Event

import pytest

from autoflow.domain.workflows.runtime import thaw_json
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from tests.integration.test_project_data_worker import (
    _dispatcher,
    _NoBrowserResources,
    _queued_pure_data_run,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["凭据", "cred"])
@pytest.mark.parametrize("value", ["private-lookup-key", "", None])
async def test_project_worker_reads_private_credential_after_start_commit(tmp_path, prefix, value):
    reference = "{{" + prefix + ":账号.password}}"
    factory, queued = _queued_pure_data_run(
        tmp_path,
        node_data={"moduleType": "dict_get_path", "dictVariable": "record", "path": reference, "resultVariable": "out"},
        variables={"record": {"private-lookup-key": "resolved", reference: "preserved"}},
    )
    reads = []

    def resolve(name):
        with factory() as session:
            events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(queued.run_id, after_sequence=0, limit=100)
        assert any(event.kind == "nodeAttempt" and event.payload.get("status") == "started" for event in events)
        reads.append(name)
        return {"password": value}

    worker = ProjectWorkflowWorkerManager(tmp_path / "temp", resolve_credential=resolve)
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        await dispatcher.dispatch(queued.run_id, expected_status_revision=queued.status_revision, execution_generation=queued.execution_generation)
        async with asyncio.timeout(15):
            await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            run = repository.get_run(run_id=queued.run_id)
            events = repository.list_events(queued.run_id, after_sequence=0, limit=100)
        assert run.status == ("failed" if value == "" else "succeeded")
        assert reads == ["账号"]
        outputs = [event.payload["value"] for event in events if event.kind == "output"]
        # Credential-derived variables stay private, including their output events.
        # Empty fields stay empty (invalid path); missing fields keep placeholders.
        assert outputs == []
        serialized = json.dumps([thaw_json(event.payload) for event in events])
        assert "private-lookup-key" not in serialized
        assert "credential:read" not in serialized
        assert "credential:result" not in serialized
        assert not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", ["{{cred:账号.}}", "{{cred:.password}}"])
async def test_project_empty_credential_parts_preserve_reference_without_protocol_failure(
    tmp_path, reference
):
    factory, queued = _queued_pure_data_run(
        tmp_path,
        node_data={
            "moduleType": "dict_get_path",
            "dictVariable": "record",
            "path": reference,
            "resultVariable": "out",
        },
        variables={"record": {reference: "preserved"}},
    )
    reads = []

    def resolve(name):
        reads.append(name)
        raise AssertionError("空凭据名称或字段不应进入凭据存储")

    worker = ProjectWorkflowWorkerManager(tmp_path / "temp", resolve_credential=resolve)
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        await dispatcher.dispatch(
            queued.run_id,
            expected_status_revision=queued.status_revision,
            execution_generation=queued.execution_generation,
        )
        async with asyncio.timeout(15):
            await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            run = repository.get_run(run_id=queued.run_id)
            events = repository.list_events(queued.run_id, after_sequence=0, limit=100)
        assert run.status == "succeeded"
        assert run.error is None
        assert reads == []
        assert [event.payload["status"] for event in events if event.kind == "nodeAttempt"] == [
            "started", "succeeded"
        ]
        # Successful lookup proves the original placeholder reached the executor;
        # the project sensitive-variable boundary suppresses public output events.
        assert [event.payload["value"] for event in events if event.kind == "output"] == []
        assert not any(
            event.kind == "status" and event.payload["status"] in {"reconciling", "interrupted"}
            for event in events
        )
        assert not worker.busy()
        assert not list((tmp_path / "temp" / "workflow-runs").glob("*/generation-*"))
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_project_sync_credential_read_obeys_node_timeout_without_output(tmp_path):
    factory, queued = _queued_pure_data_run(
        tmp_path,
        node_data={
            "moduleType": "dict_get_path",
            "dictVariable": "record",
            "path": "{{cred:账号.password}}",
            "resultVariable": "out",
            "timeout": 0.05,
        },
        variables={"record": {"lookup": "must-not-be-output"}},
    )
    reads = []
    finished = Event()

    def resolve(name):
        reads.append(name)
        try:
            Event().wait(0.25)
            return {"password": "lookup"}
        finally:
            finished.set()

    worker = ProjectWorkflowWorkerManager(tmp_path / "temp", resolve_credential=resolve)
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        await dispatcher.dispatch(
            queued.run_id,
            expected_status_revision=queued.status_revision,
            execution_generation=queued.execution_generation,
        )
        async with asyncio.timeout(15):
            await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            run = repository.get_run(run_id=queued.run_id)
            events = repository.list_events(queued.run_id, after_sequence=0, limit=100)
        assert run.status == "failed"
        assert reads == ["账号"]
        failures = [
            event for event in events
            if event.kind == "nodeAttempt" and event.payload.get("status") == "failed"
        ]
        assert len(failures) == 1
        assert failures[0].payload["error"]["code"] == "WORKFLOW_NODE_TIMEOUT"
        assert not any(event.kind == "output" for event in events)
        assert not worker.busy()
        assert not list((tmp_path / "temp" / "workflow-runs").glob("*/generation-*"))
    finally:
        await dispatcher.shutdown()
        if reads:
            assert await asyncio.to_thread(finished.wait, 1)
        factory.dispose()


@pytest.mark.asyncio
async def test_project_stop_unblocks_sync_credential_read_without_waiting_for_keychain(tmp_path):
    started, release = Event(), Event()
    factory, queued = _queued_pure_data_run(
        tmp_path,
        node_data={"moduleType": "dict_get_path", "dictVariable": "record", "path": "{{cred:账号.password}}", "resultVariable": "out"},
        variables={"record": {"never-release-this-secret": "unexpected"}},
    )

    def resolve(_name):
        started.set()
        release.wait(15)
        return {"password": "never-release-this-secret"}

    worker = ProjectWorkflowWorkerManager(tmp_path / "temp", resolve_credential=resolve)
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        run = await dispatcher.dispatch(queued.run_id, expected_status_revision=queued.status_revision, execution_generation=queued.execution_generation)
        async with asyncio.timeout(10):
            while not started.is_set():
                await asyncio.sleep(.01)
        async with asyncio.timeout(2):
            await dispatcher.cancel(run.run_id, expected_status_revision=run.status_revision, execution_generation=run.execution_generation)
            await dispatcher.wait_idle()
        assert not release.is_set()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            run = repository.get_run(run_id=queued.run_id)
            events = repository.list_events(queued.run_id, after_sequence=0, limit=100)
        assert run.status == "cancelled"
        assert not any(event.kind == "output" for event in events)
        assert "never-release-this-secret" not in json.dumps([thaw_json(event.payload) for event in events])
        assert not worker.busy()
    finally:
        release.set()
        await dispatcher.shutdown()
        factory.dispose()
