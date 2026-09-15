from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

StepName = Literal[
    "read_record:person",
    "clear_status:email",
    "set_status:email",
    "create_record:account",
    "query_records:account",
    "read_record:account",
    "update_record:account",
    "create_record:disposable",
    "read_record:disposable",
    "delete_record:disposable",
    "add_field:account",
    "ensure_field:account",
    "modify_field:account",
]
EventKind = Literal[
    "stepStarted",
    "stepSucceeded",
    "stepFailed",
    "ackLost",
    "operationRecovered",
    "operationMissing",
    "operationRetried",
    "paused",
    "resumed",
]

SET_EMAIL_STATUS: StepName = "set_status:email"
CREATE_ACCOUNT: StepName = "create_record:account"
READ_PERSON: StepName = "read_record:person"
CLEAR_EMAIL_STATUS: StepName = "clear_status:email"
QUERY_ACCOUNT: StepName = "query_records:account"
READ_ACCOUNT: StepName = "read_record:account"
UPDATE_ACCOUNT: StepName = "update_record:account"
CREATE_DISPOSABLE: StepName = "create_record:disposable"
READ_DISPOSABLE: StepName = "read_record:disposable"
DELETE_DISPOSABLE: StepName = "delete_record:disposable"
ADD_ACCOUNT_FIELD: StepName = "add_field:account"
ENSURE_ACCOUNT_FIELD: StepName = "ensure_field:account"
MODIFY_ACCOUNT_FIELD: StepName = "modify_field:account"
V1_STEPS = (SET_EMAIL_STATUS, CREATE_ACCOUNT)
B_STEPS = (
    READ_PERSON,
    CLEAR_EMAIL_STATUS,
    SET_EMAIL_STATUS,
    CREATE_ACCOUNT,
    QUERY_ACCOUNT,
    READ_ACCOUNT,
    UPDATE_ACCOUNT,
    CREATE_DISPOSABLE,
    READ_DISPOSABLE,
    DELETE_DISPOSABLE,
    ADD_ACCOUNT_FIELD,
    ENSURE_ACCOUNT_FIELD,
    MODIFY_ACCOUNT_FIELD,
)
STEPS = V1_STEPS

_CALLBACKS = {
    READ_PERSON: "read_person",
    CLEAR_EMAIL_STATUS: "clear_status",
    SET_EMAIL_STATUS: "set_status",
    CREATE_ACCOUNT: "create_record",
    QUERY_ACCOUNT: "query_account",
    READ_ACCOUNT: "read_account",
    UPDATE_ACCOUNT: "update_account",
    CREATE_DISPOSABLE: "create_disposable",
    READ_DISPOSABLE: "read_disposable",
    DELETE_DISPOSABLE: "delete_disposable",
    ADD_ACCOUNT_FIELD: "add_account_field",
    ENSURE_ACCOUNT_FIELD: "ensure_account_field",
    MODIFY_ACCOUNT_FIELD: "modify_account_field",
}


class AcknowledgementLost(Exception):
    """The capability may have committed, but its response was lost."""


@dataclass(frozen=True)
class FakeExecutionRequest:
    task_id: str
    run_id: str
    execution_generation: int
    inputs: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.task_id or not self.run_id or self.execution_generation < 0:
            raise ValueError("invalid fake execution identity")
        for name in ("person", "email"):
            if name not in self.inputs:
                raise ValueError(f"missing frozen input: {name}")
        object.__setattr__(self, "inputs", _freeze_mapping(self.inputs))


@dataclass(frozen=True)
class FakeExecutionEvent:
    sequence: int
    kind: EventKind
    step: StepName
    operation_id: str
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "kind": self.kind,
            "step": self.step,
            "operationId": self.operation_id,
            "details": _thaw(self.details),
        }


@dataclass(frozen=True)
class FakeExecutionResult:
    task_id: str
    run_id: str
    execution_generation: int
    status: Literal["succeeded", "failed"]
    events: tuple[FakeExecutionEvent, ...]
    outputs: Mapping[str, Any]
    error: Mapping[str, Any] | None
    executor: Literal["fake"] = "fake"
    browser: Literal["notExecuted"] = "notExecuted"
    studio: Literal["notExecuted"] = "notExecuted"

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "outputs", _freeze_mapping(self.outputs))
        if self.error is not None:
            object.__setattr__(self, "error", _freeze_mapping(self.error))

    def to_dict(self) -> dict[str, Any]:
        return {
            "executor": self.executor,
            "browser": self.browser,
            "studio": self.studio,
            "taskId": self.task_id,
            "runId": self.run_id,
            "executionGeneration": self.execution_generation,
            "status": self.status,
            "events": [event.to_dict() for event in self.events],
            "outputs": _thaw(self.outputs),
            "error": _thaw(self.error),
        }


class PauseBarrier:
    def __init__(self, *, before_step: StepName) -> None:
        if before_step not in STEPS:
            raise ValueError(f"unknown fake step: {before_step}")
        self.before_step = before_step
        self._reached = asyncio.Event()
        self._released = asyncio.Event()

    async def pause(self, step: StepName) -> bool:
        if step != self.before_step:
            return False
        self._reached.set()
        await self._released.wait()
        return True

    async def wait_until_reached(self) -> None:
        await self._reached.wait()

    def release(self) -> None:
        self._released.set()


class PM4FakeExecutor:
    """A QA-only deterministic script over real project capability callbacks."""

    def __init__(
        self,
        callbacks: Any,
        *,
        pause_barrier: PauseBarrier | None = None,
        fail_step: StepName | None = None,
        mode: Literal["v1", "b"] = "v1",
    ) -> None:
        self.steps = V1_STEPS if mode == "v1" else B_STEPS
        if fail_step is not None and fail_step not in self.steps:
            raise ValueError(f"unknown fake step: {fail_step}")
        self.callbacks = callbacks
        self.pause_barrier = pause_barrier
        self.fail_step = fail_step

    async def execute(self, request: FakeExecutionRequest) -> FakeExecutionResult:
        events: list[FakeExecutionEvent] = []
        outputs: dict[str, Any] = {}

        for step in self.steps:
            operation_id = stable_operation_id(
                request.task_id,
                request.run_id,
                request.execution_generation,
                step,
            )
            if self.pause_barrier is not None and step == self.pause_barrier.before_step:
                self._event(events, "paused", step, operation_id)
                await self.pause_barrier.pause(step)
                self._event(events, "resumed", step, operation_id)
            if step == self.fail_step:
                error = {
                    "code": "FAKE_STEP_FAILED",
                    "message": f"Injected failure before {step}",
                    "step": step,
                    "operationId": operation_id,
                }
                self._event(events, "stepFailed", step, operation_id, error=error)
                return self._result(request, "failed", events, outputs, error)

            self._event(events, "stepStarted", step, operation_id)
            try:
                result = await self._invoke(request, step, operation_id, events)
            except Exception as caught:  # noqa: BLE001 - fake reports callback failures
                error = {
                    "code": type(caught).__name__,
                    "message": str(caught),
                    "step": step,
                    "operationId": operation_id,
                }
                self._event(events, "stepFailed", step, operation_id, error=error)
                return self._result(request, "failed", events, outputs, error)

            output_name = {
                SET_EMAIL_STATUS: "emailStatus",
                CREATE_ACCOUNT: "account",
            }.get(step, step)
            outputs[output_name] = result
            self._event(events, "stepSucceeded", step, operation_id, result=result)

        return self._result(request, "succeeded", events, outputs, None)

    async def _invoke(
        self,
        request: FakeExecutionRequest,
        step: StepName,
        operation_id: str,
        events: list[FakeExecutionEvent],
    ) -> Any:
        identity = {
            "operation_id": operation_id,
            "task_id": request.task_id,
            "run_id": request.run_id,
            "execution_generation": request.execution_generation,
        }
        arguments = {
            **identity,
            "person": request.inputs["person"],
            "email": request.inputs["email"],
        }
        callback = getattr(self.callbacks, _CALLBACKS[step])

        for attempt in range(2):
            try:
                return await _await_if_needed(callback(**arguments))
            except AcknowledgementLost:
                self._event(events, "ackLost", step, operation_id)
                recovered = await _await_if_needed(
                    self.callbacks.query_operation(**identity)
                )
                if recovered is not None:
                    self._event(events, "operationRecovered", step, operation_id)
                    return recovered
                self._event(events, "operationMissing", step, operation_id)
                if attempt == 0:
                    self._event(events, "operationRetried", step, operation_id)
                    continue
                raise
        raise AssertionError("unreachable")

    @staticmethod
    def _event(
        events: list[FakeExecutionEvent],
        kind: EventKind,
        step: StepName,
        operation_id: str,
        **details: Any,
    ) -> None:
        events.append(
            FakeExecutionEvent(len(events) + 1, kind, step, operation_id, details)
        )

    @staticmethod
    def _result(
        request: FakeExecutionRequest,
        status: Literal["succeeded", "failed"],
        events: list[FakeExecutionEvent],
        outputs: dict[str, Any],
        error: dict[str, Any] | None,
    ) -> FakeExecutionResult:
        return FakeExecutionResult(
            request.task_id,
            request.run_id,
            request.execution_generation,
            status,
            tuple(events),
            outputs,
            error,
        )


def stable_operation_id(
    task_id: str, run_id: str, execution_generation: int, step: StepName
) -> str:
    identity = (
        f"autoflow:pm4-fake:{task_id}:{run_id}:{execution_generation}:{step}"
    )
    return str(uuid5(NAMESPACE_URL, identity))


async def _await_if_needed(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
