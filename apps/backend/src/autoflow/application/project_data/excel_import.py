"""Coordinate bounded workbook parsing and hidden generation publication."""

from contextlib import contextmanager
from pathlib import Path
from threading import Event

from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.project_data.excel import _uuid, normalize_import
from autoflow.domain.project_data.identity import record_key, system_record_key
from autoflow.domain.project_data.records import validate_record_scalar
from autoflow.domain.project_data.rules import validate_value
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_excel_imports import (
    SqlAlchemyExcelImports,
)
from autoflow.infrastructure.filesystem.project_excel import read_sheet


class ExcelImportService:
    def __init__(self, repository: SqlAlchemyExcelImports, gate: QuiesceGate):
        self.repository, self.gate, self.stopping = repository, gate, Event()

    @contextmanager
    def mutation(self):
        with self.gate.mutation() as admitted:
            if not admitted or self.stopping.is_set():
                raise ProjectError(
                    "WORKSPACE_SWITCH_IN_PROGRESS", "工作区正在切换。", 423
                )
            yield

    def submit(
        self,
        project: str,
        table: str | None,
        key: str,
        payload: dict,
        window_id: int,
        proof: str,
    ):
        project, key = _uuid(project, "projectId"), _uuid(key, "Idempotency-Key")
        if table is not None:
            table = _uuid(table, "tableId")
        data = normalize_import(payload, replace=table is not None)
        with self.mutation():
            return self.repository.accept(project, table, key, data, window_id, proof)

    def preview_replace(self, project: str, table: str):
        with self.mutation():
            return self.repository.preview_replace(
                _uuid(project, "projectId"), _uuid(table, "tableId")
            )

    def run(self, operation_id: str):
        job = None
        try:
            with self.mutation():
                job = self.repository.claim(operation_id)
            if job is None:
                return
            with self.mutation():
                self.repository.initialize(job)
            stage, data = job.request["_staging"], job.request
            columns = {int(column): field for column, field in stage["columns"].items()}
            identity_column = data["identity"].get("columnIndex")
            identity_field = columns.get(identity_column) if identity_column is not None else None
            batch = []
            with read_sheet(
                Path(job.path), data["sheetId"], data["fingerprint"]
            ) as stream:
                for row in stream:
                    if self.stopping.is_set():
                        raise ProjectError(
                            "EXCEL_IMPORT_INTERRUPTED",
                            "导入已中断，请重新选择来源文件。",
                            409,
                        )
                    if all(value is None for value in row.values):
                        continue
                    values = {}
                    for column, field in columns.items():
                        raw_value = row.values[column]
                        try:
                            values[field] = validate_value(stage["fields"][field], raw_value)
                        except ProjectError as error:
                            # Identity is a trust boundary: a business-format error
                            # must reject the import instead of becoming a text key.
                            if field == identity_field:
                                raise ProjectError(
                                    error.code, "来源身份单元格不满足字段要求。", 422,
                                    {**error.details, "rowNumber": row.row_number, "columnIndex": column},
                                ) from error
                            # A missing source cell stays missing.  Other safe source
                            # scalars are retained so the published record can expose
                            # a structured issue without inventing a replacement.
                            if raw_value is None:
                                continue
                            try:
                                values[field] = validate_record_scalar(raw_value)
                            except ProjectError:
                                raise ProjectError(
                                    error.code, "来源单元格不满足字段要求。", 422,
                                    {**error.details, "rowNumber": row.row_number, "columnIndex": column},
                                ) from error
                    key = (
                        system_record_key()
                        if identity_column is None
                        else record_key(row.values[identity_column])
                    )
                    batch.append(
                        {"keyType": key.type, "keyValue": key.value, "values": values}
                    )
                    if len(batch) == 200:
                        with self.mutation():
                            self.repository.append(job, batch)
                        batch = []
            with self.mutation():
                self.repository.append(job, batch)
            with self.mutation():
                self.repository.publish(job)
        except Exception as error:  # noqa: BLE001 -- worker boundary persists a sanitized failure
            failure = (
                error
                if isinstance(error, ProjectError)
                else ProjectError(
                    "EXCEL_IMPORT_FAILED", "文件导入失败，请检查来源文件后重试。", 500
                )
            )
            # Settling an accepted fact is allowed after admission of new work stops.
            self.repository.fail(
                operation_id,
                {
                    "code": failure.code,
                    "message": failure.message,
                    "details": failure.details,
                },
                claim=job.claim if job is not None else None,
            )

    def startup(self):
        for operation_id in self.repository.pending():
            self.repository.fail(
                operation_id,
                {
                    "code": "EXCEL_IMPORT_INTERRUPTED",
                    "message": "导入已中断，请重新选择来源文件。",
                    "details": {},
                },
            )

    def pending_operations(self):
        return self.repository.pending()

    def shutdown(self):
        self.stopping.set()
