"""Explicit owned source columns on an existing binding; no implicit addField cloud write."""
from datetime import UTC, datetime
from typing import Any

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_sync import SqlAlchemyProjectSync
from autoflow.providers.data.google_sheets import SheetsApiError, column_letter, quoted

from .access import GoogleAccess
from .bindings import _api_error, _resolve_sheet, _table
from .connections import _uuid
from .runs import SheetsRun
from .system_identity import (
    IDENTITY_HEADER,
    identity_requests,
    owned_identity,
    source_digest,
)

COLUMN_METADATA = "autoflow.sourceColumn"


class SheetsColumnService:
    def __init__(self, sync: SqlAlchemyProjectSync, access: GoogleAccess, runs: SheetsRun) -> None:
        self._sync, self._access, self._runs = sync, access, runs

    def preview(self, project: str, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = _request(payload)
        return self._sync.impacts.preview_column(project, table, request)

    def operations(self, project: str, table: str, page: int, size: int) -> dict[str, Any]:
        with self._sync.sessions() as session:
            _table(session, project, table)
        return self._sync.sync_operations(table, None, page, size, kind="column")

    def create(self, project: str, table: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = {**_request({name:value for name,value in payload.items() if name != "impactRevision"}), "impactRevision":payload["impactRevision"]}
        with self._access.send_lock:
            view, existing = self._runs.accept(project=project, table=table, kind="createSheetsColumn", key=key, request=request, binding_epoch=request["expectedBindingEpoch"], dedupe=f"column:{key}")
            if existing:
                return {"operation":view}
            operation_id, plan = view["operationId"], None
            registered = False
            try:
                self._access.require_writable(project, request["connectionId"])
                client = self._access.client(project, request["connectionId"])
                _, sheet = _resolve_sheet(client, request)
                values = _values(client, request["spreadsheetId"], sheet.title, sheet.column_count)
                if values and request["columnName"] in values[0]:
                    raise ProjectError("SHEETS_COLUMN_OWNERSHIP", "已有同名来源列，不能自动接管。", 409)
                plan = {"sheetId":sheet.sheet_id, "sheetName":sheet.title, "columnIndex":sheet.column_count, "columnCount":sheet.column_count,
                        "columnId":column_letter(sheet.column_count), "owner":operation_id, "values":[request["columnName"]], "beforeDigest":source_digest(values)}
                self._sync.freeze_column(operation_id, plan)
                registered = True
                client.batch_update(request["spreadsheetId"], identity_requests(plan, sheet.column_count, metadata_key=COLUMN_METADATA))
            except SheetsApiError as error:
                self._send_error(operation_id, error, planned=plan is not None)
                return {"operation":self._runs.operation_view(operation_id)}
            except ProjectError as error:
                self._sync.transition(operation_id, status="failed", error={"code":error.code, "message":error.message, "unsent":not registered, "retryable":False})
                raise
            return self.verify(project, table, operation_id)

    def preview_original(self, project: str, table: str, operation: str) -> dict[str, Any]:
        row = self._sync.column_operation(project, table, operation)
        change = {key:value for key,value in row.request.items() if key not in {"impactRevision", "columnPlan"}}
        return self._sync.impacts.preview_column(project, table, change, own=operation)

    def verify(self, project: str, table: str, operation: str, confirmation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._access.send_lock:
            row = self._sync.column_operation(project, table, operation)
            if row.status == "confirmed" or (row.status == "failed" and (row.error or {}).get("unsent") is True):
                return {"operation":self._runs.operation_view(operation)}
            request, plan = row.request, row.request.get("columnPlan")
            if not plan:
                raise ProjectError("SHEETS_COLUMN_PLAN_MISSING", "原操作没有发送计划。", 409)
            client = self._access.client(project, request["connectionId"])
            _, sheet = _resolve_sheet(client, request)
            values = _values(client, request["spreadsheetId"], sheet.title, sheet.column_count)
            matched = sheet.title == plan["sheetName"] and owned_identity(plan, values[0] if values else [], _metadata(client, request["spreadsheetId"]), metadata_key=COLUMN_METADATA, name=request["columnName"])
            matched = matched and all(len(value) <= plan["columnIndex"] or value[plan["columnIndex"]] in (None, "") for value in values[1:])
            if not matched:
                self._sync.transition(operation, status="unknown", expected_status_revision=row.status_revision, error={"code":"SHEETS_COLUMN_EVIDENCE_MISMATCH", "message":"原列归属、表头或空列证据不匹配；不会重复创建或覆盖。"})
                return {"operation":self._runs.operation_view(operation)}
            self._sync.transition(operation, status="verifying", expected_status_revision=row.status_revision,
                                  evidence={"checkedAt":datetime.now(UTC).isoformat(), "target":request["spreadsheetId"], "fields":[request["fieldId"]], "outcome":"matched"})
            try:
                self._sync.publish_column(operation, confirmation or request)
            except ProjectError as error:
                self._sync.transition(operation, status="failed", keep_evidence=True, error={"code":error.code, "message":error.message})
                raise
            return {"operation":self._runs.operation_view(operation)}

    def retry(self, project: str, table: str, operation: str, confirmation: dict[str, Any]) -> dict[str, Any]:
        with self._access.send_lock:
            row = self._sync.column_operation(project, table, operation)
            request, plan = row.request, row.request.get("columnPlan")
            if row.status != "failed" or (row.error or {}).get("unsent") is not True or (row.error or {}).get("code") == "SYNC_ABANDONED" or not plan:
                raise ProjectError("SHEETS_COLUMN_RETRY_UNSAFE", "只有证明未发送且未取消的原计划允许重试。", 409)
            self._access.require_writable(project, request["connectionId"])
            client = self._access.client(project, request["connectionId"])
            _, sheet = _resolve_sheet(client, request)
            values = _values(client, request["spreadsheetId"], sheet.title, sheet.column_count)
            if sheet.title != plan["sheetName"] or sheet.column_count != plan["columnCount"] or source_digest(values) != plan["beforeDigest"]:
                raise ProjectError("SHEETS_COLUMN_EVIDENCE_MISMATCH", "来源已变化，不能重发旧列计划。", 409)
            self._sync.freeze_column(operation, plan, retry=True, confirmation=confirmation)
            try:
                client.batch_update(request["spreadsheetId"], identity_requests(plan, sheet.column_count, metadata_key=COLUMN_METADATA))
            except SheetsApiError as error:
                self._send_error(operation, error, planned=True)
                return {"operation":self._runs.operation_view(operation)}
            return self.verify(project, table, operation, confirmation)

    def cancel(self, project: str, table: str, operation: str, revision: int) -> dict[str, Any]:
        with self._access.send_lock:
            return self._sync.cancel_column(project, table, operation, revision)

    def _send_error(self, operation: str, error: SheetsApiError, *, planned: bool) -> None:
        self._sync.transition(operation, status="failed" if error.unsent or not planned else "unknown", error={"code":"SHEETS_COLUMN_SEND_UNCONFIRMED", "message":"来源列尚未确认，请核验原操作。", "unsent":error.unsent or not planned, "retryable":error.unsent and planned})


def _request(payload: dict[str, Any]) -> dict[str, Any]:
    required = {"fieldId", "columnName", "datasetGeneration", "connectionId", "spreadsheetId", "sheetId", "expectedBindingEpoch", "expectedTableRevision"}
    if set(payload) != required:
        raise ProjectError("INVALID_PROJECT_DATA", "来源列请求字段不完整。", 422)
    for field in ("fieldId", "datasetGeneration", "connectionId"):
        _uuid(payload[field], field)
    name = payload["columnName"]
    if not isinstance(name, str) or not name.strip() or len(name) > 200 or name == IDENTITY_HEADER:
        raise ProjectError("INVALID_PROJECT_DATA", "来源列名必须是 1–200 字且不能占用系统身份名。", 422)
    return {**payload, "columnName":name.strip()}


def _values(client: Any, spreadsheet: str, sheet: str, count: int) -> list[list[Any]]:
    try:
        return client.values(spreadsheet, f"{quoted(sheet)}!A:{column_letter(count-1)}", "FORMULA")
    except SheetsApiError as error:
        raise _api_error(error) from error


def _metadata(client: Any, spreadsheet: str) -> list[dict[str, Any]]:
    try:
        return client.developer_metadata(spreadsheet)
    except SheetsApiError as error:
        raise _api_error(error) from error
