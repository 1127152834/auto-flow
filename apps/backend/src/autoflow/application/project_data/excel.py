"""Controlled Excel inspection, import, replacement and export use cases."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.excel import _digest, _invalid, _token_hash, _uuid
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_excel_common import (
    operation_view as _operation_view_from_row,
)
from autoflow.infrastructure.database.project_excel_inspections import (
    InspectionJob,
    SqlAlchemyProjectExcelInspections,
)
from autoflow.infrastructure.filesystem.project_excel import inspect_workbook


class ProjectExcelService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        workspace_id: str,
        instance_id: str,
        gate: Any | None = None,
    ):
        self._sessions = session_factory
        self._workspace_id = workspace_id
        self._instance_id = instance_id
        self._gate = gate
        self._inspections = SqlAlchemyProjectExcelInspections(
            session_factory, workspace_id, instance_id
        )

    def register_selection(self, payload: dict[str, Any], window_token: str) -> None:
        required = {
            "selectionToken",
            "path",
            "projectId",
            "windowId",
            "purpose",
            "expiresAt",
        }
        if set(payload) != required:
            raise _invalid("selection", "Unexpected or missing fields")
        token = _uuid(payload["selectionToken"], "selectionToken")
        project = _uuid(payload["projectId"], "projectId")
        purpose = payload["purpose"]
        if purpose not in {"inspectExcel", "exportXlsx"}:
            raise _invalid("purpose", "Invalid purpose")
        if type(payload["windowId"]) is not int or payload["windowId"] < 0:
            raise _invalid("windowId", "Must be a nonnegative integer")
        expires = payload["expiresAt"]
        if isinstance(expires, str):
            try:
                expires = datetime.fromisoformat(expires)
            except ValueError as error:
                raise _invalid("expiresAt", "Must be an ISO instant") from error
        if (
            not isinstance(expires, datetime)
            or expires.tzinfo is None
            or expires <= datetime.now(UTC)
        ):
            raise _invalid("expiresAt", "Must be a future instant")
        path = Path(payload["path"])
        if not isinstance(window_token, str) or len(window_token) < 32:
            raise ProjectError("UNAUTHORIZED", "Window authentication failed", 401)
        if not path.is_absolute():
            raise _invalid("path", "Must be absolute")
        self._inspections.register(
            {
                "token_hash": _token_hash(token),
                "path": str(path),
                "project_id": project,
                "window_id": payload["windowId"],
                "window_token_hash": _token_hash(window_token),
                "purpose": purpose,
                "expires_at": expires,
            }
        )

    def inspect(
        self,
        project_id: str,
        key: str,
        selection_token: str,
        window_id: int,
        window_token: str,
    ) -> dict[str, Any]:
        project_id, key, selection_token = (
            _uuid(project_id, "projectId"),
            _uuid(key, "Idempotency-Key"),
            _uuid(selection_token, "selectionToken"),
        )
        digest = _digest({"projectId": project_id, "selectionToken": selection_token})
        with self._mutation():
            operation, accepted = self._inspections.accept(
                project_id=project_id,
                key=key,
                digest=digest,
                token_hash=_token_hash(selection_token),
                window_id=window_id,
                window_token_hash=_token_hash(window_token),
            )
        if accepted is None:
            response = {"operation": _operation_view_from_row(operation)}
            if operation.result is not None:
                response["inspection"] = operation.result
            return response
        job = self._inspections.claim(accepted.operation_id)
        if job is None:
            return {"operation": _operation_view_from_row(operation)}
        return self._run_inspection(job)

    def _run_inspection(self, job: InspectionJob) -> dict[str, Any]:
        try:
            workbook = inspect_workbook(Path(job.path))
            snapshot = _inspection_snapshot(workbook, job.inspection_id, job.expires_at)
            with self._mutation():
                operation = self._inspections.complete(
                    job, snapshot, workbook.fingerprint
                )
            if operation is None:
                raise ProjectError(
                    "OPERATION_CLAIM_LOST", "Inspection claim was lost", 409
                )
            return {
                "operation": _operation_view_from_row(operation),
                "inspection": snapshot,
            }
        except Exception as error:
            failure = (
                error
                if isinstance(error, ProjectError)
                else ProjectError(
                    "EXCEL_INSPECTION_FAILED", "Excel inspection failed", 500
                )
            )
            with self._mutation():
                self._inspections.fail(
                    job.operation_id,
                    job.claim_token,
                    {
                        "code": failure.code,
                        "message": failure.message,
                        "details": failure.details,
                    },
                )
            if error is failure:
                raise
            raise failure from error

    def startup(self) -> None:
        for pending in self._inspections.pending():
            try:
                with self._mutation():
                    self._inspections.fail(
                        pending.operation_id,
                        None,
                        {
                            "code": "EXCEL_INSPECTION_INTERRUPTED",
                            "message": "Excel inspection was interrupted",
                            "details": {},
                        },
                    )
            except ProjectError:
                continue

    def shutdown(self) -> None:
        return None

    def pending_operations(self) -> list[str]:
        return [job.operation_id for job in self._inspections.pending()]

    def blockers(self) -> list[str]:
        return ["project_excel_operation_active"] if self.pending_operations() else []

    def _mutation(self):
        context = nullcontext(True) if self._gate is None else self._gate.mutation()

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


def _inspection_snapshot(
    workbook: Any, inspection_id: str, expires_at: datetime
) -> dict[str, Any]:
    return {
        "inspectionId": inspection_id,
        "fingerprint": workbook.fingerprint,
        "filename": workbook.filename,
        "expiresAt": _instant(expires_at),
        "sheets": [
            {
                "sheetId": sheet.sheet_id,
                "name": sheet.name,
                "headers": list(sheet.headers),
                "sample": [list(row) for row in sheet.sample],
                "rowCount": sheet.row_count,
                "ignoredEmptyRowCount": sheet.ignored_empty_row_count,
                "formulaRowCount": list(sheet.formula_row_count),
                "identityCandidates": [
                    index
                    for index, eligible in enumerate(sheet.identity_eligible)
                    if eligible
                ],
                "issues": list(sheet.issues),
            }
            for sheet in workbook.sheets
        ],
        "issues": [],
    }


def _instant(value: datetime) -> str:
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()
