"""Source inspection, identity verification and table bindings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.project_data.tables import DataTableService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_sync import SqlAlchemyProjectSync
from autoflow.infrastructure.database.project_sync_models import SheetsBindingRow
from autoflow.providers.data.google_sheets import (
    SheetsApiError,
    SheetsClient,
    column_letter,
    column_range,
    quoted,
)

from .access import GoogleAccess
from .connections import _invalid, _uuid
from .runs import SheetsRun
from .system_identity import (
    canonical_uuid,
    identity_plan,
    identity_requests,
    owned_identity,
    source_digest,
    verify_identity,
)

MAX_MAPPING_ENTRIES = 200


class SheetsBindingService:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        runs: SheetsRun,
        access: GoogleAccess,
        tables: DataTableService,
        sync: SqlAlchemyProjectSync,
    ) -> None:
        self._sessions, self._runs, self._access = sessions, runs, access
        self._tables, self._sync = tables, sync

    # ------------------------------------------------------------------- inspection

    def inspect(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        request = _inspection_request(payload)
        with self._sessions() as session:
            table = _table(session, project_id, table_id)
            fields = _fields(session, table)
            epoch = _epoch(session, table_id)
            overlaps = _overlaps(session, project_id, request, table_id)
        client = self._access.client(project_id, request["connectionId"])
        inspection = _inspect_remote(client, request, fields, epoch, overlaps)
        view, existing = self._runs.accept(
            project=project_id,
            table=table_id,
            kind="inspectSheets",
            key=key,
            request=request,
            binding_epoch=epoch,
            dedupe=f"inspect:{key}",
        )
        if existing:
            return {"operation": view, "inspection": inspection}
        self._runs.confirm(view["operationId"], inspection=inspection)
        return {"operation": self._runs.operation_view(view["operationId"]), "inspection": inspection}

    # --------------------------------------------------------------------- binding

    def put_binding(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self._access.send_lock:
            request = _binding_request(payload)
            with self._sessions() as session:
                table = _table(session, project_id, table_id)
                fields = _fields(session, table)
                epoch = _epoch(session, table_id)
            identity_field_id = _validate_mapping(request, fields)
            self._access.require_writable(project_id, request["connectionId"])
            client = self._access.client(project_id, request["connectionId"])
            spreadsheet, sheet = _resolve_sheet(client, request)
            # A column that carries a formula stays read-only locally: the provider
            # copies the formula for appended rows and never writes one back
            # (DATA-SH-11), so the binding records the fact instead of letting a
            # later push overwrite the formula with a literal.
            formula_columns = _formula_columns(client, request["spreadsheetId"], sheet.title)
            system_plan = None
            if request["identityStrategy"]["kind"] == "system":
                system_plan = self._sync.known_system_identity(request["spreadsheetId"], sheet.sheet_id, request["identityStrategy"]["columnId"])
                values = client.values(request["spreadsheetId"], f"{quoted(sheet.title)}!A:{column_letter(sheet.column_count - 1)}", "FORMULA")
                column = system_plan["columnIndex"]
                keys = [row[column] if column < len(row) else None for row in values[1:] if any(value not in (None, "") for value in row)]
                if not owned_identity(system_plan, values[0] if values else [], client.developer_metadata(request["spreadsheetId"])) or not all(canonical_uuid(value) for value in keys) or len(set(keys)) != len(keys):
                    raise ProjectError("SHEETS_IDENTITY_UNVERIFIED", "已有系统列归属或 UUID 不完整，不能复用或覆盖。", 409)
            view, existing = self._runs.accept(
                project=project_id,
                table=table_id,
                kind="changeSheetsBinding",
                key=key,
                request=request,
                binding_epoch=epoch,
                dedupe=f"binding:{key}",
            )
            if existing:
                return {"operation": view}
            operation_id = view["operationId"]
            try:
                # `filename` is the shared display name for a table source; Sheets
                # uses the spreadsheet title so the source tab can show it.
                source = {
                    "sheetName": sheet.title,
                    "spreadsheetTitle": spreadsheet.title,
                    "filename": spreadsheet.title,
                }
                binding = self._runs.bind(
                    project_id,
                    table_id,
                    connection_id=request["connectionId"],
                    spreadsheet_id=request["spreadsheetId"],
                    sheet_id=request["sheetId"],
                    spreadsheet_title=spreadsheet.title,
                    sheet_name=sheet.title,
                    identity_strategy=request["identityStrategy"],
                    mapping=request["mapping"],
                    expected_table_revision=request["expectedTableRevision"],
                    expected_binding_epoch=request["expectedBindingEpoch"],
                    source=source,
                    impact_revision=request["impactRevision"],
                    identity_field_id=identity_field_id,
                    system_identity_plan=system_plan,
                    formula_columns=sorted(formula_columns),
                )
            except ProjectError as error:
                self._runs.fail(operation_id, error)
                raise
            self._runs.complete(operation_id, binding)
            return {"operation": self._runs.operation_view(operation_id)}

    def initialize_identity(self, project_id: str, table_id: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._access.send_lock:
            request = _binding_request(payload)
            if request["identityStrategy"]["kind"] != "system":
                raise _invalid("identityStrategy", "初始化必须选择系统身份。")
            with self._sessions() as session:
                table = _table(session, project_id, table_id)
                fields = _fields(session, table)
                epoch = _epoch(session, table_id)
            _validate_mapping(request, fields)
            view, existing = self._runs.accept(project=project_id, table=table_id, kind="initializeSheetsIdentity", key=key, request=request, binding_epoch=epoch, dedupe=f"systemIdentity:{key}")
            if existing:
                return {"operation": view}
            operation_id = view["operationId"]
            plan = None
            try:
                self._access.require_writable(project_id, request["connectionId"])
                client = self._access.client(project_id, request["connectionId"])
                spreadsheet, sheet = _resolve_sheet(client, request)
                values = client.values(request["spreadsheetId"], f"{quoted(sheet.title)}!A:{column_letter(sheet.column_count - 1)}", "FORMULA")
                plan = identity_plan(values, column=_column_index(request["identityStrategy"]["columnId"]), sheet_id=sheet.sheet_id, owner=operation_id)
                plan.update(columnCount=sheet.column_count, sheetName=sheet.title, spreadsheetTitle=spreadsheet.title, formulaColumns=sorted(_formula_columns(client, request["spreadsheetId"], sheet.title)))
                writes = identity_requests(plan, sheet.column_count)
                self._sync.freeze_identity(operation_id, plan)
                client.batch_update(request["spreadsheetId"], writes)
            except SheetsApiError as error:
                self._sync.transition(operation_id, status="failed" if error.unsent or plan is None else "unknown", error={"code": "SHEETS_IDENTITY_SEND_UNCONFIRMED", "message": "初始化未确认，请核验原操作。", "retryable": error.unsent and plan is not None, "unsent": error.unsent or plan is None})
                return {"operation": self._runs.operation_view(operation_id)}
            except ProjectError as error:
                self._runs.fail(operation_id, error)
                raise
            return self.verify_identity(project_id, table_id, operation_id)

    def retry_identity(self, project_id: str, table_id: str, operation_id: str, confirmation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._access.send_lock:
            frozen = self._sync.identity_operation(project_id, table_id, operation_id)
            if frozen.status != "failed" or (frozen.error or {}).get("unsent") is not True:
                raise ProjectError("SHEETS_IDENTITY_RETRY_UNSAFE", "原请求可能已发送，只能核验，不能再次创建列。", 409)
            request, plan = frozen.request, frozen.request.get("initialization")
            if not plan:
                raise ProjectError("SHEETS_IDENTITY_PLAN_MISSING", "未形成发送计划，请重新检查来源后发起初始化。", 409)
            self._access.require_writable(project_id, request["connectionId"])
            client = self._access.client(project_id, request["connectionId"])
            _, sheet = _resolve_sheet(client, request)
            values = client.values(request["spreadsheetId"], f"{quoted(sheet.title)}!A:{column_letter(sheet.column_count - 1)}", "FORMULA")
            if sheet.title != plan["sheetName"] or sheet.column_count != plan["columnCount"] or source_digest(values) != plan["beforeDigest"]:
                raise ProjectError("SHEETS_IDENTITY_EVIDENCE_MISMATCH", "来源已变化，原计划不能重发。", 409)
            self._sync.freeze_identity(operation_id, plan, retry=True, confirmation=confirmation)
            try:
                client.batch_update(request["spreadsheetId"], identity_requests(plan, sheet.column_count))
            except SheetsApiError as error:
                self._sync.transition(operation_id, status="failed" if error.unsent else "unknown", error={"code": "SHEETS_IDENTITY_SEND_UNCONFIRMED", "message": "原初始化尚未确认。", "unsent": error.unsent, "retryable": error.unsent})
                return {"operation": self._runs.operation_view(operation_id)}
            return self.verify_identity(project_id, table_id, operation_id, confirmation)

    def preview_identity(self, project_id: str, table_id: str, operation_id: str) -> dict[str, Any]:
        frozen = self._sync.identity_operation(project_id, table_id, operation_id)
        change = {key: frozen.request[key] for key in ("connectionId", "spreadsheetId", "sheetId", "identityStrategy", "mapping")}
        return self._sync.impacts.preview_binding(project_id, table_id, change, own=operation_id)

    def verify_identity(self, project_id: str, table_id: str, operation_id: str, confirmation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._access.send_lock:
            frozen = self._sync.identity_operation(project_id, table_id, operation_id)
            if frozen.status == "confirmed" or (frozen.status == "failed" and (frozen.error or {}).get("unsent") is True):
                return {"operation": self._runs.operation_view(operation_id)}
            request, plan = frozen.request, frozen.request.get("initialization")
            confirmation = confirmation or {"expectedTableRevision": request["expectedTableRevision"], "impactRevision": request["impactRevision"]}
            with self._sessions() as session:
                local = _table(session, project_id, table_id)
                _validate_mapping(request, _fields(session, local))
            if not plan:
                raise ProjectError("SHEETS_IDENTITY_PLAN_MISSING", "原操作尚未生成初始化计划。", 409)
            client = self._access.client(project_id, request["connectionId"])
            try:
                _, sheet = _resolve_sheet(client, request)
                values = client.values(request["spreadsheetId"], f"{quoted(sheet.title)}!A:{column_letter(sheet.column_count - 1)}", "FORMULA")
                metadata = client.developer_metadata(request["spreadsheetId"])
                matched = sheet.title == plan["sheetName"] and verify_identity(plan, values, metadata)
            except SheetsApiError as error:
                raise _api_error(error) from error
            if not matched:
                self._sync.transition(operation_id, status="unknown", expected_status_revision=frozen.status_revision, error={"code": "SHEETS_IDENTITY_EVIDENCE_MISMATCH", "message": "原身份列、UUID 或行内容尚不能完整核验；不会再次创建或写入。"})
                return {"operation": self._runs.operation_view(operation_id)}
            self._sync.transition(operation_id, status="verifying", expected_status_revision=frozen.status_revision, evidence={"checkedAt": datetime.now(UTC).isoformat(), "target": request["spreadsheetId"], "fields": [request["identityStrategy"]["columnId"]], "outcome": "matched"})
            try:
                self._runs.bind(project_id, table_id,
                    connection_id=request["connectionId"], spreadsheet_id=request["spreadsheetId"], sheet_id=request["sheetId"],
                    spreadsheet_title=plan["spreadsheetTitle"], sheet_name=plan["sheetName"], identity_strategy=request["identityStrategy"], mapping=request["mapping"],
                    expected_table_revision=confirmation["expectedTableRevision"], expected_binding_epoch=request["expectedBindingEpoch"], impact_revision=confirmation["impactRevision"],
                    source={"sheetName": plan["sheetName"], "spreadsheetTitle": plan["spreadsheetTitle"], "filename": plan["spreadsheetTitle"]},
                    formula_columns=plan["formulaColumns"], initialization_operation_id=operation_id, system_identity_plan=plan)
            except ProjectError as error:
                self._sync.transition(operation_id, status="failed", error={"code": error.code, "message": error.message}, keep_evidence=True)
                raise
            return {"operation": self._runs.operation_view(operation_id)}

    def delete_binding(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self._access.send_lock:
            if set(payload) != {"impactRevision", "expectedTableRevision"}:
                raise _invalid("payload", "意外的字段")
            _uuid(project_id, "projectId")
            _uuid(table_id, "tableId")
            _uuid(key, "Idempotency-Key")
            impact = _revision(payload["impactRevision"], "impactRevision")
            expected = _revision(
                payload["expectedTableRevision"], "expectedTableRevision"
            )
            with self._sessions() as session:
                _table(session, project_id, table_id)
            view, existing = self._runs.accept(
                project=project_id,
                table=table_id,
                kind="removeSheetsBinding",
                key=key,
                request={
                    "tableId": table_id,
                    "impactRevision": impact,
                    "expectedTableRevision": expected,
                },
                binding_epoch=_epoch_for(self._sessions, project_id, table_id),
                dedupe=f"unbind:{key}",
            )
            if existing:
                return {"operation": view}
            operation_id = view["operationId"]
            try:
                # The confirmation is re-derived inside the delete transaction, so a
                # binding change in between is reported instead of silently removed.
                self._runs.unbind(project_id, table_id, expected, impact)
                result = {
                    "table": self._tables.get(project_id, table_id),
                    "unbound": True,
                }
            except ProjectError as error:
                self._runs.fail(operation_id, error)
                raise
            self._runs.complete(operation_id, result)
            return {"operation": self._runs.operation_view(operation_id)}

    def read_binding(self, project_id: str, table_id: str) -> dict[str, Any] | None:
        with self._sessions() as session:
            _table(session, project_id, table_id)
        binding = self._runs.binding(project_id, table_id)
        if binding is None:
            return None
        return binding


def _epoch_for(
    sessions: sessionmaker[Session], project_id: str, table_id: str
) -> int:
    with sessions() as session:
        return _epoch(session, table_id)


def _table(session: Session, project_id: str, table_id: str) -> DataTableRow:
    _uuid(project_id, "projectId")
    _uuid(table_id, "tableId")
    table = session.get(DataTableRow, table_id)
    if table is None or table.project_id != project_id or not table.published:
        raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
    return table


def _fields(session: Session, table: DataTableRow) -> list[DataFieldRow]:
    return list(
        session.scalars(
            select(DataFieldRow)
            .where(
                DataFieldRow.table_id == table.id,
                DataFieldRow.dataset_generation == table.current_generation,
            )
            .order_by(DataFieldRow.position)
        ).all()
    )


def _epoch(session: Session, table_id: str) -> int:
    row = session.get(SheetsBindingRow, table_id)
    return row.binding_epoch if row else 0


def _overlaps(
    session: Session, project_id: str, request: dict[str, Any], table_id: str
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(SheetsBindingRow).where(
            SheetsBindingRow.spreadsheet_id == request["spreadsheetId"],
            SheetsBindingRow.table_id != table_id,
        )
    ).all()
    mine = {entry["columnId"] for entry in request["mapping"]}
    overlaps = []
    for row in rows:
        shared = sorted(
            mine & {entry.get("columnId") for entry in row.mapping if entry.get("columnId")}
        )
        if shared:
            overlaps.append(
                {
                    "projectId": row.project_id,
                    "tableId": row.table_id,
                    "columnIds": shared,
                }
            )
    return overlaps


def _inspection_request(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "connectionId",
        "spreadsheetId",
        "sheetId",
        "identityStrategy",
        "mapping",
    }
    if set(payload) != required:
        raise _invalid("payload", "意外的字段")
    return {
        "connectionId": _uuid(payload["connectionId"], "connectionId"),
        "spreadsheetId": _spreadsheet_id(payload["spreadsheetId"]),
        "sheetId": _sheet_id(payload["sheetId"]),
        "identityStrategy": _identity(payload["identityStrategy"]),
        "mapping": _mapping(payload["mapping"]),
    }


def _binding_request(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "connectionId",
        "spreadsheetId",
        "sheetId",
        "identityStrategy",
        "mapping",
        "impactRevision",
        "expectedTableRevision",
    }
    allowed = required | {"expectedBindingEpoch"}
    if set(payload) - {"expectedBindingEpoch"} != required or set(payload) - allowed:
        raise _invalid("payload", "意外的字段")
    request = _inspection_request(
        {
            key: payload[key]
            for key in (
                "connectionId",
                "spreadsheetId",
                "sheetId",
                "identityStrategy",
                "mapping",
            )
        }
    )
    request["expectedTableRevision"] = _revision(
        payload["expectedTableRevision"], "expectedTableRevision"
    )
    request["impactRevision"] = _revision(payload["impactRevision"], "impactRevision")
    request["expectedBindingEpoch"] = (
        None
        if payload.get("expectedBindingEpoch") is None
        else _revision(payload["expectedBindingEpoch"], "expectedBindingEpoch")
    )
    return request


def _spreadsheet_id(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 256 or "/" in value:
        raise _invalid("spreadsheetId", "spreadsheetId 格式不正确")
    return value


def _sheet_id(value: Any) -> int:
    if type(value) is not int or value < 0 or value > 2**53 - 1:
        raise _invalid("sheetId", "sheetId 必须是 JSON 安全整数")
    return value


def _revision(value: Any, field: str) -> int:
    if type(value) is not int or value < 1:
        raise _invalid(field, "必须是正整数")
    return value


def _identity(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("kind") not in {"column", "system"}:
        raise _invalid("identityStrategy", "身份策略必须是 column 或 system")
    kind = value["kind"]
    column_id = value.get("columnId")
    if not isinstance(column_id, str) or not column_id:
        raise _invalid("identityStrategy", "按列识别身份时必须指定 columnId")
    return {"kind": kind, "columnId": column_id}


def _mapping(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_MAPPING_ENTRIES:
        raise _invalid("mapping", "映射必须是 1–200 条")
    entries, seen = [], set()
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != {
            "fieldId",
            "columnId",
            "direction",
            "formula",
        }:
            raise _invalid("mapping", "映射条目字段不正确")
        field_id = _uuid(raw["fieldId"], "fieldId")
        column_id = raw["columnId"]
        if not isinstance(column_id, str) or not column_id or len(column_id) > 8:
            raise _invalid("mapping", "columnId 必须是 A1 列标识")
        if raw["direction"] not in {"read", "write", "both"}:
            raise _invalid("mapping", "direction 不受支持")
        if type(raw["formula"]) is not bool:
            raise _invalid("mapping", "formula 必须是布尔值")
        # Normalise before the duplicate check: `b` and `B` address the same
        # source column, so accepting both would leave the identity lookup in
        # `_validate_mapping` reading whichever entry came first.
        column_id = column_id.upper()
        if column_id in seen:
            raise _invalid("mapping", "同一来源列不能被映射两次")
        seen.add(column_id)
        entries.append(
            {
                "fieldId": field_id,
                "columnId": column_id,
                "direction": raw["direction"],
                "formula": raw["formula"],
            }
        )
    return entries


def _validate_mapping(
    request: dict[str, Any], fields: list[DataFieldRow]
) -> str | None:
    """Validate the mapping and resolve the local identity field."""
    by_id = {field.id: field for field in fields}
    for entry in request["mapping"]:
        field = by_id.get(entry["fieldId"])
        if field is None:
            raise ProjectError(
                "SHEETS_MAPPING_UNKNOWN_FIELD",
                "映射引用了本表不存在的字段。",
                422,
                {"fieldId": entry["fieldId"]},
            )
        if entry["direction"] in {"write", "both"} and (
            not field.writable or field.formula
        ):
            raise ProjectError(
                "SHEETS_MAPPING_NOT_WRITABLE",
                "公式或只读字段不能被写入来源。",
                422,
                {"fieldId": field.id},
            )
    identity = request["identityStrategy"]
    if identity["kind"] == "system":
        if any(entry["columnId"] == identity["columnId"] for entry in request["mapping"]):
            raise _invalid("mapping", "系统身份列不可映射为业务字段。")
        return None
    entry = next(
        (
            item
            for item in request["mapping"]
            if item["columnId"] == identity["columnId"]
        ),
        None,
    )
    if entry is None or entry["direction"] == "write":
        raise ProjectError(
            "SHEETS_IDENTITY_NOT_MAPPED",
            "按列识别身份时必须把该列映射到一个文本字段。",
            422,
            {"columnId": identity["columnId"]},
        )
    field = by_id[entry["fieldId"]]
    if field.type != "string":
        raise ProjectError(
            "SHEETS_IDENTITY_NOT_TEXT",
            "身份字段必须是文本类型，才能保留前导零等内容差异。",
            422,
            {"fieldId": field.id},
        )
    return field.id


def _resolve_sheet(client: SheetsClient, request: dict[str, Any]) -> tuple[Any, Any]:
    try:
        spreadsheet = client.metadata(request["spreadsheetId"])
    except SheetsApiError as error:
        raise _api_error(error) from error
    sheet = spreadsheet.sheet(request["sheetId"])
    if sheet is None:
        raise ProjectError(
            "SHEETS_WORKSHEET_NOT_FOUND", "该 Spreadsheet 中找不到指定的工作表。", 404
        )
    return spreadsheet, sheet


def _formula_columns(
    client: SheetsClient, spreadsheet_id: str, sheet_name: str
) -> set[str]:
    """Which source columns carry a formula in their data rows.

    Read with the FORMULA render so an unevaluated formula is still recognised;
    only the data rows count, so a header that merely looks like text is not a
    formula column.
    """
    try:
        grid = client.values(
            spreadsheet_id, f"{quoted(sheet_name)}!A:ZZ", "FORMULA"
        )
    except SheetsApiError as error:
        raise _api_error(error) from error
    columns: set[str] = set()
    for row in grid[1:]:
        for index, cell in enumerate(row):
            if isinstance(cell, str) and cell.startswith("="):
                columns.add(column_letter(index))
    return columns


def _inspect_remote(
    client: SheetsClient,
    request: dict[str, Any],
    fields: list[DataFieldRow],
    epoch: int,
    overlaps: list[dict[str, Any]],
) -> dict[str, Any]:
    spreadsheet, sheet = _resolve_sheet(client, request)
    try:
        header = client.values(
            request["spreadsheetId"], f"{quoted(sheet.title)}!1:1", "FORMULA"
        )
    except SheetsApiError as error:
        raise _api_error(error) from error
    titles = [str(cell) for cell in (header[0] if header else [])]
    issues: list[dict[str, Any]] = []
    formulas = _formula_columns(client, request["spreadsheetId"], sheet.title)
    columns = [
        {
            "columnId": column_letter(index),
            "name": name,
            "formula": column_letter(index) in formulas,
        }
        for index, name in enumerate(titles)
        if name
    ]
    known = {column["columnId"] for column in columns}
    by_id = {field.id: field for field in fields}
    for entry in request["mapping"]:
        if entry["columnId"] not in known:
            issues.append(
                {
                    "code": "SHEETS_COLUMN_MISSING",
                    "message": f"来源列 {entry['columnId']} 没有表头。",
                    "columnId": entry["columnId"],
                }
            )
        field = by_id.get(entry["fieldId"])
        if field is None:
            issues.append(
                {
                    "code": "SHEETS_FIELD_MISSING",
                    "message": "映射引用了本表不存在的字段。",
                    "columnId": entry["columnId"],
                }
            )
    identity = request["identityStrategy"]
    summary = {"unique": False, "missing": 0, "duplicates": 0}
    if identity["kind"] == "column":
        column = identity["columnId"]
        if column not in known:
            issues.append(
                {
                    "code": "SHEETS_IDENTITY_MISSING",
                    "message": f"身份列 {column} 没有表头。",
                    "columnId": column,
                }
            )
        else:
            summary = _identity_summary(
                client, request["spreadsheetId"], sheet.title, column
            )
            if summary["missing"]:
                issues.append(
                    {
                        "code": "SHEETS_IDENTITY_INCOMPLETE",
                        "message": f"身份列有 {summary['missing']} 个空值。",
                        "columnId": column,
                    }
                )
            if summary["duplicates"]:
                issues.append(
                    {
                        "code": "SHEETS_IDENTITY_DUPLICATE",
                        "message": f"身份列有 {summary['duplicates']} 个重复值。",
                        "columnId": column,
                    }
                )
    return {
        "valid": not issues,
        "issues": issues,
        "columns": columns,
        "identitySummary": summary,
        "overlaps": overlaps,
        "spreadsheetTitle": spreadsheet.title,
        "sheetName": sheet.title,
        "bindingEpoch": epoch,
    }


def _identity_summary(
    client: SheetsClient, spreadsheet_id: str, sheet_title: str, column: str
) -> dict[str, Any]:
    try:
        rows = client.values(
            spreadsheet_id, column_range(sheet_title, _column_index(column)), "FORMULA"
        )
    except SheetsApiError as error:
        raise _api_error(error) from error
    seen: set[str] = set()
    missing = duplicates = 0
    for row in rows:
        value = row[0] if row else ""
        if value is None or value == "":
            missing += 1
            continue
        marker = _identity_token(value)
        if marker in seen:
            duplicates += 1
        seen.add(marker)
    return {"unique": not missing and not duplicates, "missing": missing, "duplicates": duplicates}


def _identity_token(value: Any) -> str:
    if isinstance(value, bool):
        return f"boolean:{value}"
    if isinstance(value, int):
        return f"integer:{value}"
    if isinstance(value, float) and float(value).is_integer():
        return f"integer:{int(value)}"
    return f"text:{value}"


def _column_index(column_id: str) -> int:
    letters = column_id.upper()
    if not letters.isalpha() or len(letters) > 3:
        raise _invalid("columnId", "必须是 A1 列标识")
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return index - 1


def _api_error(error: SheetsApiError) -> ProjectError:
    status = 502 if error.unsent or error.retryable or error.uncertain else 422
    if error.status == 403:
        status = 409
    return ProjectError(
        "SHEETS_API_FAILED",
        error.message,
        status,
        {
            "reason": error.reason,
            "upstreamStatus": error.status,
            "retryable": error.retryable,
            "uncertain": error.uncertain,
        },
    )
