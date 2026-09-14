from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.projects.models import (
    ProjectError,
    ProjectOperation,
    ProjectRecord,
    project_to_dict,
)

from .models import ProjectOperationRow, ProjectRow


class SqlAlchemyProjects:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def create(self, record, operation):
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == operation.idempotency_key
                )
            )
            if existing:
                self._match(existing, operation)
                saved = _project_from_result(existing.result)
                saved_operation = _operation(existing)
                session.rollback()
                return saved, saved_operation
            try:
                session.add(_project_row(record))
                session.flush()
                done = operation.with_result(record.project_id, record)
                session.add(_operation_row(done))
                session.commit()
                return record, done
            except IntegrityError:
                session.rollback()
                raise ProjectError(
                    "PROJECT_NAME_CONFLICT",
                    "Project name is already in use",
                    409,
                    {
                        "fields": {"name": "Project name is already in use"},
                        "domainCode": "project_name_conflict",
                        "retryable": False,
                    },
                )

    def update(self, project_id, patch, expected_revision, operation):
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == operation.idempotency_key
                )
            )
            if existing:
                self._match(existing, operation)
                saved = _project_from_result(existing.result)
                saved_operation = _operation(existing)
                session.rollback()
                return saved, saved_operation
            row = session.get(ProjectRow, project_id)
            if not row or row.lifecycle_state == "deleted":
                session.rollback()
                raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
            if row.lifecycle_state == "closing":
                session.rollback()
                raise ProjectError("PROJECT_CLOSING", "Project is closing", 423)
            if row.lifecycle_state != "active":
                session.rollback()
                raise ProjectError(
                    "LIFECYCLE_CONFLICT", "Project cannot be edited", 409
                )
            current = _project(row)
            if current.management_revision != expected_revision:
                session.rollback()
                raise ProjectError(
                    "REVISION_CONFLICT",
                    "Project was modified",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": current.management_revision,
                        "current": project_to_dict(current),
                        "domainCode": "revision_conflict",
                        "retryable": False,
                    },
                )
            changed = current.patched(patch, datetime.now(UTC))
            try:
                row.name, row.name_key, row.description = (
                    changed.name,
                    changed.name.casefold(),
                    changed.description,
                )
                row.search_text = f"{changed.name} {changed.description}".casefold()
                row.default_resources, row.management_revision, row.updated_at = (
                    changed.default_resources,
                    changed.management_revision,
                    changed.updated_at,
                )
                session.flush()
                done = operation.with_result(project_id, changed)
                session.add(_operation_row(done))
                session.commit()
                return changed, done
            except IntegrityError:
                session.rollback()
                raise ProjectError(
                    "PROJECT_NAME_CONFLICT",
                    "Project name is already in use",
                    409,
                    {"fields": {"name": "Project name is already in use"}},
                )

    def get(self, project_id):
        with self._session_factory() as session:
            row = session.get(ProjectRow, project_id)
            return _project(row) if row else None

    def list(
        self, q=None, lifecycle_state=None, page=1, page_size=50, sort="-lastOpenedAt"
    ):
        with self._session_factory() as session:
            query = select(ProjectRow).where(ProjectRow.lifecycle_state != "deleted")
            if q:
                query = query.where(
                    ProjectRow.search_text.contains(
                        q.strip().casefold(), autoescape=True
                    )
                )
            if lifecycle_state:
                query = query.where(ProjectRow.lifecycle_state == lifecycle_state)
            total = (
                session.scalar(select(func.count()).select_from(query.subquery())) or 0
            )
            orders = {
                "name": (ProjectRow.name_key, ProjectRow.id),
                "-name": (ProjectRow.name_key.desc(), ProjectRow.id),
                "updatedAt": (ProjectRow.updated_at, ProjectRow.id),
                "-updatedAt": (ProjectRow.updated_at.desc(), ProjectRow.id),
                "lastOpenedAt": (
                    ProjectRow.last_opened_at.is_(None),
                    ProjectRow.last_opened_at,
                    ProjectRow.updated_at.desc(),
                    ProjectRow.id,
                ),
                "-lastOpenedAt": (
                    ProjectRow.last_opened_at.is_(None),
                    ProjectRow.last_opened_at.desc(),
                    ProjectRow.updated_at.desc(),
                    ProjectRow.id,
                ),
            }
            if sort not in orders:
                raise ProjectError(
                    "VALIDATION_ERROR",
                    "Invalid sort",
                    422,
                    {"fields": {"sort": "Invalid sort"}},
                )
            rows = session.scalars(
                query.order_by(*orders[sort])
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return [_project(row) for row in rows], total

    def open(self, project_id, now):
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(ProjectRow, project_id)
            if not row or row.lifecycle_state == "deleted":
                session.rollback()
                raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
            if row.lifecycle_state == "deleting":
                session.rollback()
                raise ProjectError("LIFECYCLE_CONFLICT", "Project is deleting", 409)
            row.last_opened_at = now
            session.flush()
            saved = _project(row)
            session.commit()
            return saved

    def get_operation(
        self, operation_id=None, key=None, project_id=None, workspace=False
    ):
        with self._session_factory() as session:
            query = select(ProjectOperationRow)
            query = (
                query.where(ProjectOperationRow.id == operation_id)
                if operation_id
                else query.where(ProjectOperationRow.idempotency_key == key)
            )
            if workspace:
                query = query.where(ProjectOperationRow.kind == "createProject")
            else:
                query = query.where(ProjectOperationRow.project_id == project_id)
            row = session.scalar(query)
            return _operation(row) if row else None

    def list_operations(
        self,
        project_id,
        page=1,
        page_size=50,
        kind=None,
        status=None,
        resource_type=None,
    ):
        with self._session_factory() as session:
            base = select(ProjectOperationRow).where(
                ProjectOperationRow.project_id == project_id
            )
            if kind:
                base = base.where(ProjectOperationRow.kind == kind)
            if status:
                base = base.where(ProjectOperationRow.status == status)
            if resource_type:
                base = base.where(
                    ProjectOperationRow.resource["type"].as_string() == resource_type
                )
            total = (
                session.scalar(select(func.count()).select_from(base.subquery())) or 0
            )
            rows = session.scalars(
                base.order_by(
                    ProjectOperationRow.created_at.desc(), ProjectOperationRow.id
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return [_operation(row) for row in rows], total

    @staticmethod
    def _match(existing, incoming):
        if (
            existing.kind != incoming.kind
            or existing.request_digest != incoming.request_digest
        ):
            raise ProjectError(
                "OPERATION_PAYLOAD_MISMATCH",
                "Idempotency key was used for another request",
                409,
                {"domainCode": "operation_payload_mismatch", "retryable": False},
            )


def _aware(value):
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def _project(row):
    return ProjectRecord(
        row.id,
        row.name,
        row.description,
        row.default_resources,
        row.management_revision,
        row.lifecycle_state,
        _aware(row.created_at),
        _aware(row.updated_at),
        _aware(row.last_opened_at),
    )


def _project_row(value):
    return ProjectRow(
        id=value.project_id,
        name=value.name,
        name_key=value.name.casefold(),
        description=value.description,
        search_text=f"{value.name} {value.description}".casefold(),
        default_resources=value.default_resources,
        management_revision=value.management_revision,
        lifecycle_state=value.lifecycle_state,
        created_at=value.created_at,
        updated_at=value.updated_at,
        last_opened_at=value.last_opened_at,
    )


def _operation(row):
    return ProjectOperation(
        row.id,
        row.project_id,
        row.idempotency_key,
        row.kind,
        row.request_digest,
        row.status,
        row.status_revision,
        row.resource,
        row.result,
        row.error,
        _aware(row.created_at),
        _aware(row.updated_at),
        _aware(row.completed_at),
    )


def _operation_row(value):
    return ProjectOperationRow(
        id=value.operation_id,
        project_id=value.project_id,
        idempotency_key=value.idempotency_key,
        kind=value.kind,
        request_digest=value.request_digest,
        status=value.status,
        status_revision=value.status_revision,
        resource=value.resource,
        result=_json_dates(value.result),
        error=value.error,
        created_at=value.created_at,
        updated_at=value.updated_at,
        completed_at=value.completed_at,
    )


def _json_dates(value):
    return (
        {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in value.items()}
        if value
        else value
    )


def _project_from_result(value):
    assert value
    return ProjectRecord(
        value["projectId"],
        value["name"],
        value["description"],
        value["defaultResources"],
        value["managementRevision"],
        value["lifecycleState"],
        datetime.fromisoformat(value["createdAt"]),
        datetime.fromisoformat(value["updatedAt"]),
        datetime.fromisoformat(value["lastOpenedAt"])
        if value["lastOpenedAt"]
        else None,
    )
