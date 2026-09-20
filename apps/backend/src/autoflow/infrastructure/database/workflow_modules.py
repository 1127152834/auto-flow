from __future__ import annotations

import copy
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.errors import WorkflowDocumentError
from autoflow.domain.workflows.modules import CustomModuleDraft, SavedCustomModule

from .workflow_models import (
    WorkflowCustomModuleRequestRow,
    WorkflowCustomModuleRow,
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _saved(row: WorkflowCustomModuleRow) -> SavedCustomModule:
    return SavedCustomModule(
        id=row.id,
        definition=copy.deepcopy(row.definition),
        dependencies=tuple(row.dependency_ids),
        revision=row.revision,
        usage_count=row.usage_count,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _response(value: SavedCustomModule) -> dict[str, object]:
    return {**value.to_payload(), "_dependencyIds": list(value.dependencies)}


def _from_response(value: dict[str, object]) -> SavedCustomModule:
    raw_dependencies = value.get("_dependencyIds", [])
    dependencies = raw_dependencies if isinstance(raw_dependencies, list) else []
    revision = value.get("revision")
    usage_count = value.get("usage_count")
    if not isinstance(revision, int) or not isinstance(usage_count, int):
        raise TypeError("invalid custom module receipt")
    return SavedCustomModule(
        id=str(value["id"]),
        definition={
            key: copy.deepcopy(item)
            for key, item in value.items()
            if key
            not in {
                "id",
                "revision",
                "usage_count",
                "created_at",
                "updated_at",
                "_dependencyIds",
            }
        },
        dependencies=tuple(str(item) for item in dependencies),
        revision=revision,
        usage_count=usage_count,
        created_at=datetime.fromisoformat(str(value["created_at"])),
        updated_at=datetime.fromisoformat(str(value["updated_at"])),
    )


class SqlAlchemyWorkflowModules:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _receipt(
        session: Session, client_request_id: str, request_digest: str
    ) -> WorkflowCustomModuleRequestRow | None:
        row = session.get(WorkflowCustomModuleRequestRow, client_request_id)
        if row is None:
            return None
        if row.request_digest != request_digest:
            raise WorkflowDocumentError(
                "IDEMPOTENCY_CONFLICT", "请求 ID 已用于不同内容", 409
            )
        return row

    def recover_save(
        self, client_request_id: str, request_digest: str
    ) -> SavedCustomModule | None:
        with self._session_factory() as session:
            previous = self._receipt(session, client_request_id, request_digest)
            return _from_response(previous.response) if previous is not None else None

    def create(
        self,
        module_id: str,
        draft: CustomModuleDraft,
        *,
        client_request_id: str,
        request_digest: str,
        now: datetime,
    ) -> SavedCustomModule:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            previous = self._receipt(session, client_request_id, request_digest)
            if previous is not None:
                session.rollback()
                return _from_response(previous.response)
            row = WorkflowCustomModuleRow(
                id=module_id,
                name=draft.name,
                definition=copy.deepcopy(draft.definition),
                dependency_ids=list(draft.dependencies),
                revision=1,
                usage_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError as error:
                session.rollback()
                raise WorkflowDocumentError(
                    "CUSTOM_MODULE_NAME_CONFLICT", "模块名称已存在", 409
                ) from error
            saved = _saved(row)
            session.add(
                WorkflowCustomModuleRequestRow(
                    id=client_request_id,
                    request_digest=request_digest,
                    kind="create",
                    module_id=module_id,
                    response=_response(saved),
                    created_at=now,
                )
            )
            session.commit()
            return saved

    def get(self, module_id: str) -> SavedCustomModule | None:
        with self._session_factory() as session:
            row = session.get(WorkflowCustomModuleRow, module_id)
            return _saved(row) if row is not None else None

    def list_all(self) -> tuple[SavedCustomModule, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(WorkflowCustomModuleRow).order_by(
                    WorkflowCustomModuleRow.updated_at.desc()
                )
            )
            return tuple(_saved(row) for row in rows)

    def update(
        self,
        module_id: str,
        draft: CustomModuleDraft,
        *,
        expected_revision: int,
        client_request_id: str,
        request_digest: str,
        now: datetime,
    ) -> SavedCustomModule:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            previous = self._receipt(session, client_request_id, request_digest)
            if previous is not None:
                session.rollback()
                return _from_response(previous.response)
            row = session.get(WorkflowCustomModuleRow, module_id)
            if row is None:
                session.rollback()
                raise WorkflowDocumentError("CUSTOM_MODULE_NOT_FOUND", "模块不存在", 404)
            if row.revision != expected_revision:
                current_revision = row.revision
                session.rollback()
                raise WorkflowDocumentError(
                    "CUSTOM_MODULE_REVISION_CONFLICT",
                    "模块已由其他窗口修改",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": current_revision,
                    },
                )
            row.name = draft.name
            row.definition = copy.deepcopy(draft.definition)
            row.dependency_ids = list(draft.dependencies)
            row.revision += 1
            row.updated_at = now
            try:
                session.flush()
            except IntegrityError as error:
                session.rollback()
                raise WorkflowDocumentError(
                    "CUSTOM_MODULE_NAME_CONFLICT", "模块名称已存在", 409
                ) from error
            saved = _saved(row)
            session.add(
                WorkflowCustomModuleRequestRow(
                    id=client_request_id,
                    request_digest=request_digest,
                    kind="update",
                    module_id=module_id,
                    response=_response(saved),
                    created_at=now,
                )
            )
            session.commit()
            return saved

    def delete(
        self,
        module_id: str,
        *,
        expected_revision: int,
        client_request_id: str,
        request_digest: str,
        now: datetime,
    ) -> None:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            previous = self._receipt(session, client_request_id, request_digest)
            if previous is not None:
                session.rollback()
                return
            row = session.get(WorkflowCustomModuleRow, module_id)
            if row is None:
                session.rollback()
                raise WorkflowDocumentError("CUSTOM_MODULE_NOT_FOUND", "模块不存在", 404)
            if row.revision != expected_revision:
                current_revision = row.revision
                session.rollback()
                raise WorkflowDocumentError(
                    "CUSTOM_MODULE_REVISION_CONFLICT",
                    "模块已由其他窗口修改",
                    409,
                    {
                        "expectedRevision": expected_revision,
                        "currentRevision": current_revision,
                    },
                )
            session.delete(row)
            session.add(
                WorkflowCustomModuleRequestRow(
                    id=client_request_id,
                    request_digest=request_digest,
                    kind="delete",
                    module_id=module_id,
                    response={"success": True},
                    created_at=now,
                )
            )
            session.commit()

    def increment_usage(self, module_id: str) -> SavedCustomModule:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(WorkflowCustomModuleRow, module_id)
            if row is None:
                session.rollback()
                raise WorkflowDocumentError("CUSTOM_MODULE_NOT_FOUND", "模块不存在", 404)
            row.usage_count += 1
            session.commit()
            session.refresh(row)
            return _saved(row)
