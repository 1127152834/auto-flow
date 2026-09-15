"""Hidden generation staging with short commits and a single publication boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.excel import _digest, _not_expired, _window
from autoflow.domain.project_data.models import table_to_dict
from autoflow.domain.projects.models import ProjectError

from .models import ProjectOperationRow
from .project_data import _table
from .project_data_catalog import SqlAlchemyProjectDataCatalog
from .project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataGenerationRow,
    DataImpactRow,
    DataRecordRow,
    DataTableRow,
)
from .project_data_status_batch_models import DataStatusBatchRow
from .project_excel_common import operation_view
from .project_excel_models import (
    ProjectExcelImportJobRow,
    ProjectExcelInspectionRow,
    ProjectFileSelectionRow,
)
from .project_run_models import ProjectRecordLeaseRow


@dataclass(frozen=True)
class ImportJob:
    operation_id: str
    project_id: str
    table_id: str
    generation: str
    action: str
    request: dict[str, Any]
    claim: str
    path: str


def _facts(session: Session, project: str, table: str) -> int:
    resource = DataChangeRow.resource
    return (
        session.scalar(
            select(func.count())
            .select_from(DataChangeRow)
            .where(
                DataChangeRow.project_id == project,
                or_(
                    resource["tableId"].as_string() == table,
                    resource["recordRef"]["tableId"].as_string() == table,
                    resource["fieldRef"]["tableId"].as_string() == table,
                ),
            )
        )
        or 0
    )


def _batches(session: Session, project: str, table: str) -> bool:
    return (
        session.scalar(
            select(DataStatusBatchRow.operation_id)
            .join(
                ProjectOperationRow,
                ProjectOperationRow.id == DataStatusBatchRow.operation_id,
            )
            .where(
                DataStatusBatchRow.project_id == project,
                DataStatusBatchRow.table_id == table,
                ProjectOperationRow.status.in_(("accepted", "running", "reconciling")),
            )
            .limit(1)
        )
        is not None
    )


def _leases(session: Session, project: str, table: DataTableRow) -> bool:
    return (
        session.scalar(
            select(ProjectRecordLeaseRow.id)
            .where(
                ProjectRecordLeaseRow.project_id == project,
                ProjectRecordLeaseRow.record_ref["tableId"].as_string() == table.id,
                ProjectRecordLeaseRow.record_ref["datasetGeneration"].as_string()
                == table.current_generation,
                ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
            )
            .limit(1)
        )
        is not None
    )


class SqlAlchemyExcelImports:
    def __init__(
        self, sessions: sessionmaker[Session], workspace_id: str, instance_id: str
    ):
        self.sessions, self.workspace_id, self.instance_id = (
            sessions,
            workspace_id,
            instance_id,
        )

    def preview_replace(self, project: str, table_id: str) -> dict:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            table = SqlAlchemyProjectDataCatalog._table(
                session, project, table_id, True
            )
            now = datetime.now(UTC)
            revisions = {
                "datasetGeneration": table.current_generation,
                "tableRevision": table.table_revision,
            }
            count = (
                session.scalar(
                    select(func.count())
                    .select_from(DataRecordRow)
                    .where(
                        DataRecordRow.dataset_generation == table.current_generation,
                        DataRecordRow.deleted.is_(False),
                    )
                )
                or 0
            )
            blockers = (
                ["仍有批量状态操作正在处理，请等待完成后重新确认。"]
                if _batches(session, project, table_id)
                else []
            )
            if _leases(session, project, table):
                blockers.append("仍有运行占用当前数据，请等待释放后重新确认。")
            report = {
                "target": {"type": "table", "projectId": project, "tableId": table_id},
                "expectedRevisions": revisions,
                "recordCount": count,
                "blockers": blockers,
                "calculatedAt": now.isoformat(),
            }
            impact = DataImpactRow(
                project_id=project,
                action="replaceDataset",
                target=report["target"],
                change_digest=_digest({"action": "replaceDataset"}),
                expected_revisions=revisions,
                facts_digest=str(_facts(session, project, table_id)),
                report={},
                expires_at=now + timedelta(minutes=10),
            )
            session.add(impact)
            session.flush()
            report["impactRevision"] = impact.id
            impact.report = report
            session.commit()
            return report

    def _require_impact(
        self, session: Session, project: str, table: DataTableRow, data: dict
    ):
        impact = session.get(DataImpactRow, data["impactRevision"])
        if (
            table.current_generation != data["expectedDatasetGeneration"]
            or table.table_revision != data["expectedTableRevision"]
        ):
            raise ProjectError("REVISION_CONFLICT", "数据表已更新，请重新确认。", 409)
        if (
            impact is None
            or impact.project_id != project
            or impact.action != "replaceDataset"
            or impact.target
            != {"type": "table", "projectId": project, "tableId": table.id}
        ):
            raise ProjectError(
                "IMPACT_CONFIRMATION_REQUIRED", "请先确认重新导入的影响。", 412
            )
        _not_expired(impact.expires_at)
        if (
            impact.expected_revisions
            != {
                "datasetGeneration": table.current_generation,
                "tableRevision": table.table_revision,
            }
            or impact.facts_digest != str(_facts(session, project, table.id))
            or impact.report["blockers"]
            or _batches(session, project, table.id)
            or _leases(session, project, table)
        ):
            raise ProjectError(
                "REVISION_CONFLICT", "确认之后数据已更新，请重新确认。", 409
            )

    def accept(
        self,
        project: str,
        table_id: str | None,
        key: str,
        data: dict,
        window_id: int,
        proof: str,
    ) -> dict:
        from .project_data import SqlAlchemyProjectData

        digest = _digest(
            {
                "projectId": project,
                "tableId": table_id,
                "action": "replace" if table_id else "create",
                "request": data,
            }
        )
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            old = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            if old is not None:
                if (
                    old.project_id != project
                    or old.kind != "importExcel"
                    or old.request_digest != digest
                ):
                    raise ProjectError(
                        "OPERATION_PAYLOAD_MISMATCH", "原操作键已用于其他请求。", 409
                    )
                return operation_view(old)
            SqlAlchemyProjectData._guard_project_write(session, project)
            inspection = session.get(ProjectExcelInspectionRow, data["inspectionId"])
            if inspection is None or inspection.project_id != project:
                raise ProjectError(
                    "EXCEL_INSPECTION_NOT_FOUND", "文件检查结果不存在。", 404
                )
            selection = session.get(
                ProjectFileSelectionRow, inspection.selection_token_hash
            )
            if (
                selection is None
                or selection.workspace_id != self.workspace_id
                or selection.instance_id != self.instance_id
            ):
                raise ProjectError(
                    "FILE_SELECTION_EXPIRED",
                    "服务已重新连接，请重新选择来源文件。",
                    410,
                )
            _window(
                inspection.window_id, inspection.window_token_hash, window_id, proof
            )
            _not_expired(inspection.expires_at)
            if data["fingerprint"] != inspection.fingerprint:
                raise ProjectError("EXCEL_SOURCE_CHANGED", "来源文件已发生变化。", 409)
            sheet = next(
                (
                    item
                    for item in inspection.snapshot["sheets"]
                    if item["sheetId"] == data["sheetId"]
                ),
                None,
            )
            if sheet is None or any(
                item["columnIndex"] >= len(sheet["headers"]) for item in data["mapping"]
            ):
                raise ProjectError("INVALID_PROJECT_DATA", "工作表或列映射无效。", 422)
            if (
                data["identity"]["mode"] == "column"
                and data["identity"]["columnIndex"] not in sheet["identityCandidates"]
            ):
                raise ProjectError(
                    "EXCEL_INVALID_IDENTITY_COLUMN",
                    "身份列必须全部非空、唯一，且不能包含公式。",
                    422,
                )
            existing: dict[str, dict] = {}
            if table_id:
                table = SqlAlchemyProjectDataCatalog._table(
                    session, project, table_id, True
                )
                self._require_impact(session, project, table, data)
                for field in session.scalars(
                    select(DataFieldRow).where(
                        DataFieldRow.dataset_generation == table.current_generation
                    )
                ):
                    existing[field.id] = {
                        "key": field.key,
                        "name": field.name,
                        "type": field.type,
                        "required": field.required,
                        "validation": field.validation,
                    }
            fields = dict(existing)
            columns = {}
            for item in data["mapping"]:
                target = item["target"]
                if target["kind"] == "existing":
                    field_id = target["fieldId"]
                    if field_id not in existing:
                        raise ProjectError(
                            "FIELD_NOT_FOUND", "映射字段不属于当前数据表。", 404
                        )
                else:
                    field_id = str(uuid4())
                    fields[field_id] = target["definition"]
                columns[str(item["columnIndex"])] = field_id
            if len({value["key"] for value in fields.values()}) != len(fields):
                raise ProjectError("FIELD_KEY_CONFLICT", "字段键重复。", 409)
            mapped = set(columns.values())
            if any(
                field["required"] and field_id not in mapped
                for field_id, field in fields.items()
            ):
                raise ProjectError(
                    "INVALID_PROJECT_DATA", "所有必填字段都必须映射来源列。", 422
                )
            identity = (
                {"mode": "system"}
                if data["identity"]["mode"] == "system"
                else {
                    "mode": "field",
                    "fieldId": columns[str(data["identity"]["columnIndex"])],
                }
            )
            now, operation_id, generation = (
                datetime.now(UTC),
                str(uuid4()),
                str(uuid4()),
            )
            internal = {
                "fields": fields,
                "columns": columns,
                "identity": identity,
                "source": {
                    "kind": "excel",
                    "filename": inspection.snapshot["filename"],
                    "sheetId": data["sheetId"],
                    "sheetName": sheet["name"],
                    "fingerprint": inspection.fingerprint,
                    "importedAt": now.isoformat(),
                },
            }
            request = {**data, "_staging": internal}
            operation = ProjectOperationRow(
                id=operation_id,
                project_id=project,
                idempotency_key=key,
                kind="importExcel",
                request_digest=digest,
                status="accepted",
                status_revision=1,
                resource={"type": "table", "projectId": project, "tableId": table_id}
                if table_id
                else {"type": "project", "projectId": project},
                result=None,
                error=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
            job = ProjectExcelImportJobRow(
                operation_id=operation_id,
                project_id=project,
                table_id=table_id or str(uuid4()),
                inspection_id=inspection.id,
                target_generation=generation,
                action="replace" if table_id else "create",
                request=request,
                state="accepted",
                claim_token=None,
                candidate_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add_all((operation, job))
            session.commit()
            return operation_view(operation)

    def claim(self, operation_id: str) -> ImportJob | None:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(ProjectExcelImportJobRow, operation_id)
            if row is None or row.state != "accepted":
                return None
            inspection = session.get(ProjectExcelInspectionRow, row.inspection_id)
            assert inspection is not None and row.table_id is not None
            _not_expired(inspection.expires_at)
            row.state = "running"
            row.claim_token = str(uuid4())
            row.updated_at = datetime.now(UTC)
            operation = session.get(ProjectOperationRow, operation_id)
            assert operation is not None
            operation.status = "running"
            operation.status_revision += 1
            operation.updated_at = row.updated_at
            session.commit()
            return ImportJob(
                row.operation_id,
                row.project_id,
                row.table_id,
                row.target_generation,
                row.action,
                row.request,
                row.claim_token,
                inspection.path,
            )

    def initialize(self, job: ImportJob) -> None:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            session.execute(text("PRAGMA defer_foreign_keys=ON"))
            self._owned(session, job)
            data, stage, now = job.request, job.request["_staging"], datetime.now(UTC)
            if job.action == "create":
                session.add(
                    DataTableRow(
                        id=job.table_id,
                        project_id=job.project_id,
                        published=False,
                        name=data["name"],
                        name_key=f"__excel_pending__:{job.operation_id}",
                        search_text=f"{data['name']}\n{data['description']}".casefold(),
                        description=data["description"],
                        source_kind="excel",
                        current_generation=job.generation,
                        table_revision=1,
                        identity=stage["identity"],
                        slot_definitions=[],
                        created_at=now,
                        updated_at=now,
                    )
                )
            session.add(
                DataGenerationRow(
                    id=job.generation,
                    project_id=job.project_id,
                    table_id=job.table_id,
                    identity=stage["identity"],
                    source=stage["source"],
                    created_at=now,
                )
            )
            for position, (field_id, definition) in enumerate(stage["fields"].items()):
                session.add(
                    DataFieldRow(
                        id=field_id,
                        project_id=job.project_id,
                        table_id=job.table_id,
                        dataset_generation=job.generation,
                        **definition,
                        writable=True,
                        formula=False,
                        field_revision=1,
                        position=position,
                    )
                )
            session.commit()

    def append(self, job: ImportJob, rows: list[dict]) -> None:
        if not rows:
            return
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            saved = self._owned(session, job)
            now = datetime.now(UTC)
            for row in rows:
                session.add(
                    DataRecordRow(
                        project_id=job.project_id,
                        table_id=job.table_id,
                        dataset_generation=job.generation,
                        key_type=row["keyType"],
                        key_value=row["keyValue"],
                        values_json=row["values"],
                        status_id=None,
                        current_environment_id=None,
                        record_slots=[],
                        content_revision=1,
                        status_revision=1,
                        link_revision=1,
                        deleted=False,
                        created_at=now,
                        updated_at=now,
                    )
                )
            saved.candidate_count += len(rows)
            saved.updated_at = now
            try:
                session.commit()
            except IntegrityError as error:
                raise ProjectError(
                    "EXCEL_DUPLICATE_IDENTITY", "来源列包含重复的记录身份。", 422
                ) from error

    def publish(self, job: ImportJob) -> dict:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            saved = self._owned(session, job)
            before = None
            if job.action == "replace":
                table = SqlAlchemyProjectDataCatalog._table(
                    session, job.project_id, job.table_id, True
                )
                self._require_impact(session, job.project_id, table, job.request)
                before = {
                    "datasetGeneration": table.current_generation,
                    "tableRevision": table.table_revision,
                }
                table.current_generation = job.generation
                table.table_revision += 1
                table.identity = job.request["_staging"]["identity"]
                table.source_kind = "excel"
            else:
                from .project_data import SqlAlchemyProjectData

                SqlAlchemyProjectData._guard_project_write(session, job.project_id)
                hidden_table = session.get(DataTableRow, job.table_id)
                assert hidden_table is not None
                table = hidden_table
                if (
                    session.scalar(
                        select(DataTableRow.id).where(
                            DataTableRow.project_id == job.project_id,
                            DataTableRow.name_key == table.name.casefold(),
                            DataTableRow.published.is_(True),
                        )
                    )
                    is not None
                ):
                    raise ProjectError(
                        "TABLE_NAME_CONFLICT", "数据表名称已被使用。", 409
                    )
                table.name_key = table.name.casefold()
                table.published = True
            now = datetime.now(UTC)
            table.updated_at = now
            result = {
                "table": table_to_dict(
                    _table(
                        table,
                        saved.candidate_count,
                        {
                            key: value
                            for key, value in job.request["_staging"]["source"].items()
                            if key in ("kind", "filename", "sheetName", "importedAt")
                        },
                    )
                ),
                "importedRecordCount": saved.candidate_count,
            }
            if job.action == "replace":
                result["previousDatasetGeneration"] = job.request[
                    "expectedDatasetGeneration"
                ]
            operation = session.get(ProjectOperationRow, job.operation_id)
            assert operation is not None
            operation.resource = {
                "type": "table",
                "projectId": job.project_id,
                "tableId": job.table_id,
            }
            operation.result = result
            operation.status = "succeeded"
            operation.status_revision += 1
            operation.updated_at = now
            operation.completed_at = now
            saved.state = "succeeded"
            saved.updated_at = now
            session.add(
                DataChangeRow(
                    id=str(uuid4()),
                    project_id=job.project_id,
                    operation_id=job.operation_id,
                    sequence=1,
                    resource=operation.resource,
                    origin="import",
                    before=before,
                    after=result["table"],
                    created_at=now,
                )
            )
            session.commit()
            return operation_view(operation)

    def fail(self, operation_id: str, error: dict, *, claim: str | None = None) -> None:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            saved = session.get(ProjectExcelImportJobRow, operation_id)
            if (
                saved is None
                or saved.state in ("succeeded", "failed")
                or (claim is not None and saved.claim_token != claim)
            ):
                return
            operation = session.get(ProjectOperationRow, operation_id)
            assert operation is not None
            now = datetime.now(UTC)
            saved.state = "failed"
            saved.updated_at = now
            operation.status = "failed"
            operation.error = error
            operation.status_revision += 1
            operation.updated_at = now
            operation.completed_at = now
            session.commit()

    def pending(self) -> list[str]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(ProjectExcelImportJobRow.operation_id).where(
                        ProjectExcelImportJobRow.state.in_(
                            ("accepted", "running", "publishing")
                        )
                    )
                )
            )

    @staticmethod
    def _owned(session: Session, job: ImportJob) -> ProjectExcelImportJobRow:
        row = session.get(ProjectExcelImportJobRow, job.operation_id)
        if row is None or row.state != "running" or row.claim_token != job.claim:
            raise ProjectError("OPERATION_CLAIM_LOST", "导入操作已停止。", 409)
        return row
