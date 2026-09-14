"""Asynchronous, restart-safe XLSX exports."""

from __future__ import annotations

import json
import threading
from concurrent.futures import Executor, Future
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from autoflow.domain.project_data.excel import _digest, _token_hash, _uuid
from autoflow.domain.project_data.query import decode_query
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_excel_exports import (
    ExportJob,
    SqlAlchemyProjectExcelExports,
)
from autoflow.infrastructure.filesystem.project_excel import (
    verify_workbook_publication,
    write_workbook,
)


class ProjectExcelExportService:
    def __init__(
        self, repository: SqlAlchemyProjectExcelExports, gate: Any, executor: Executor
    ):
        self.repository, self.gate, self.executor = repository, gate, executor
        self._stopping = threading.Event()

    def start(
        self,
        project_id: str,
        table_id: str,
        key: str,
        payload: dict[str, Any],
        window_id: int,
        window_token: str,
    ):
        project_id, table_id, key = (
            _uuid(project_id, "projectId"),
            _uuid(table_id, "tableId"),
            _uuid(key, "Idempotency-Key"),
        )
        request = _request(payload)
        digest = _digest(
            {"projectId": project_id, "tableId": table_id, "request": request}
        )
        with self._mutation():
            operation, job = self.repository.accept(
                project_id=project_id,
                table_id=table_id,
                key=key,
                digest=digest,
                token_hash=_token_hash(request["selectionToken"]),
                window_id=window_id,
                window_token_hash=_token_hash(window_token),
                request=request,
            )
        if job is not None:
            try:
                self._submit(job.operation_id)
            except Exception as cause:
                self.repository.fail(
                    job.operation_id,
                    {
                        "code": "EXCEL_EXPORT_EXECUTION_FAILED",
                        "message": "Excel export could not be scheduled",
                        "details": {},
                    },
                )
                raise ProjectError(
                    "EXCEL_EXPORT_EXECUTION_FAILED",
                    "Excel export could not be scheduled",
                    500,
                ) from cause
        return operation

    def _submit(self, operation_id: str) -> Future[Any]:
        if self._stopping.is_set():
            raise RuntimeError("export coordinator is stopping")
        return self.executor.submit(self._run, operation_id)

    def _run(self, operation_id: str) -> None:
        try:
            with self._mutation():
                job = self.repository.claim(operation_id)
            if job is None:
                return
            snapshot = self.repository.snapshot(job)
            try:
                write_workbook(
                    Path(job.path),
                    snapshot.headers,
                    snapshot.rows(),
                    before_publish=lambda p: self._prepare(job, p),
                )
            finally:
                snapshot.close()
            if self.repository.complete(job) is None:
                raise ProjectError("OPERATION_CLAIM_LOST", "Export claim was lost", 409)
        except Exception as cause:  # noqa: BLE001 -- persist every worker failure
            error = (
                cause
                if isinstance(cause, ProjectError)
                else ProjectError("EXCEL_EXPORT_FAILED", "Excel export failed", 500)
            )
            self.repository.fail(
                operation_id,
                {
                    "code": error.code,
                    "message": error.message,
                    "details": error.details,
                },
            )

    def _prepare(self, job: ExportJob, publication: Any) -> None:
        with self._mutation():
            self.repository.prepare(job, publication)

    def startup(self) -> None:
        for job in self.repository.pending():
            publication = self.repository.publication(job.operation_id)
            try:
                if (
                    job.claim_token
                    and publication
                    and publication.state == "publishing"
                    and publication.digest
                ):
                    outcome = verify_workbook_publication(
                        Path(publication.path), publication.digest
                    )
                    if outcome == "matches":
                        self.repository.complete(job)
                        continue
                    code = (
                        "EXCEL_EXPORT_TARGET_MISSING"
                        if outcome == "missing"
                        else "EXCEL_EXPORT_TARGET_CONFLICT"
                    )
                else:
                    code = "EXCEL_EXPORT_INTERRUPTED"
                if publication and publication.state == "publishing":
                    self.repository.fail_publication_recovery(job, outcome)
                else:
                    self.repository.fail(
                        job.operation_id,
                        {
                            "code": code,
                            "message": "Excel export was interrupted",
                            "details": {},
                        },
                    )
            except Exception:  # noqa: BLE001,S112 -- retain evidence for a later retry
                # Leave durable evidence pending for the next startup/reconcile attempt.
                continue
        for command_id, target_id in self.repository.pending_reconciliations():
            publication = self.repository.publication(target_id)
            recovery_outcome: str
            if publication is None or not publication.digest:
                recovery_outcome = "error"
            else:
                try:
                    recovery_outcome = verify_workbook_publication(
                        Path(publication.path), publication.digest
                    )
                except Exception:  # noqa: BLE001
                    recovery_outcome = "error"
            try:
                self.repository.finish_reconcile(
                    command_id, target_id, recovery_outcome
                )
            except ProjectError:
                continue

    def reconcile(
        self, project_id: str, operation_id: str, key: str, expected_revision: int
    ):
        project_id = _uuid(project_id, "projectId")
        operation_id = _uuid(operation_id, "operationId")
        key = _uuid(key, "Idempotency-Key")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ProjectError(
                "VALIDATION_ERROR", "Invalid expectedStatusRevision", 422
            )
        digest = _digest(
            {
                "projectId": project_id,
                "targetOperationId": operation_id,
                "expectedStatusRevision": expected_revision,
            }
        )
        with self._mutation():
            command, accepted = self.repository.accept_reconcile(
                project_id, operation_id, key, digest, expected_revision
            )
        if not accepted:
            return command
        publication = self.repository.publication(operation_id)
        assert publication and publication.digest
        outcome: str
        try:
            outcome = verify_workbook_publication(
                Path(publication.path), publication.digest
            )
        except Exception:  # noqa: BLE001 -- the durable command must reach a terminal state
            outcome = "error"
        return self.repository.finish_reconcile(command.id, operation_id, outcome)

    def pending_operations(self) -> list[str]:
        return [x.operation_id for x in self.repository.pending()] + [
            x[0] for x in self.repository.pending_reconciliations()
        ]

    def blockers(self) -> list[str]:
        return ["project_excel_operation_active"] if self.pending_operations() else []

    def shutdown(self) -> None:
        self._stopping.set()

    def _mutation(self):
        context = nullcontext(True) if self.gate is None else self.gate.mutation()

        class Guard:
            def __enter__(self):
                admitted = context.__enter__()
                if not admitted:
                    context.__exit__(None, None, None)
                    raise ProjectError(
                        "SETTINGS_QUIESCE_BLOCKED", "Mutations are paused", 423
                    )
                return admitted

            def __exit__(self, *args):
                return context.__exit__(*args)

        return Guard()


def _request(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "selectionToken",
        "datasetGeneration",
        "scope",
        "fieldIds",
        "includeStatus",
    }
    if not required <= set(payload) or set(payload) - required - {"filter", "orderBy"}:
        raise ProjectError("VALIDATION_ERROR", "Invalid export request", 422)
    token, generation = (
        _uuid(payload["selectionToken"], "selectionToken"),
        _uuid(payload["datasetGeneration"], "datasetGeneration"),
    )
    scope = payload["scope"]
    if (
        scope not in {"all", "filter"}
        or (scope == "all" and "filter" in payload)
        or (scope == "filter" and "filter" not in payload)
    ):
        raise ProjectError("VALIDATION_ERROR", "Invalid export scope", 422)
    fields = payload["fieldIds"]
    if (
        not isinstance(fields, list)
        or len(fields) > 500
        or any(not isinstance(x, str) for x in fields)
    ):
        raise ProjectError("VALIDATION_ERROR", "Invalid fieldIds", 422)
    fields = [_uuid(x, "fieldIds") for x in fields]
    if len(set(fields)) != len(fields):
        raise ProjectError("VALIDATION_ERROR", "Duplicate fieldIds", 422)
    if type(payload["includeStatus"]) is not bool:
        raise ProjectError("VALIDATION_ERROR", "Invalid includeStatus", 422)
    filter_value = decode_query(
        payload.get("filter") or _encoded({"type": "all", "items": []}), "filter"
    )
    order_value = decode_query(payload.get("orderBy") or _encoded([]), "orderBy")
    return {
        "selectionToken": token,
        "datasetGeneration": generation,
        "scope": scope,
        "filterValue": filter_value,
        "orderValue": order_value,
        "fieldIds": fields,
        "includeStatus": payload["includeStatus"],
    }


def _encoded(value: Any) -> str:
    import base64

    return (
        base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
