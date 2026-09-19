from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.identity import (
    RecordKey,
    RecordKeyType,
    encode_record_key,
)
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_claims import active_record_lease
from autoflow.infrastructure.database.project_data import (
    _completed,
    _operation,
    _operation_result,
    _operation_row,
)
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
    _status,
)
from autoflow.infrastructure.database.project_data_catalog import (
    _change as catalog_change,
)
from autoflow.infrastructure.database.project_data_models import (
    DataImpactRow,
    DataRecordRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
    _resource,
)
from autoflow.infrastructure.database.project_data_records import (
    _change as record_change,
)
from autoflow.infrastructure.database.project_data_status_batch_models import (
    DataStatusBatchBlockRow,
    DataStatusBatchRow,
)


class SqlAlchemyProjectDataDeletions:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def preview_status(
        self, project_id: str, table_id: str, status_id: str
    ) -> dict[str, Any]:
        target = _status_target(project_id, table_id, status_id)
        with self._session_factory() as session:
            session.execute(text("BEGIN"))
            report, facts = self._status_facts(session, project_id, table_id, status_id)
            session.rollback()
        return self._save_impact(project_id, "deleteStatus", target, report, facts)

    def preview_record(
        self, project_id: str, table_id: str, generation: str, key: RecordKey
    ) -> dict[str, Any]:
        target = _record_target(project_id, table_id, generation, key)
        with self._session_factory() as session:
            session.execute(text("BEGIN"))
            report, facts = self._record_facts(
                session, project_id, table_id, generation, key, check_lease=True
            )
            session.rollback()
        return self._save_impact(project_id, "deleteRecord", target, report, facts)

    def delete_status(
        self,
        project_id: str,
        table_id: str,
        status_id: str,
        expected_status: int,
        expected_table: int,
        impact: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = SqlAlchemyProjectDataCatalog._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            report, facts = self._status_facts(
                session, project_id, table_id, status_id, True
            )
            self._require_impact(
                session, project_id, "deleteStatus", report, facts, impact
            )
            table = self._table(session, project_id, table_id, True)
            status = self._status(session, project_id, table_id, status_id)
            SqlAlchemyProjectDataCatalog._cas(table.table_revision, expected_table)
            SqlAlchemyProjectDataCatalog._cas(
                status.status_revision, expected_status, "Status"
            )
            before = _status(status)
            status.deleted = True
            status.status_revision += 1
            table.table_revision += 1
            table.updated_at = datetime.now(UTC)
            after = {**_status(status), "deleted": True}
            result = {
                "action": "delete",
                "statusId": status_id,
                "deleted": True,
                "tableRevision": table.table_revision,
            }
            done = _completed(operation, result)
            session.add(_operation_row(done))
            session.flush()
            session.add(catalog_change(done, 1, before, after))
            session.commit()
            return result, done, False

    def delete_record(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
        expected_content: int,
        expected_status: int,
        expected_link: int,
        impact: int,
        operation: ProjectOperation,
    ) -> tuple[dict[str, Any], ProjectOperation, bool]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = SqlAlchemyProjectDataCatalog._existing(session, operation)
            if existing is not None:
                session.rollback()
                return _operation_result(existing), _operation(existing), True
            report, facts = self._record_facts(
                session, project_id, table_id, generation, key, True, check_lease=True
            )
            self._require_impact(
                session, project_id, "deleteRecord", report, facts, impact
            )
            table = SqlAlchemyProjectDataRecords._table(
                session, project_id, table_id, generation, True
            )
            row = self._required_record(session, generation, key)
            _record_cas(row, expected_content, expected_status, expected_link)
            fields = SqlAlchemyProjectDataRecords._fields(session, table)
            before = SqlAlchemyProjectDataRecords._snapshot(row, fields)
            row.deleted = True
            row.updated_at = datetime.now(UTC)
            after = SqlAlchemyProjectDataRecords._snapshot(row, fields)
            resource = _resource(before["ref"])
            result = {"target": resource, "deleted": True}
            done = _completed(replace(operation, resource=resource), result)
            session.add(_operation_row(done))
            session.flush()
            session.add(record_change(done, before, after))
            session.commit()
            return result, done, False

    def _save_impact(
        self,
        project_id: str,
        action: str,
        target: dict[str, Any],
        report: dict[str, Any],
        facts: str,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            now = datetime.now(UTC)
            saved = DataImpactRow(
                project_id=project_id,
                action=action,
                target=target,
                change_digest=_digest({"action": action, "target": target}),
                expected_revisions=report["expectedRevisions"],
                facts_digest=facts,
                report={},
                expires_at=now + timedelta(minutes=10),
            )
            session.add(saved)
            session.flush()
            report.update(impactRevision=saved.id, calculatedAt=now.isoformat())
            saved.report = report
            session.commit()
            return report

    @staticmethod
    def _require_impact(
        session: Session,
        project_id: str,
        action: str,
        report: dict[str, Any],
        facts: str,
        impact: int,
    ) -> None:
        saved = session.get(DataImpactRow, impact)
        if (
            saved is None
            or saved.project_id != project_id
            or saved.action != action
            or saved.target != report["target"]
            or saved.change_digest
            != _digest({"action": action, "target": report["target"]})
            or _utc(saved.expires_at) <= datetime.now(UTC)
            or saved.expected_revisions != report["expectedRevisions"]
            or saved.facts_digest != facts
            or saved.report.get("blockers")
            or report["blockers"]
        ):
            raise _stale(report["blockers"])

    @staticmethod
    def _table(
        session: Session, project_id: str, table_id: str, write: bool
    ) -> DataTableRow:
        return SqlAlchemyProjectDataCatalog._table(session, project_id, table_id, write)

    @staticmethod
    def _status(
        session: Session, project_id: str, table_id: str, status_id: str
    ) -> DataStatusRow:
        row = session.scalar(
            select(DataStatusRow).where(
                DataStatusRow.project_id == project_id,
                DataStatusRow.table_id == table_id,
                DataStatusRow.id == status_id,
                DataStatusRow.deleted.is_(False),
            )
        )
        if row is None:
            raise ProjectError("STATUS_NOT_FOUND", "Status was not found", 404)
        return row

    @staticmethod
    def _required_record(
        session: Session, generation: str, key: RecordKey
    ) -> DataRecordRow:
        row = session.get(DataRecordRow, (generation, key.type, key.value))
        if row is None or row.deleted:
            raise ProjectError("RECORD_NOT_FOUND", "Record was not found", 404)
        return row

    def _status_facts(
        self,
        session: Session,
        project_id: str,
        table_id: str,
        status_id: str,
        write: bool = False,
    ) -> tuple[dict[str, Any], str]:
        table = self._table(session, project_id, table_id, write)
        if write and table.source_kind not in {"local", "excel", "sheets"}:
            raise ProjectError(
                "SOURCE_WRITE_UNAVAILABLE", "Source does not support status writes", 412
            )
        status = self._status(session, project_id, table_id, status_id)
        project = session.get(ProjectRow, project_id)
        assert project is not None
        reference_count = 0
        reference_hasher = hashlib.sha256()
        refs: list[dict[str, Any]] = []
        for row in session.execute(
            select(
                DataRecordRow.dataset_generation,
                DataRecordRow.key_type,
                DataRecordRow.key_value,
            )
            .where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == table_id,
                DataRecordRow.dataset_generation == table.current_generation,
                DataRecordRow.deleted.is_(False),
                DataRecordRow.status_id == status_id,
            )
            .order_by(DataRecordRow.key_type, DataRecordRow.key_value)
            .execution_options(yield_per=500)
        ):
            ref = _record_target(
                project_id,
                table_id,
                row.dataset_generation,
                RecordKey(cast(RecordKeyType, row.key_type), row.key_value),
            )
            reference_count += 1
            reference_hasher.update(_json(ref) + b"\n")
            if len(refs) < 20:
                refs.append(ref)
        target = _status_target(project_id, table_id, status_id)
        blockers = _project_blockers(project, target) + [
            _blocker("STATUS_IN_USE", ref, "A current record uses this status")
            for ref in refs[:20]
        ]
        if _pending_status_destination(session, project_id, table_id, status_id):
            blockers.append(
                _blocker(
                    "STATUS_BATCH_DESTINATION_PENDING",
                    target,
                    "A pending batch status operation uses this status",
                )
            )
        revisions = {
            "tableRevision": table.table_revision,
            "statusRevision": status.status_revision,
        }
        report = {
            "target": target,
            "changeDigest": _digest({"action": "deleteStatus", "target": target}),
            "expectedRevisions": revisions,
            "impacts": [
                {
                    "code": "STATUS_DELETE",
                    "resource": target,
                    "message": f"Delete status; {reference_count} current references",
                    "blocking": bool(reference_count),
                }
            ],
            "blockers": blockers,
        }
        return report, _digest(
            {
                "revisions": revisions,
                "currentGeneration": table.current_generation,
                "projectLifecycle": project.lifecycle_state,
                "projectManagementRevision": project.management_revision,
                "referenceCount": reference_count,
                "referenceDigest": reference_hasher.hexdigest(),
            }
        )

    def _record_facts(
        self,
        session: Session,
        project_id: str,
        table_id: str,
        generation: str,
        key: RecordKey,
        write: bool = False,
        *,
        check_lease: bool = False,
    ) -> tuple[dict[str, Any], str]:
        table = SqlAlchemyProjectDataRecords._table(
            session, project_id, table_id, generation, write
        )
        row = self._required_record(session, generation, key)
        target = _record_target(project_id, table_id, generation, key)
        project = session.get(ProjectRow, project_id)
        assert project is not None
        blockers = _project_blockers(project, target)
        # Task capabilities validate ownership through their write cursor instead.
        if (
            check_lease
            and active_record_lease(session, project_id, table_id, generation, key)
            is not None
        ):
            blockers.append(
                _blocker(
                    "RECORD_IN_USE",
                    target,
                    "Record is currently used by a running task",
                )
            )
        if _pending_status_target(session, target["recordRef"]):
            blockers.append(
                _blocker(
                    "RECORD_STATUS_BATCH_PENDING",
                    target,
                    "A pending batch status operation references this record",
                )
            )
        if row.current_environment_id is not None:
            blockers.append(
                _blocker(
                    "RECORD_ENVIRONMENT_IN_USE",
                    target,
                    "Record has a current environment",
                )
            )
        active_slots: list[dict[str, Any]] = []
        for slot in row.record_slots:
            recognized, slot_target = _slot_ref(slot)
            if not recognized:
                blockers.append(
                    _blocker(
                        "RECORD_SLOT_UNSUPPORTED",
                        target,
                        "Record has an unsupported slot target",
                    )
                )
            elif slot_target is not None:
                active_slots.append(slot)
        if active_slots:
            blockers.append(
                _blocker("RECORD_SLOT_IN_USE", target, "Record has active record slots")
            )
        inbound_count = 0
        dependency_hasher = hashlib.sha256()
        candidates = session.execute(
            select(
                DataRecordRow.table_id,
                DataRecordRow.dataset_generation,
                DataRecordRow.key_type,
                DataRecordRow.key_value,
                DataRecordRow.record_slots,
            )
            .join(
                DataTableRow,
                (DataTableRow.project_id == DataRecordRow.project_id)
                & (DataTableRow.id == DataRecordRow.table_id)
                & (DataTableRow.current_generation == DataRecordRow.dataset_generation),
            )
            .where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.deleted.is_(False),
            )
            .order_by(
                DataRecordRow.table_id, DataRecordRow.key_type, DataRecordRow.key_value
            )
            .execution_options(yield_per=500)
        )
        for candidate in candidates:
            if (
                candidate.dataset_generation == generation
                and candidate.key_type == key.type
                and candidate.key_value == key.value
            ):
                continue
            ref = _record_target(
                project_id,
                candidate.table_id,
                candidate.dataset_generation,
                RecordKey(cast(RecordKeyType, candidate.key_type), candidate.key_value),
            )
            recognized_refs = [_slot_ref(slot) for slot in candidate.record_slots]
            if any(not recognized for recognized, _ in recognized_refs):
                dependency_hasher.update(_json(["unsupported", ref]) + b"\n")
                if len(blockers) < 20:
                    blockers.append(
                        _blocker(
                            "RECORD_SLOT_UNSUPPORTED",
                            ref,
                            "A current record has an unsupported slot target",
                        )
                    )
            if any(
                slot_target == target["recordRef"] for _, slot_target in recognized_refs
            ):
                inbound_count += 1
                dependency_hasher.update(_json(["reference", ref]) + b"\n")
                if len(blockers) < 20:
                    blockers.append(
                        _blocker(
                            "RECORD_REFERENCED",
                            ref,
                            "A current record slot references this record",
                        )
                    )
        revisions = {
            "tableRevision": table.table_revision,
            "contentRevision": row.content_revision,
            "statusRevision": row.status_revision,
            "linkRevision": row.link_revision,
        }
        report = {
            "target": target,
            "changeDigest": _digest({"action": "deleteRecord", "target": target}),
            "expectedRevisions": revisions,
            "impacts": [
                {
                    "code": "RECORD_DELETE",
                    "resource": target,
                    "message": f"Delete record; {inbound_count} inbound references",
                    "blocking": bool(blockers),
                }
            ],
            "blockers": blockers,
        }
        facts_value = {
            "revisions": revisions,
            "recordSlots": active_slots,
            "currentEnvironmentId": row.current_environment_id,
            "projectLifecycle": project.lifecycle_state,
            "projectManagementRevision": project.management_revision,
            "dependencyDigest": dependency_hasher.hexdigest(),
            "inboundCount": inbound_count,
        }
        return report, _digest(facts_value)


def _slot_ref(slot: object) -> tuple[bool, dict[str, Any] | None]:
    if not isinstance(slot, dict) or set(slot) != {"slotId", "target"}:
        return False, None
    try:
        if (
            not isinstance(slot["slotId"], str)
            or str(UUID(slot["slotId"])) != slot["slotId"]
        ):
            return False, None
    except (ValueError, TypeError, AttributeError):
        return False, None
    target = slot["target"]
    if target is None:
        return True, None
    return _valid_record_ref(target), target if isinstance(target, dict) else None


def _valid_record_ref(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "projectId",
        "tableId",
        "datasetGeneration",
        "recordKey",
    }:
        return False
    try:
        identities = (value["projectId"], value["tableId"], value["datasetGeneration"])
        if any(
            not isinstance(item, str) or str(UUID(item)) != item for item in identities
        ):
            return False
    except (ValueError, TypeError, AttributeError):
        return False
    key = value["recordKey"]
    if (
        not isinstance(key, dict)
        or set(key) != {"type", "value"}
        or not isinstance(key["type"], str)
        or key["type"] not in {"text", "integer", "uuid"}
        or not isinstance(key["value"], str)
    ):
        return False
    try:
        encode_record_key(RecordKey(cast(RecordKeyType, key["type"]), key["value"]))
    except ProjectError:
        return False
    return True


def _project_blockers(
    project: ProjectRow, target: dict[str, Any]
) -> list[dict[str, Any]]:
    if project.lifecycle_state == "active":
        return []
    return [
        _blocker(
            "PROJECT_READ_ONLY",
            target,
            "Project lifecycle does not allow deletion",
        )
    ]


def _pending_status_target(session: Session, record_ref: dict[str, Any]) -> bool:
    if not inspect(session.connection()).has_table(
        DataStatusBatchBlockRow.__tablename__
    ):
        return False
    blocks = session.scalars(
        select(DataStatusBatchBlockRow)
        .join(
            DataStatusBatchRow,
            DataStatusBatchRow.operation_id == DataStatusBatchBlockRow.operation_id,
        )
        .join(
            ProjectOperationRow,
            ProjectOperationRow.id == DataStatusBatchBlockRow.operation_id,
        )
        .where(
            DataStatusBatchBlockRow.state == "notStarted",
            DataStatusBatchRow.cancel_requested.is_(False),
            ProjectOperationRow.status.in_(("accepted", "running", "reconciling")),
        )
    ).all()
    return any(
        target.get("recordRef") == record_ref
        for block in blocks
        for target in block.targets
    )


def _pending_status_destination(
    session: Session, project_id: str, table_id: str, status_id: str
) -> bool:
    if not inspect(session.connection()).has_table(DataStatusBatchRow.__tablename__):
        return False
    return (
        session.scalar(
            select(DataStatusBatchRow.operation_id)
            .join(
                ProjectOperationRow,
                ProjectOperationRow.id == DataStatusBatchRow.operation_id,
            )
            .where(
                DataStatusBatchRow.project_id == project_id,
                DataStatusBatchRow.table_id == table_id,
                DataStatusBatchRow.status_id == status_id,
                DataStatusBatchRow.cancel_requested.is_(False),
                ProjectOperationRow.status.in_(("accepted", "running", "reconciling")),
            )
            .limit(1)
        )
        is not None
    )


def _status_target(project_id: str, table_id: str, status_id: str) -> dict[str, Any]:
    return {
        "type": "status",
        "projectId": project_id,
        "tableId": table_id,
        "statusId": status_id,
    }


def _record_target(
    project_id: str, table_id: str, generation: str, key: RecordKey
) -> dict[str, Any]:
    return {
        "type": "record",
        "recordRef": {
            "projectId": project_id,
            "tableId": table_id,
            "datasetGeneration": generation,
            "recordKey": {"type": key.type, "value": key.value},
        },
    }


def _record_cas(row: DataRecordRow, content: int, status: int, link: int) -> None:
    for current, expected, name in (
        (row.content_revision, content, "Content"),
        (row.status_revision, status, "Status"),
        (row.link_revision, link, "Link"),
    ):
        if current != expected:
            raise ProjectError(
                "REVISION_CONFLICT",
                f"{name} was modified",
                409,
                {
                    "expectedRevision": expected,
                    "currentRevision": current,
                    "domainCode": "revision_conflict",
                    "retryable": False,
                },
            )


def _blocker(code: str, resource: dict[str, Any], message: str) -> dict[str, Any]:
    return {"code": code, "resource": resource, "state": "blocked", "message": message}


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _stale(blockers: list[dict[str, Any]]) -> ProjectError:
    return ProjectError(
        "PRECONDITION_FAILED",
        "Recalculate the deletion impact before saving",
        412,
        {"blockers": blockers, "retryable": False},
    )
