"""The accept → do work → record evidence → complete envelope for sync commands.

Both bindings and outbound sending need the same shape, so it lives in one
place instead of being copied into each service.
"""

from __future__ import annotations

from typing import Any

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_sync import SqlAlchemyProjectSync


class SheetsRun:
    def __init__(self, sync: SqlAlchemyProjectSync) -> None:
        self._sync = sync

    # ---------------------------------------------------------------- repository

    def binding(self, project: str, table: str) -> dict[str, Any] | None:
        return self._sync.binding(project, table)

    def bind(self, project: str, table: str, **values: Any) -> dict[str, Any]:
        return self._sync.put_binding(project, table, **values)

    def summary(self, project: str, table: str) -> dict[str, Any]:
        return self._sync.summary_for_table(project, table)

    # ------------------------------------------------------------------- lifecycle

    def accept(
        self,
        *,
        project: str,
        table: str,
        kind: str,
        key: str,
        request: dict[str, Any],
        binding_epoch: int,
        dedupe: str,
        record_ref: dict[str, Any] | None = None,
        target_content_revision: int | None = None,
    ) -> tuple[dict[str, Any], bool]:
        result, existing = self._sync.accept(
            project=project,
            table=table,
            kind=kind,
            key=key,
            request=request,
            target={
                "spreadsheetId": request.get("spreadsheetId"),
                "sheetId": request.get("sheetId"),
            },
            dedupe_key=dedupe,
            binding_epoch=binding_epoch,
            record_ref=record_ref,
            target_content_revision=target_content_revision,
        )
        return result["operation"], existing

    def operation_view(self, operation_id: str) -> dict[str, Any]:
        return self._sync.operation_view(operation_id)

    def sync_view(self, operation_id: str) -> dict[str, Any]:
        return self._sync.sync_operation_by_id(operation_id)

    def confirm(
        self,
        operation_id: str,
        *,
        inspection: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        self._sync.transition(operation_id, status="confirmed", evidence=evidence)
        payload = result if result is not None else {}
        if inspection is not None:
            payload = {**payload, "inspection": inspection}
        self._sync.finish_operation(operation_id, payload)

    def fail(self, operation_id: str, error: ProjectError) -> None:
        payload = {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        }
        self._sync.transition(operation_id, status="failed", error=payload)
        self._sync.fail_operation(operation_id, payload)

    def complete(self, operation_id: str, result: dict[str, Any]) -> None:
        # The paired sync row must leave `pending` too, or the table would show a
        # queue entry for a command that already finished.
        self._sync.transition(operation_id, status="confirmed")
        self._sync.finish_operation(operation_id, result)
