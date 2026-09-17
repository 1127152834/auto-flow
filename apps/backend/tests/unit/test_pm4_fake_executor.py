from __future__ import annotations

import asyncio

import pytest

from tests.qa.pm4_fake_executor import (
    AcknowledgementLost,
    FakeExecutionRequest,
    PauseBarrier,
    PM4FakeExecutor,
    stable_operation_id,
)


class CapabilityCallbacks:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.operations: dict[str, dict] = {}

    async def set_status(self, **request):
        self.calls.append(("set_status", request))
        result = {
            "recordRef": request["email"]["recordRef"],
            "status": "used",
        }
        self.operations[request["operation_id"]] = result
        return result

    async def create_record(self, **request):
        self.calls.append(("create_record", request))
        result = {
            "recordRef": {"tableId": "accounts", "recordKey": "account-1"},
            "values": {
                "person": request["person"]["values"]["name"],
                "email": request["email"]["values"]["address"],
            },
        }
        self.operations[request["operation_id"]] = result
        return result

    async def query_operation(self, **request):
        self.calls.append(("query_operation", request))
        return self.operations.get(request["operation_id"])


def request(*, generation: int = 4) -> FakeExecutionRequest:
    return FakeExecutionRequest(
        task_id="task-7",
        run_id="run-9",
        execution_generation=generation,
        inputs={
            "person": {
                "recordRef": {"tableId": "people", "recordKey": "person-1"},
                "values": {"name": "Alice"},
            },
            "email": {
                "recordRef": {"tableId": "emails", "recordKey": "email-1"},
                "values": {"address": "alice@example.test"},
            },
        },
    )


@pytest.mark.asyncio
async def test_executes_status_then_account_from_frozen_named_inputs():
    source = {
        "person": {
            "recordRef": {"tableId": "people", "recordKey": "person-1"},
            "values": {"name": "Alice"},
        },
        "email": {
            "recordRef": {"tableId": "emails", "recordKey": "email-1"},
            "values": {"address": "alice@example.test"},
        },
    }
    frozen = FakeExecutionRequest("task-7", "run-9", 4, source)
    source["person"]["values"]["name"] = "mutated"
    callbacks = CapabilityCallbacks()

    result = await PM4FakeExecutor(callbacks).execute(frozen)

    assert [name for name, _ in callbacks.calls] == ["set_status", "create_record"]
    assert callbacks.calls[0][1]["email"]["values"]["address"] == (
        "alice@example.test"
    )
    assert callbacks.calls[1][1]["person"]["values"]["name"] == "Alice"
    assert [call[1]["execution_generation"] for call in callbacks.calls] == [4, 4]
    assert result.to_dict() == {
        "executor": "fake",
        "browser": "notExecuted",
        "studio": "notExecuted",
        "taskId": "task-7",
        "runId": "run-9",
        "executionGeneration": 4,
        "status": "succeeded",
        "events": [
            {
                "sequence": 1,
                "kind": "stepStarted",
                "step": "set_status:email",
                "operationId": "9e3323aa-48c0-5b56-8bac-a4173f44702b",
                "details": {},
            },
            {
                "sequence": 2,
                "kind": "stepSucceeded",
                "step": "set_status:email",
                "operationId": "9e3323aa-48c0-5b56-8bac-a4173f44702b",
                "details": {
                    "result": {
                        "recordRef": {
                            "tableId": "emails",
                            "recordKey": "email-1",
                        },
                        "status": "used",
                    }
                },
            },
            {
                "sequence": 3,
                "kind": "stepStarted",
                "step": "create_record:account",
                "operationId": "42b3ed8c-5e7d-5435-a00e-ed2a3fcc3a8f",
                "details": {},
            },
            {
                "sequence": 4,
                "kind": "stepSucceeded",
                "step": "create_record:account",
                "operationId": "42b3ed8c-5e7d-5435-a00e-ed2a3fcc3a8f",
                "details": {
                    "result": {
                        "recordRef": {
                            "tableId": "accounts",
                            "recordKey": "account-1",
                        },
                        "values": {
                            "person": "Alice",
                            "email": "alice@example.test",
                        },
                    }
                },
            },
        ],
        "outputs": {
            "emailStatus": {
                "recordRef": {"tableId": "emails", "recordKey": "email-1"},
                "status": "used",
            },
            "account": {
                "recordRef": {"tableId": "accounts", "recordKey": "account-1"},
                "values": {
                    "person": "Alice",
                    "email": "alice@example.test",
                },
            },
        },
        "error": None,
    }


def test_operation_identity_uses_every_run_identity_field_and_step_name():
    assert stable_operation_id("task-7", "run-9", 4, "set_status:email") == (
        "9e3323aa-48c0-5b56-8bac-a4173f44702b"
    )
    identities = {
        stable_operation_id(task, run, generation, step)
        for task, run, generation, step in (
            ("task-7", "run-9", 4, "set_status:email"),
            ("task-8", "run-9", 4, "set_status:email"),
            ("task-7", "run-10", 4, "set_status:email"),
            ("task-7", "run-9", 5, "set_status:email"),
            ("task-7", "run-9", 4, "create_record:account"),
        )
    }
    assert len(identities) == 5


@pytest.mark.asyncio
async def test_lost_commit_ack_queries_the_same_operation_without_duplicate_create():
    callbacks = CapabilityCallbacks()
    create_calls = 0

    async def create_record(**call):
        nonlocal create_calls
        create_calls += 1
        callbacks.calls.append(("create_record", call))
        committed = {"recordRef": {"tableId": "accounts", "recordKey": "one"}}
        callbacks.operations[call["operation_id"]] = committed
        raise AcknowledgementLost("commit response was lost")

    callbacks.create_record = create_record

    result = await PM4FakeExecutor(callbacks).execute(request())

    create_operation_id = callbacks.calls[1][1]["operation_id"]
    assert create_calls == 1
    assert callbacks.calls[2] == (
        "query_operation",
        {
            "operation_id": create_operation_id,
            "task_id": "task-7",
            "run_id": "run-9",
            "execution_generation": 4,
        },
    )
    assert result.status == "succeeded"
    assert result.outputs["account"]["recordRef"]["recordKey"] == "one"
    assert [event.kind for event in result.events][-3:] == [
        "ackLost",
        "operationRecovered",
        "stepSucceeded",
    ]


@pytest.mark.asyncio
async def test_missing_operation_after_lost_ack_retries_with_the_original_identity():
    callbacks = CapabilityCallbacks()
    attempts: list[str] = []

    async def create_record(**call):
        attempts.append(call["operation_id"])
        if len(attempts) == 1:
            raise AcknowledgementLost("no durable result")
        return {"recordRef": {"tableId": "accounts", "recordKey": "retried"}}

    callbacks.create_record = create_record

    result = await PM4FakeExecutor(callbacks).execute(request())

    assert len(attempts) == 2 and attempts[0] == attempts[1]
    assert result.outputs["account"]["recordRef"]["recordKey"] == "retried"
    assert [event.kind for event in result.events][-4:] == [
        "ackLost",
        "operationMissing",
        "operationRetried",
        "stepSucceeded",
    ]


@pytest.mark.asyncio
async def test_pause_barrier_stops_before_the_selected_step_until_released():
    callbacks = CapabilityCallbacks()
    barrier = PauseBarrier(before_step="create_record:account")
    execution = asyncio.create_task(
        PM4FakeExecutor(callbacks, pause_barrier=barrier).execute(request())
    )

    await asyncio.wait_for(barrier.wait_until_reached(), timeout=1)
    assert [name for name, _ in callbacks.calls] == ["set_status"]
    assert not execution.done()

    barrier.release()
    result = await asyncio.wait_for(execution, timeout=1)
    assert result.status == "succeeded"
    assert [name for name, _ in callbacks.calls] == ["set_status", "create_record"]
    assert [event.kind for event in result.events][2:4] == ["paused", "resumed"]


@pytest.mark.asyncio
async def test_failure_before_second_step_keeps_the_first_committed_result():
    callbacks = CapabilityCallbacks()

    result = await PM4FakeExecutor(
        callbacks, fail_step="create_record:account"
    ).execute(request())

    assert [name for name, _ in callbacks.calls] == ["set_status"]
    assert result.status == "failed"
    assert result.outputs["emailStatus"]["status"] == "used"
    assert result.error == {
        "code": "FAKE_STEP_FAILED",
        "message": "Injected failure before create_record:account",
        "step": "create_record:account",
        "operationId": "42b3ed8c-5e7d-5435-a00e-ed2a3fcc3a8f",
    }


@pytest.mark.asyncio
async def test_real_callback_rejects_a_revoked_execution_generation():
    class ExecutionGenerationRevoked(Exception):
        pass

    callbacks = CapabilityCallbacks()

    async def set_status(**call):
        assert call["execution_generation"] == 3
        raise ExecutionGenerationRevoked("execution generation 3 is revoked")

    callbacks.set_status = set_status

    result = await PM4FakeExecutor(callbacks).execute(request(generation=3))

    assert result.status == "failed"
    assert callbacks.calls == []
    assert result.error == {
        "code": "ExecutionGenerationRevoked",
        "message": "execution generation 3 is revoked",
        "step": "set_status:email",
        "operationId": stable_operation_id(
            "task-7", "run-9", 3, "set_status:email"
        ),
    }


def test_requires_both_named_inputs_before_any_callback_can_run():
    with pytest.raises(ValueError, match="missing frozen input: email"):
        FakeExecutionRequest(
            "task-7",
            "run-9",
            4,
            {"person": {"recordRef": {"recordKey": "person-1"}}},
        )
