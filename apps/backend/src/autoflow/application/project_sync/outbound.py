"""Local change intents, remote sends and the confirmation evidence behind them.

A send is never repeated blindly: a request that provably never left the
machine may be retried, while a request whose outcome is unknown is recorded as
`unknown` and can only be reconciled against its original target.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.identity import (
    RecordKey,
    RecordKeyType,
    decode_record_key,
)
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_sync import SqlAlchemyProjectSync
from autoflow.infrastructure.database.project_sync_models import SyncOperationRow
from autoflow.providers.data.google_sheets import (
    SheetsApiError,
    SheetsClient,
    cell,
    column_letter,
    quoted,
)

from .access import GoogleAccess
from .bindings import _api_error, _column_index
from .connections import _invalid, _uuid
from .runs import SheetsRun

MAX_PUSH_RECORDS = 200
PUSH_RETRY_LIMIT = 3
WHOLE_SHEET = "A:ZZ"


class SheetsSyncService:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        runs: SheetsRun,
        sync: SqlAlchemyProjectSync,
        access: GoogleAccess,
    ) -> None:
        self._sessions, self._runs, self._sync = sessions, runs, sync
        self._access = access
        self._records = SqlAlchemyProjectDataRecords(sessions)

    # ----------------------------------------------------------------------- state

    def state(self, project_id: str, table_id: str) -> dict[str, Any]:
        _uuid(project_id, "projectId")
        _uuid(table_id, "tableId")
        binding = self._runs.binding(project_id, table_id)
        if binding is None:
            return {
                "summary": {
                    "status": "notApplicable",
                    "pendingCount": 0,
                    "unknownCount": 0,
                }
            }
        return {"summary": self._runs.summary(project_id, table_id), "binding": binding}

    def source_observations(
        self, project: str, table: str, generation: str, encoded: str, key_type: str,
    ) -> dict[str, Any]:
        _uuid(project, "projectId")
        _uuid(table, "tableId")
        _uuid(generation, "datasetGeneration")
        return self._sync.source_observations(project, table, generation, decode_record_key(encoded, key_type))

    def pause(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._paused(project_id, table_id, payload, True)

    def resume(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._paused(project_id, table_id, payload, False)

    def _paused(
        self, project_id: str, table_id: str, payload: dict[str, Any], paused: bool
    ) -> dict[str, Any]:
        if set(payload) != {"expectedBindingEpoch"}:
            raise _invalid("payload", "意外的字段")
        epoch = _revision(payload["expectedBindingEpoch"], "expectedBindingEpoch")
        self._sync.set_paused(project_id, table_id, paused, epoch)
        return {
            "summary": self._runs.summary(project_id, table_id),
            "binding": self._runs.binding(project_id, table_id),
        }

    # ------------------------------------------------------------------- operations

    def list_operations(
        self,
        project_id: str,
        table_id: str,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        self._require_table(project_id, table_id)
        return self._sync.sync_operations(table_id, status, page, page_size)

    def read_operation(
        self, project_id: str, table_id: str, sync_operation_id: str
    ) -> dict[str, Any]:
        self._require_table(project_id, table_id)
        return self._sync.sync_operation(
            table_id, _uuid(sync_operation_id, "syncOperationId")
        )

    # ------------------------------------------------------------------------ pull

    def pull(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if set(payload) != {"expectedTableRevision"}:
            raise _invalid("payload", "意外的字段")
        expected = _revision(payload["expectedTableRevision"], "expectedTableRevision")
        with self._sessions() as session:
            table = _require_table(session, project_id, table_id)
            if table.table_revision != expected:
                raise ProjectError(
                    "PRECONDITION_FAILED",
                    "表结构已变化，请重新加载。",
                    412,
                    {"reason": "tableRevision", "tableRevision": table.table_revision},
                )
            generation = table.current_generation
            fields = {field.id: field for field in _fields(session, table)}
        binding = self._require_binding(project_id, table_id)
        epoch = int(binding["bindingEpoch"])
        view, existing = self._runs.accept(
            project=project_id,
            table=table_id,
            kind="syncPull",
            key=key,
            request=payload,
            binding_epoch=epoch,
            dedupe=f"pull:{key}",
        )
        if existing:
            return {"operation": view}
        operation_id = view["operationId"]
        try:
            client = self._access.client(project_id, str(binding["connectionId"]))
            self._pull(client, project_id, table_id, generation, fields, binding)
        except ProjectError as error:
            self._runs.fail(operation_id, error)
            raise
        # The frozen `syncPull` result is which table ran and what the queue looks
        # like afterwards; per-record outcomes are their own sync operations.
        self._runs.complete_queue(
            operation_id, lambda: self._run_result(project_id, table_id)
        )
        return {"operation": self._runs.operation_view(operation_id)}

    def _pull(
        self,
        client: SheetsClient,
        project_id: str,
        table_id: str,
        generation: str,
        fields: dict[str, DataFieldRow],
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        spreadsheet_id = str(binding["spreadsheetId"])
        sheet_name = str(binding["sheetName"])
        try:
            raw = client.values(
                spreadsheet_id, f"{quoted(sheet_name)}!{WHOLE_SHEET}", "FORMULA"
            )
            computed = client.values(
                spreadsheet_id,
                f"{quoted(sheet_name)}!{WHOLE_SHEET}",
                "UNFORMATTED_VALUE",
            )
        except SheetsApiError as error:
            raise _api_error(error) from error
        header = [str(value) for value in raw[0]] if raw else []
        identity = _identity_column(binding["identityStrategy"], header)
        keys: list[RecordKey] = []
        valid = identity < len(header) and bool(header[identity])
        for remote in raw[1:]:
            if not any(value is not None and str(value) != "" for value in remote):
                continue
            marker = remote[identity] if identity < len(remote) else None
            if marker is None or marker == "" or isinstance(marker, bool) or (isinstance(marker, str) and marker.startswith("=")):
                valid = False
                continue
            keys.append(_record_key_for(marker))
        valid = valid and len(set(keys)) == len(keys)
        namespace = json.dumps({"columnId": column_letter(identity), "header": header[identity] if identity < len(header) else "", "encoding": "typed-record-key-v1"}, sort_keys=True, ensure_ascii=False)
        self._sync.verify_source_identity(project_id, table_id, generation, int(binding["bindingEpoch"]), namespace, keys, valid=valid)
        by_column = {
            str(entry["columnId"]).upper(): entry for entry in binding["mapping"]
        }
        created = refreshed = conflicts = rows = 0
        for index in range(1, len(raw)):
            row = raw[index]
            if not any(str(value) != "" for value in row):
                continue
            marker = row[identity] if identity < len(row) else ""
            if marker is None or marker == "":
                continue
            rows += 1
            values: dict[str, Any] = {}
            for position in range(len(header)):
                entry = by_column.get(column_letter(position))
                if entry is None or entry["direction"] == "write":
                    continue
                field = fields.get(str(entry["fieldId"]))
                if field is None:
                    continue
                # A formula column stores the formula itself: the provider
                # copies it when a row is appended (DATA-SH-11), so a pull reads
                # it from the FORMULA view while plain cells keep the value the
                # user sees.
                source = raw if field.formula else computed
                values[field.id] = _coerce(
                    field.type, _cell_value(source, index, position)
                )
            key = _record_key_for(marker)
            outcome = self._ingest(project_id, table_id, generation, key, values)
            if valid:
                self._sync.observe_source(project_id, table_id, generation, int(binding["bindingEpoch"]), key, values)
            if outcome == "created":
                created += 1
            elif outcome == "refreshed":
                refreshed += 1
            elif outcome == "conflict":
                conflicts += 1
        return {"created": created, "refreshed": refreshed, "conflicts": conflicts, "rows": rows}

    def _ingest(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
        values: dict[str, Any],
    ) -> str:
        with self._sessions() as session:
            existing = session.get(DataRecordRow, (generation, key.type, key.value))
            if existing is None:
                return self._create_record(project_id, table_id, generation, key, values)
            refresh = _formula_values(session, existing, values)
            revision = existing.content_revision
        if not refresh:
            return "seen"
        try:
            self._records.update(
                project_id,
                table_id,
                generation,
                key,
                refresh,
                revision,
                _record_operation(
                    project_id, table_id, generation, key, "updateRecord", refresh
                ),
                # The source owns the formula these cells hold, so the refresh
                # writes past the local read-only rule the same way a create does.
                origin="source",
            )
        except ProjectError as error:
            if error.code in {"CONTENT_REVISION_CONFLICT", "RECORD_NOT_FOUND"}:
                # A concurrent local edit keeps its value; the next pull retries.
                return "conflict"
            raise
        return "refreshed"

    def _create_record(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
        values: dict[str, Any],
    ) -> str:
        try:
            self._records.create(
                project_id,
                table_id,
                generation,
                values,
                _record_operation(
                    project_id, table_id, generation, key, "createRecord", values
                ),
                key=key,
                origin="source",
            )
        except ProjectError as error:
            if error.code in {"RECORD_ALREADY_EXISTS"}:
                return "seen"
            if error.code in {
                "REQUIRED_FIELD_MISSING",
                "INVALID_RECORD_VALUE",
                "UNKNOWN_FIELD",
            }:
                return "conflict"
            raise
        return "created"

    # ------------------------------------------------------------------------ push

    def push(
        self, project_id: str, table_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if set(payload) != {"mode", "expectedBindingEpoch"}:
            raise _invalid("payload", "意外的字段")
        mode = payload["mode"]
        if mode not in {"due", "allPending"}:
            raise _invalid("mode", "mode 必须是 due 或 allPending")
        epoch = _revision(payload["expectedBindingEpoch"], "expectedBindingEpoch")
        binding = self._require_binding(project_id, table_id)
        if int(binding["bindingEpoch"]) != epoch:
            raise ProjectError(
                "PRECONDITION_FAILED",
                "绑定已变化，请重新加载。",
                412,
                {"reason": "bindingEpoch", "bindingEpoch": binding["bindingEpoch"]},
            )
        if binding["syncPaused"]:
            # DATA-LIFE-05: pausing keeps recording local intents but stops new
            # network writes, so a push must refuse rather than send.
            raise ProjectError(
                "SYNC_PAUSED",
                "同步已暂停，请先恢复同步。",
                409,
                {"bindingEpoch": binding["bindingEpoch"]},
            )
        self._access.require_writable(project_id, str(binding["connectionId"]))
        view, existing = self._runs.accept(
            project=project_id,
            table=table_id,
            kind="syncPush",
            key=key,
            request=payload,
            binding_epoch=epoch,
            dedupe=f"push:{key}",
        )
        if existing:
            return {"operation": view}
        operation_id = view["operationId"]
        try:
            client = self._access.client(project_id, str(binding["connectionId"]))
            self._push(client, project_id, table_id, binding, mode)
        except ProjectError as error:
            self._runs.fail(operation_id, error)
            raise
        self._runs.complete_queue(
            operation_id, lambda: self._run_result(project_id, table_id)
        )
        return {"operation": self._runs.operation_view(operation_id)}

    def _run_result(self, project_id: str, table_id: str) -> dict[str, Any]:
        """The one frozen result shape for a pull or a push."""
        return {
            "tableId": table_id,
            "summary": self._runs.summary(project_id, table_id),
        }

    def _push(
        self,
        client: SheetsClient,
        project_id: str,
        table_id: str,
        binding: dict[str, Any],
        mode: str,
    ) -> dict[str, Any]:
        intents = [
            intent
            for intent in self._sync.pending(table_id, MAX_PUSH_RECORDS)
            if mode == "allPending"
            or (intent.status in {"pending", "failed"} and intent.attempts < PUSH_RETRY_LIMIT)
        ]
        if not intents:
            return {"confirmed": 0, "failed": 0, "unknown": 0, "targets": []}
        spreadsheet_id = str(binding["spreadsheetId"])
        sheet_name = str(binding["sheetName"])
        header = _header(client, spreadsheet_id, sheet_name)
        identity_index = _identity_column(binding["identityStrategy"], header)
        remote = _remote_keys(client, spreadsheet_id, sheet_name, identity_index)
        confirmed = failed = unknown = 0
        writes: list[dict[str, Any]] = []
        planned: list[tuple[Any, dict[str, Any], int]] = []
        with self._sessions() as session:
            table = _require_table(session, project_id, table_id)
            generation = table.current_generation
            fields = {field.id: field for field in _fields(session, table)}
            for intent in intents:
                if intent.request.get("datasetGeneration") != generation:
                    # The row this intent was raised for left the current data
                    # (a re-import replaced the dataset while the binding stayed),
                    # so the same key in the new generation is a different fact
                    # and must never be written to the source on the old intent.
                    self._sync.transition(
                        intent.id,
                        status="failed",
                        error={
                            "code": "SYNC_GENERATION_CHANGED",
                            "message": "数据代次已更换，这条本地修改需要在新数据上重新发起。",
                        },
                    )
                    continue
                key = RecordKey(_key_type(intent.record_key_type), str(intent.record_key))
                row_index = remote.get(_marker(key))
                if row_index is None:
                    self._sync.mark(table_id, key.type, key.value, remote_missing=True)
                    self._sync.transition(
                        intent.id,
                        status="failed",
                        attempt=True,
                        error={
                            "code": "SYNC_REMOTE_ROW_MISSING",
                            "message": "来源中已找不到这一行，请先重新拉取确认。",
                        },
                    )
                    failed += 1
                    continue
                record = session.get(DataRecordRow, (generation, key.type, key.value))
                if not isinstance(intent.request.get("values"), dict):
                    self._sync.transition(intent.id, status="failed", error={
                        "code": "SYNC_SNAPSHOT_MISSING",
                        "message": "旧同步操作缺少原字段快照，禁止猜测写入；请核查后重新发起修改。",
                    })
                    failed += 1
                    continue
                cells = {} if record is None or record.deleted else _write_cells(intent.request["values"], fields, binding)
                if not cells:
                    self._sync.transition(
                        intent.id,
                        status="failed",
                        attempt=True,
                        error={
                            "code": "SYNC_NOTHING_TO_WRITE",
                            "message": "这一行没有可写入的来源列。",
                        },
                    )
                    failed += 1
                    continue
                try:
                    self._sync.transition(
                        intent.id, status="sending", attempt=True,
                        expected_status_revision=intent.status_revision,
                    )
                except ProjectError as error:
                    if error.code == "PRECONDITION_FAILED":
                        continue  # An edit/cancel/other sender won; never send stale facts.
                    raise
                for column, value in cells.items():
                    writes.append(
                        {
                            "range": cell(sheet_name, _column_index(column), row_index),
                            "values": [[value]],
                        }
                    )
                planned.append((intent, cells, row_index))
        if not writes:
            return {"confirmed": confirmed, "failed": failed, "unknown": 0, "targets": []}
        try:
            client.batch_update_values(spreadsheet_id, writes, "RAW")
        except SheetsApiError as error:
            payload = {
                "code": "SYNC_SEND_UNKNOWN" if error.uncertain else "SYNC_SEND_FAILED",
                "message": error.message,
                "upstreamStatus": error.status,
                "retryable": error.retryable,
            }
            status = "unknown" if error.uncertain else "failed"
            for intent, _, _ in planned:
                self._sync.transition(
                    intent.id, status=status, error=payload
                )
            return {
                "confirmed": confirmed,
                "failed": failed + (0 if error.uncertain else len(planned)),
                "unknown": unknown + (len(planned) if error.uncertain else 0),
                "targets": [],
                "error": payload,
            }
        for intent, cells, row_index in planned:
            try:
                matched = self._verify(
                    client, spreadsheet_id, sheet_name, row_index, cells
                )
            except ProjectError as error:
                # The write already succeeded. A failed read is no evidence that
                # it did not apply; preserve the original intent for reconciliation.
                self._sync.transition(intent.id, status="unknown", error={
                    "code": "SYNC_VERIFY_UNAVAILABLE",
                    "message": error.message,
                    "details": error.details,
                })
                unknown += 1
                continue
            evidence = {
                "checkedAt": datetime.now(UTC).isoformat(),
                "target": f"{sheet_name}!{row_index}",
                "fields": sorted(cells),
                "outcome": "matched" if matched else "notMatched",
            }
            if matched:
                self._sync.transition(
                    intent.id, status="confirmed", evidence=evidence
                )
                self._sync.mark(
                    table_id,
                    str(intent.record_key_type),
                    str(intent.record_key),
                    remote_missing=False,
                    observed=evidence,
                )
                confirmed += 1
            else:
                self._sync.transition(
                    intent.id,
                    status="failed",
                    evidence=evidence,
                    error={
                        "code": "SYNC_VERIFY_MISMATCH",
                        "message": "来源返回的内容与本次写入不一致。",
                    },
                )
                failed += 1
        return {
            "confirmed": confirmed,
            "failed": failed,
            "unknown": unknown,
            "targets": [row_index for _, _, row_index in planned],
        }

    def _verify(
        self,
        client: SheetsClient,
        spreadsheet_id: str,
        sheet_name: str,
        row: int,
        cells: dict[str, Any],
    ) -> bool:
        for column, value in cells.items():
            try:
                read = client.values(
                    spreadsheet_id, cell(sheet_name, _column_index(column), row), "FORMULA"
                )
            except SheetsApiError as error:
                raise _api_error(error) from error
            actual = read[0][0] if read and read[0] else ""  # ValueRange omits empty trailing cells.
            if not _same(actual, value):
                return False
        return True

    # -------------------------------------------------------------------- recovery

    def reconcile(
        self,
        project_id: str,
        table_id: str,
        sync_operation_id: str,
        key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if set(payload) != {"expectedStatusRevision"}:
            raise _invalid("payload", "意外的字段")
        expected = _revision(payload["expectedStatusRevision"], "expectedStatusRevision")
        sync_operation_id = _uuid(sync_operation_id, "syncOperationId")
        # A retry of this command has to answer with the decision it already
        # made, so the replay is looked up before the revision it quotes.
        replay = self._sync.replay(
            project_id, table_id, "reconcileSync", key, payload
        )
        if replay is not None:
            return {"operation": replay}
        original = self._sync.sync_operation(table_id, sync_operation_id)
        if original["statusRevision"] != expected:
            raise ProjectError(
                "PRECONDITION_FAILED",
                "该操作已被其他请求更新，请重新加载。",
                412,
                {
                    "reason": "statusRevision",
                    "statusRevision": original["statusRevision"],
                },
            )
        if original["status"] not in {"sending", "verifying", "unknown"}:
            raise ProjectError(
                "SYNC_NOT_RECONCILABLE",
                "只有结果未知的操作才需要核验。",
                409,
                {"status": original["status"]},
            )
        binding = self._require_binding(project_id, table_id)
        record = original.get("record")
        if record is None:
            raise ProjectError(
                "SYNC_NOT_RECONCILABLE", "该操作没有可核验的记录目标。", 409
            )
        record_key = RecordKey(record["recordKey"]["type"], record["recordKey"]["value"])
        with self._sessions() as session:
            row = session.get(
                DataRecordRow,
                (record["datasetGeneration"], record_key.type, record_key.value),
            )
            if row is None or row.deleted:
                raise ProjectError("RECORD_NOT_FOUND", "本地记录已不存在。", 404)
            fields = {
                field.id: field
                for field in _fields(session, _require_table(session, project_id, table_id))
            }
            intent = session.get(SyncOperationRow, sync_operation_id)
            if intent is None or not isinstance(intent.request.get("values"), dict):
                raise ProjectError("SYNC_SNAPSHOT_MISSING", "原字段快照不可用，不能用当前记录推定历史结果。", 409)
            cells = _write_cells(intent.request["values"], fields, binding)
        view, existing = self._runs.accept(
            project=project_id,
            table=table_id,
            kind="reconcileSync",
            key=key,
            request=payload,
            binding_epoch=int(binding["bindingEpoch"]),
            dedupe=f"reconcile:{key}",
            record_ref=record,
        )
        if existing:
            return {"operation": view}
        operation_id = view["operationId"]
        try:
            client = self._access.client(project_id, str(binding["connectionId"]))
            spreadsheet_id = str(binding["spreadsheetId"])
            sheet_name = str(binding["sheetName"])
            header = _header(client, spreadsheet_id, sheet_name)
            remote = _remote_keys(
                client, spreadsheet_id, sheet_name, _identity_column(binding["identityStrategy"], header)
            )
            row_index = remote.get(_marker(record_key))
            outcome = "notMatched"
            if row_index is not None and cells:
                outcome = (
                    "matched"
                    if self._verify(client, spreadsheet_id, sheet_name, row_index, cells)
                    else "notMatched"
                )
        except ProjectError as error:
            # Only this read command failed; the original write stays reconcilable.
            self._runs.fail(operation_id, error)
            raise
        evidence = {
            "checkedAt": datetime.now(UTC).isoformat(),
            "target": f"{sheet_name}!{row_index or 0}",
            "fields": sorted(cells),
            "outcome": outcome,
        }
        self._sync.transition(
            sync_operation_id,
            status="confirmed" if outcome == "matched" else "failed",
            evidence=evidence,
            error=None
            if outcome == "matched"
            else {
                "code": "SYNC_RECONCILE_MISMATCH",
                "message": "来源中的内容与本次写入不一致，请重新确认。",
            },
        )
        # The frozen `reconcileSync` result is the sync operation it confirmed.
        self._runs.complete(
            operation_id, self._sync.sync_operation(table_id, sync_operation_id)
        )
        return {"operation": self._runs.operation_view(operation_id)}

    def abandon(
        self,
        project_id: str,
        table_id: str,
        sync_operation_id: str,
        key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if set(payload) != {"expectedStatusRevision", "reason"}:
            raise _invalid("payload", "意外的字段")
        expected = _revision(payload["expectedStatusRevision"], "expectedStatusRevision")
        reason = payload["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise _invalid("reason", "必须说明放弃原因")
        current = self._sync.sync_operation(
            table_id, _uuid(sync_operation_id, "syncOperationId")
        )
        if current["statusRevision"] != expected:
            raise ProjectError(
                "PRECONDITION_FAILED",
                "该操作已被其他请求更新，请重新加载。",
                412,
                {
                    "reason": "statusRevision",
                    "statusRevision": current["statusRevision"],
                },
            )
        if current["status"] != "pending":
            raise ProjectError(
                "SYNC_NOT_ABANDONABLE",
                "已经发送过的操作不能放弃，只能核验或保留为历史。",
                409,
                {"status": current["status"]},
            )
        return self._sync.transition(
            sync_operation_id,
            status="failed",
            error={"code": "SYNC_ABANDONED", "message": reason.strip()},
            expected_status_revision=expected,
        )

    # --------------------------------------------------------------------- helpers

    def _require_table(
        self, project_id: str, table_id: str, session: Session | None = None
    ) -> DataTableRow:
        _uuid(project_id, "projectId")
        _uuid(table_id, "tableId")
        if session is not None:
            return _require_table(session, project_id, table_id)
        with self._sessions() as inner:
            return _require_table(inner, project_id, table_id)

    def _require_binding(self, project_id: str, table_id: str) -> dict[str, Any]:
        self._require_table(project_id, table_id)
        binding = self._runs.binding(project_id, table_id)
        if binding is None:
            raise ProjectError("SHEETS_BINDING_NOT_FOUND", "该表未绑定 Sheets。", 404)
        return binding


def _require_table(session: Session, project_id: str, table_id: str) -> DataTableRow:
    row = session.get(DataTableRow, table_id)
    if row is None or row.project_id != project_id or not row.published:
        raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
    return row


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


def _write_cells(
    values: dict[str, Any],
    fields: dict[str, DataFieldRow],
    binding: dict[str, Any],
) -> dict[str, Any]:
    cells: dict[str, Any] = {}
    for entry in binding["mapping"]:
        if entry["direction"] == "read":
            continue
        field = fields.get(str(entry["fieldId"]))
        if field is None or not field.writable or field.formula:
            continue
        if field.id in values:
            cells[str(entry["columnId"]).upper()] = "" if values[field.id] is None else values[field.id]
    return cells


def _formula_values(
    session: Session, row: DataRecordRow, remote: dict[str, Any]
) -> dict[str, Any]:
    fields = {
        field.id: field
        for field in session.scalars(
            select(DataFieldRow).where(
                DataFieldRow.dataset_generation == row.dataset_generation,
                DataFieldRow.table_id == row.table_id,
            )
        ).all()
    }
    return {
        field_id: value
        for field_id, value in remote.items()
        if (field := fields.get(field_id)) is not None
        and field.formula
        and row.values_json.get(field_id) != value
    }


def _coerce(field_type: str, value: Any) -> Any:
    """Fit a remote cell to the local field type before it is validated.

    A spreadsheet types `1` as a number while the local column may be text; the
    record key keeps the remote type, the stored value follows the local field.
    """
    # ponytail: only the text case needs rewriting today. Numbers, dates and
    # booleans keep the remote shape and are rejected by field validation when
    # they genuinely disagree.
    if field_type != "string" or value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _cell_value(computed: list[list[Any]], index: int, position: int) -> Any:
    row = computed[index] if index < len(computed) else []
    value = row[position] if position < len(row) else ""
    return "" if value is None else value


def _same(left: Any, right: Any) -> bool:
    """Whether a remote cell still holds the fact that was written.

    Identity in this project is typed -- the text `"2"` and the number `2` are
    different records -- so a confirmation compares the same shape on both
    sides. The check is symmetric because the caller's argument order follows
    the read, and `RAW` writes preserve the shape while `2.0` and `2` are one
    number.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        return (
            isinstance(left, (int, float))
            and isinstance(right, (int, float))
            and float(left) == float(right)
        )
    return type(left) is type(right) and left == right


def _identity_column(strategy: dict[str, Any], header: list[str]) -> int:
    column = strategy.get("columnId")
    if strategy.get("kind") != "column" or not isinstance(column, str):
        raise ProjectError(
            "SYNC_NOT_IMPLEMENTED",
            "系统身份表的来源同步尚未交付，请选择按列识别身份。",
            501,
            {"capability": "sheets.systemIdentity"},
        )
    return _column_index(column)


def _record_key_for(marker: Any) -> RecordKey:
    if isinstance(marker, bool):
        return RecordKey("text", str(marker))
    if isinstance(marker, int) or (isinstance(marker, float) and marker.is_integer()):
        return RecordKey("integer", str(int(marker)))
    return RecordKey("text", str(marker))


def _key_type(value: str | None) -> RecordKeyType:
    return value if value in {"text", "integer", "uuid"} else "text"  # type: ignore[return-value]


def _marker(key: RecordKey) -> str:
    return f"{key.type}:{key.value}"


def _remote_keys(
    client: SheetsClient, spreadsheet_id: str, sheet_name: str, index: int
) -> dict[str, int]:
    letters = column_letter(index)
    try:
        values = client.values(
            spreadsheet_id, f"{quoted(sheet_name)}!{letters}2:{letters}", "FORMULA"
        )
    except SheetsApiError as error:
        raise _api_error(error) from error
    keys: dict[str, int] = {}
    for offset, row in enumerate(values):
        value = row[0] if row else ""
        if value is None or value == "":
            continue
        keys.setdefault(_marker(_record_key_for(value)), offset + 2)
    return keys


def _header(client: SheetsClient, spreadsheet_id: str, sheet_name: str) -> list[str]:
    try:
        values = client.values(spreadsheet_id, f"{quoted(sheet_name)}!1:1", "FORMULA")
    except SheetsApiError as error:
        raise _api_error(error) from error
    return [str(value) for value in (values[0] if values else [])]


def _record_operation(
    project_id: str,
    table_id: str,
    generation: str,
    key: RecordKey,
    kind: str,
    values: dict[str, Any],
) -> ProjectOperation:
    stable = _stable_id(
        f"sheets:{project_id}:{table_id}:{generation}:{kind}:{key.type}:{key.value}:"
        f"{json.dumps(values, sort_keys=True, ensure_ascii=False, default=str)}"
    )
    now = datetime.now(UTC)
    return ProjectOperation(
        operation_id=stable,
        project_id=project_id,
        idempotency_key=stable,
        kind=kind,
        request_digest=stable,
        status="running",
        status_revision=1,
        resource={"type": "table", "projectId": project_id, "tableId": table_id},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, hashlib.sha256(value.encode()).hexdigest()))


def _revision(value: Any, field: str) -> int:
    if type(value) is not int or value < 1:
        raise _invalid(field, "必须是正整数")
    return value


def _identity_token(value: Any) -> str:
    if isinstance(value, bool):
        return f"boolean:{value}"
    if isinstance(value, int):
        return f"integer:{value}"
    if isinstance(value, float) and float(value).is_integer():
        return f"integer:{int(value)}"
    return f"text:{value}"
