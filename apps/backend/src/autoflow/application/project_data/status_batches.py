from __future__ import annotations

import logging
from concurrent.futures import Executor
from dataclasses import replace
from datetime import UTC, datetime
from threading import Event
from typing import Any, Protocol, cast

from autoflow.application.project_data.records import _ids, _nullable_uuid, _revision
from autoflow.application.project_data.tables import (
    _canonical_uuid,
    _operation,
    _validation,
)
from autoflow.domain.project_data.identity import (
    RecordKey,
    RecordKeyType,
    encode_record_key,
)
from autoflow.domain.project_data.status_batches import RecordStatusBatchRepository
from autoflow.domain.projects.models import ProjectOperation

logger = logging.getLogger(__name__)


class MutationGate(Protocol):
    def mutation(self): ...


class RecordStatusBatchCoordinator:
    def __init__(
        self,
        repository: RecordStatusBatchRepository,
        gate: MutationGate,
        executor: Executor,
    ):
        self.repository, self.gate, self.executor = repository, gate, executor
        self._stopping = Event()

    def submit(self, operation_id: str) -> None:
        future = self.executor.submit(self.run, operation_id)

        def report_failure(done) -> None:
            error = done.exception()
            if error is not None:
                logger.error(
                    "status batch worker failed operation_id=%s exception_type=%s",
                    operation_id,
                    type(error).__name__,
                )

        future.add_done_callback(report_failure)

    def run(self, operation_id: str) -> None:
        while True:
            for attempt in range(3):
                try:
                    with self.gate.mutation() as admitted:
                        if not admitted:
                            return
                        more = self.repository.process_block(operation_id)
                    break
                except Exception as error:  # noqa: BLE001 - worker boundary persists failure
                    if attempt == 2:
                        self.repository.fail(operation_id, error)
                        return
                    if self._stopping.wait(0.05 * (attempt + 1)):
                        return
            if not more:
                return

    def resume(self) -> None:
        for operation_id in self.repository.pending_operation_ids():
            self.submit(operation_id)

    def shutdown(self) -> None:
        self._stopping.set()


class RecordStatusBatchService:
    def __init__(
        self,
        repository: RecordStatusBatchRepository,
        coordinator: RecordStatusBatchCoordinator,
    ):
        self.repository, self.coordinator = repository, coordinator

    def preview(
        self, project_id: str, table_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        request = _request(project_id, table_id, payload)
        return self.repository.preview(project_id, table_id, request)

    def start(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> tuple[ProjectOperation, bool]:
        request = _request(project_id, table_id, payload)
        operation = _batch_operation(
            project_id,
            table_id,
            _canonical_uuid(key, "Idempotency-Key"),
            "setRecordStatuses",
            request,
        )
        accepted, replay = self.repository.accept(
            project_id, table_id, request, operation
        )
        if not replay and accepted.status == "accepted":
            self.coordinator.submit(accepted.operation_id)
        return accepted, replay

    def cancel(
        self,
        project_id: str,
        table_id: str,
        operation_id: str,
        key: str,
        payload: dict[str, Any],
    ) -> tuple[ProjectOperation, bool]:
        _ids(project_id, table_id)
        operation_id = _canonical_uuid(operation_id, "operationId")
        if not isinstance(payload, dict) or set(payload) != {
            "expectedOperationRevision"
        }:
            raise _validation("form", "Invalid cancellation request")
        expected = _revision(
            payload["expectedOperationRevision"], "expectedOperationRevision"
        )
        command = _batch_operation(
            project_id,
            table_id,
            _canonical_uuid(key, "Idempotency-Key"),
            "cancelRecordStatuses",
            {"operationId": operation_id, "expectedOperationRevision": expected},
        )
        return self.repository.cancel(
            project_id, table_id, operation_id, expected, command
        )


def _request(project_id: str, table_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _ids(project_id, table_id)
    if (
        not isinstance(payload, dict)
        or set(payload) - {"statusId", "targets", "blockSize"}
        or not {"statusId", "targets"}.issubset(payload)
    ):
        raise _validation("form", "Invalid batch status request")
    status_id = _nullable_uuid(payload["statusId"], "statusId")
    block_size = payload.get("blockSize", 100)
    if type(block_size) is not int or not 1 <= block_size <= 100:
        raise _validation("blockSize", "Must be between 1 and 100")
    raw = payload["targets"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= 1000:
        raise _validation("targets", "Must contain between 1 and 1000 records")
    targets: list[dict[str, Any]] = []
    seen: dict[tuple[str, str, str, str, str], int] = {}
    for item in raw:
        if (
            not isinstance(item, dict)
            or set(item) != {"recordRef", "expectedStatusRevision"}
            or not isinstance(item["recordRef"], dict)
        ):
            raise _validation("targets", "Invalid record target")
        ref = item["recordRef"]
        if (
            set(ref) != {"projectId", "tableId", "datasetGeneration", "recordKey"}
            or ref.get("projectId") != project_id
            or ref.get("tableId") != table_id
        ):
            raise _validation("targets", "Record target is outside the requested table")
        generation = _canonical_uuid(ref.get("datasetGeneration"), "datasetGeneration")
        key = ref.get("recordKey")
        if (
            not isinstance(key, dict)
            or set(key) != {"type", "value"}
            or key.get("type") not in {"text", "integer", "uuid"}
            or not isinstance(key.get("value"), str)
        ):
            raise _validation("targets", "Invalid record key")
        encode_record_key(RecordKey(cast(RecordKeyType, key["type"]), key["value"]))
        expected = _revision(item["expectedStatusRevision"], "expectedStatusRevision")
        identity = (project_id, table_id, generation, key["type"], key["value"])
        if identity in seen:
            if seen[identity] != expected:
                raise _validation(
                    "targets", "Duplicate target has different expected revisions"
                )
            continue
        seen[identity] = expected
        targets.append(
            {
                "recordRef": {
                    "projectId": project_id,
                    "tableId": table_id,
                    "datasetGeneration": generation,
                    "recordKey": key,
                },
                "expectedStatusRevision": expected,
            }
        )
    return {"statusId": status_id, "targets": targets, "blockSize": block_size}


def _batch_operation(
    project_id: str, table_id: str, key: str, kind: str, request: dict[str, Any]
) -> ProjectOperation:
    now = datetime.now(UTC)
    return replace(
        _operation(
            key,
            kind,
            {
                "scope": "table",
                "target": {"projectId": project_id, "tableId": table_id},
                "request": request,
            },
            project_id,
            table_id,
            now,
        ),
        status="accepted",
    )
