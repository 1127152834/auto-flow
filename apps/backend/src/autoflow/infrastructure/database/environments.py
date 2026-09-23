from __future__ import annotations

import builtins
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.environments.models import (
    EnvironmentInstance,
    EnvironmentOccupancy,
    EnvironmentRef,
    ManualStatus,
    PersistentEnvironment,
)
from autoflow.domain.environments.rules import (
    LIVE_INSTANCE_STATES,
    check_live_capacity,
    environment_error,
    occupy_environment,
    resolve_environment_source,
)
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.domain.workflows.runtime import TERMINAL_STATUSES
from autoflow.infrastructure.database.environment_models import (
    ProjectEndOperationRow,
    ProjectEnvironmentInstanceRow,
    ProjectEnvironmentOccupancyRow,
    ProjectEnvironmentRow,
    ProjectEnvironmentSaveRow,
    ProjectManualItemRow,
)
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_data_models import (
    DataImpactRow,
    DataRecordRow,
)
from autoflow.infrastructure.database.project_run_models import ProjectTaskRow
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow


def _manual_order(sort: str | None):
    """Manual item ordering stays explicit: soonest retention first, or most recent update."""
    if sort == "expiresAt":
        # SQLite sorts NULL first ascending; items without a deadline belong last.
        return (
            ProjectManualItemRow.expires_at.is_(None),
            ProjectManualItemRow.expires_at.asc(),
            ProjectManualItemRow.id,
        )
    return (ProjectManualItemRow.updated_at.desc(), ProjectManualItemRow.id)


class SqlAlchemyEnvironments:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def list(self, project_id: str, **query):
        with self._session_factory() as session:
            self._project(session, project_id)
            statement = select(ProjectEnvironmentRow).where(
                ProjectEnvironmentRow.project_id == project_id,
                ProjectEnvironmentRow.state != "deleted",
            )
            state = query.get("state")
            if state:
                statement = statement.where(ProjectEnvironmentRow.state == state)
            q = (query.get("q") or "").strip()
            if q:
                pattern = f"%{q.casefold()}%"
                statement = statement.where(
                    or_(
                        func.lower(ProjectEnvironmentRow.name).like(pattern),
                        func.lower(ProjectEnvironmentRow.notes).like(pattern),
                    )
                )
            sort = query.get("sort") or "-updatedAt"
            order = {
                "name": (ProjectEnvironmentRow.name_key, ProjectEnvironmentRow.id),
                "-name": (
                    ProjectEnvironmentRow.name_key.desc(),
                    ProjectEnvironmentRow.id,
                ),
                "updatedAt": (ProjectEnvironmentRow.updated_at, ProjectEnvironmentRow.id),
                "-updatedAt": (
                    ProjectEnvironmentRow.updated_at.desc(),
                    ProjectEnvironmentRow.id,
                ),
            }.get(sort)
            if order is None:
                raise environment_error(
                    "VALIDATION_ERROR",
                    "Invalid sort",
                    422,
                    {"fields": {"sort": "Unsupported sort"}},
                )
            page = query.get("page") or 1
            page_size = query.get("page_size") or 50
            total = session.scalar(select(func.count()).select_from(statement.subquery()))
            rows = session.scalars(
                statement.order_by(*order).offset((page - 1) * page_size).limit(page_size)
            ).all()
            return [_environment(row) for row in rows], int(total or 0)

    def get(self, project_id: str, environment_id: str) -> PersistentEnvironment:
        with self._session_factory() as session:
            return _environment(self._environment(session, project_id, environment_id))

    def get_with_instance(self, project_id: str, environment_id: str):
        with self._session_factory() as session:
            environment = _environment(
                self._environment(session, project_id, environment_id)
            )
            occupancy = session.get(ProjectEnvironmentOccupancyRow, environment_id)
            instance = None
            if occupancy is not None:
                row = session.get(ProjectEnvironmentInstanceRow, occupancy.instance_id)
                if row is not None:
                    instance = _instance(row)
            return environment, instance

    def update_metadata(
        self,
        project_id: str,
        environment_id: str,
        patch: dict[str, str],
        expected_revision: int,
        operation: ProjectOperation,
    ):
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == operation.idempotency_key
                )
            )
            if existing:
                self._match(existing, operation)
                saved = _environment(
                    self._environment(session, project_id, environment_id)
                )
                session.rollback()
                return saved, _operation(existing), True
            row = self._environment(session, project_id, environment_id, writable=True)
            if row.metadata_revision != expected_revision:
                session.rollback()
                raise environment_error(
                    "ENVIRONMENT_METADATA_CONFLICT",
                    "Environment metadata has changed",
                    409,
                    {
                        "domainCode": "environment_metadata_conflict",
                        "expectedRevision": expected_revision,
                        "currentRevision": row.metadata_revision,
                    },
                )
            now = datetime.now(UTC)
            if "name" in patch:
                row.name = patch["name"]
                row.name_key = patch["name"].casefold()
            if "notes" in patch:
                row.notes = patch["notes"]
            row.metadata_revision += 1
            row.updated_at = now
            try:
                session.flush()
            except IntegrityError as error:
                session.rollback()
                raise environment_error(
                    "IDENTITY_CONFLICT",
                    "Environment name is already in use",
                    409,
                    {"fields": {"name": "Environment name is already in use"}},
                ) from error
            done = _complete(operation, _jsonable(_environment(row).to_dict()), now)
            session.add(_operation_row(done))
            session.commit()
            return _environment(row), done, False

    def create_ready(
        self,
        record: PersistentEnvironment,
        digest: str,
        *,
        created_from_source: str = "newFromProfile",
        created_from_task_id: str | None = None,
    ) -> PersistentEnvironment:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = session.get(ProjectEnvironmentRow, record.ref.environment_id)
            if existing is not None:
                # A retried save after a lost response republishes the same
                # environment; the durable row wins over the replay payload.
                session.rollback()
                return _environment(existing)
            session.add(
                ProjectEnvironmentRow(
                    id=record.ref.environment_id,
                    project_id=record.ref.project_id,
                    name=record.name,
                    name_key=record.name.casefold(),
                    notes=record.notes,
                    state=record.state,
                    profile_id=record.profile_id,
                    content_generation=record.ref.content_generation,
                    metadata_revision=record.ref.metadata_revision,
                    current_digest=digest,
                    created_from_source=created_from_source,
                    created_from_task_id=created_from_task_id,
                    unavailable_reason=None,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                )
            )
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise environment_error(
                    "IDENTITY_CONFLICT",
                    "Environment name is already in use",
                    409,
                    {"fields": {"name": "Environment name is already in use"}},
                ) from error
            return record

    def publish_update(
        self,
        project_id: str,
        environment_id: str,
        digest: str,
        *,
        generation: int | None = None,
    ) -> PersistentEnvironment:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = self._environment(session, project_id, environment_id, writable=True)
            if generation is not None and generation <= row.content_generation:
                # A save that read the source before a newer publish completed
                # must not overwrite the newer content with its stale snapshot.
                raise environment_error(
                    "SAVE_GENERATION_CONFLICT",
                    "Saved environment content has changed",
                    409,
                    {
                        "domainCode": "save_generation_conflict",
                        "expectedRevision": generation,
                        "currentRevision": row.content_generation,
                    },
                )
            row.content_generation = generation or row.content_generation + 1
            row.current_digest = digest
            row.updated_at = datetime.now(UTC)
            session.commit()
            return _environment(row)

    def reserve_instance(self, record: EnvironmentInstance, occupancy: EnvironmentOccupancy | None):
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            self.reserve_instance_in_session(session, record, occupancy)
            session.commit()
            return record

    def reserve_instance_in_session(
        self, session: Session, record: EnvironmentInstance,
        occupancy: EnvironmentOccupancy | None, *, max_live_instances: int | None = None,
    ) -> EnvironmentInstance:
        self._project(session, record.project_id)
        if max_live_instances is not None:
            count = session.scalar(select(func.count()).select_from(
                ProjectEnvironmentInstanceRow
            ).where(ProjectEnvironmentInstanceRow.state.in_(tuple(LIVE_INSTANCE_STATES))))
            check_live_capacity(int(count or 0), max_live_instances)
        if occupancy is not None:
            current = session.get(ProjectEnvironmentOccupancyRow, occupancy.environment_id)
            occupy_environment(
                occupancy.environment_id, occupancy.instance_id,
                occupancy.holder_kind, occupancy.holder_id,
                _occupancy(current) if current else None,
            )
            if current is None:
                session.add(
                    ProjectEnvironmentOccupancyRow(
                        environment_id=occupancy.environment_id,
                        instance_id=occupancy.instance_id,
                        holder_kind=occupancy.holder_kind,
                        holder_id=occupancy.holder_id,
                        created_at=record.created_at,
                    )
                )
        session.add(_instance_row(record))
        session.flush()
        return record

    def resolve_source_in_session(
        self, session: Session, project_id: str, policy: dict[str, Any],
        inputs: dict[str, dict[str, Any]] | None = None,
    ):
        project = self._project(session, project_id)
        environments = session.scalars(select(ProjectEnvironmentRow).where(
            ProjectEnvironmentRow.project_id == project_id,
            ProjectEnvironmentRow.state != "deleted",
        )).all()
        return resolve_environment_source(
            policy, project_id=project_id,
            project_default_profile_id=(project.default_resources or {}).get("profileId"),
            inputs=inputs,
            environments={row.id: _environment(row) for row in environments},
        )

    def disposable_task_instances(self, instance_id: str | None = None) -> builtins.list[EnvironmentInstance]:
        """Only terminal task copies without outstanding retention/manual ownership."""
        with self._session_factory() as session:
            statement = select(ProjectEnvironmentInstanceRow).join(
                WorkflowRunRow, WorkflowRunRow.id == ProjectEnvironmentInstanceRow.active_run_id,
            ).join(
                ProjectTaskRow, ProjectTaskRow.id == ProjectEnvironmentInstanceRow.active_task_id,
            ).where(
                ProjectTaskRow.run_id == WorkflowRunRow.id,
                ProjectTaskRow.project_id == ProjectEnvironmentInstanceRow.project_id,
                WorkflowRunRow.status.in_(TERMINAL_STATUSES),
                ProjectEnvironmentInstanceRow.maintenance_operation_id.is_(None),
                ProjectEnvironmentInstanceRow.state.in_(
                    ("reserved", "starting", "active", "closing", "closed", "cleaning", "cleanup_failed")
                ),
                ~select(ProjectManualItemRow.id).where(
                    ProjectManualItemRow.instance_id == ProjectEnvironmentInstanceRow.id,
                ).exists(),
            )
            if instance_id is not None:
                statement = statement.where(ProjectEnvironmentInstanceRow.id == instance_id)
            result = []
            for row in session.scalars(statement):
                operations = session.scalars(select(ProjectOperationRow).where(
                    ProjectOperationRow.project_id == row.project_id,
                    ProjectOperationRow.kind == "saveEnvironment",
                ))
                protected = False
                for operation in operations:
                    resource = operation.resource
                    outcome = operation.result or {}
                    if outcome.get("phase") == "completed" and outcome.get("complete") is True:
                        continue
                    if resource.get("retainEnvironment") is False:
                        continue
                    target = resource.get("instanceId") or (outcome.get("instance") or {}).get("instanceId")
                    # Legacy commands lack instance identity. An unresolved save
                    # cannot authorize automatic deletion of any possible copy.
                    if target is None or target == row.id:
                        protected = True
                        break
                if not protected:
                    result.append(_instance(row))
            return result

    def set_instance_state(self, instance_id: str, state: str) -> EnvironmentInstance:
        with self._session_factory() as session:
            row = session.get(ProjectEnvironmentInstanceRow, instance_id)
            if row is None:
                raise environment_error(
                    "NOT_FOUND", "Environment instance was not found", 404
                )
            row.state = state
            row.updated_at = datetime.now(UTC)
            session.commit()
            return _instance(row)

    def release_occupancy(self, environment_id: str, instance_id: str) -> None:
        with self._session_factory() as session:
            row = session.get(ProjectEnvironmentOccupancyRow, environment_id)
            if row is not None and row.instance_id == instance_id:
                session.delete(row)
                session.commit()

    def list_instances(self, project_id: str, **query):
        with self._session_factory() as session:
            self._project(session, project_id)
            statement = select(ProjectEnvironmentInstanceRow).where(
                ProjectEnvironmentInstanceRow.project_id == project_id
            )
            state = query.get("state")
            if state:
                statement = statement.where(ProjectEnvironmentInstanceRow.state == state)
            task_id = query.get("task_id")
            if task_id:
                statement = statement.where(
                    ProjectEnvironmentInstanceRow.active_task_id == task_id
                )
            run_id = query.get("run_id")
            if run_id:
                statement = statement.where(
                    ProjectEnvironmentInstanceRow.active_run_id == run_id
                )
            page = query.get("page") or 1
            page_size = query.get("page_size") or 50
            total = session.scalar(select(func.count()).select_from(statement.subquery()))
            rows = session.scalars(
                statement.order_by(
                    ProjectEnvironmentInstanceRow.updated_at.desc(),
                    ProjectEnvironmentInstanceRow.id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return [_instance(row) for row in rows], int(total or 0)

    def get_instance(self, project_id: str, instance_id: str) -> EnvironmentInstance:
        with self._session_factory() as session:
            row = session.get(ProjectEnvironmentInstanceRow, instance_id)
            if row is None or row.project_id != project_id:
                raise environment_error(
                    "NOT_FOUND", "Environment instance was not found", 404
                )
            return _instance(row)

    def bind_records(
        self, project_id: str, environment_id: str, results: builtins.list[Any]
    ) -> None:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            now = datetime.now(UTC)
            for result in results:
                record_ref = result.record_ref
                row = session.get(
                    DataRecordRow,
                    (
                        record_ref["datasetGeneration"],
                        record_ref["recordKey"]["type"],
                        record_ref["recordKey"]["value"],
                    ),
                )
                if (
                    row is None
                    or row.project_id != project_id
                    or row.table_id != record_ref["tableId"]
                    or row.deleted
                ):
                    session.rollback()
                    raise environment_error(
                        "ASSOCIATION_TARGET_MISSING",
                        "Association target was not found",
                        404,
                        {"domainCode": "association_target_missing", "record": record_ref},
                    )
                expected_revision = result.link_revision - int(result.changed)
                if (row.link_revision != expected_revision
                        or row.current_environment_id != result.previous_environment_id):
                    raise environment_error(
                        "LINK_REVISION_CONFLICT", "Record environment link has changed", 409,
                        {"record": record_ref, "expectedRevision": expected_revision,
                         "currentRevision": row.link_revision},
                    )
                if not result.changed:
                    continue
                row.current_environment_id = result.environment_id
                row.link_revision = result.link_revision
                row.updated_at = now
            session.commit()

    def map_environments(self, project_id: str) -> dict[str, PersistentEnvironment]:
        items, _total = self.list(project_id, page=1, page_size=200, sort="-updatedAt")
        return {item.ref.environment_id: item for item in items}

    def find_instance_by_task(self, project_id: str, task_id: str) -> EnvironmentInstance | None:
        items, _total = self.list_instances(project_id, task_id=task_id, page=1, page_size=1)
        return items[0] if items else None

    def active_instance_for_run_request(self, run_request_id: str) -> EnvironmentInstance | None:
        with self._session_factory() as session:
            run = session.scalar(select(WorkflowRunRow).where(
                WorkflowRunRow.run_request_id == run_request_id,
            ))
            if run is None:
                raise environment_error("END_ACCESS_REVOKED", "运行身份不存在", 409)
            task = session.scalar(select(ProjectTaskRow).where(ProjectTaskRow.run_id == run.id))
            if task is None:
                return None
            if run.status != "running":
                raise environment_error("END_ACCESS_REVOKED", "运行已失去浏览器控制权", 409)
            instances = session.scalars(select(ProjectEnvironmentInstanceRow).where(
                ProjectEnvironmentInstanceRow.project_id == task.project_id,
                ProjectEnvironmentInstanceRow.active_task_id == task.id,
                ProjectEnvironmentInstanceRow.active_run_id == run.id,
            )).all()
            if len(instances) != 1 or instances[0].state != "active":
                raise environment_error("ENVIRONMENT_UNAVAILABLE", "任务环境尚未准备完成", 409)
            instance = instances[0]
            if instance.environment_id is not None:
                occupancy = session.get(ProjectEnvironmentOccupancyRow, instance.environment_id)
                if occupancy is None or occupancy.instance_id != instance.id or occupancy.holder_id != task.id:
                    raise environment_error("END_ACCESS_REVOKED", "任务环境占用已失效", 409)
            return _instance(instance)

    def count_live_instances(self, project_id: str | None = None) -> int:
        with self._session_factory() as session:
            statement = select(func.count()).select_from(ProjectEnvironmentInstanceRow).where(
                ProjectEnvironmentInstanceRow.state.in_(tuple(LIVE_INSTANCE_STATES))
            )
            if project_id:
                statement = statement.where(
                    ProjectEnvironmentInstanceRow.project_id == project_id
                )
            return int(session.scalar(statement) or 0)

    def operation_by_key(self, key: str):
        with self._session_factory() as session:
            row = session.scalar(
                select(ProjectOperationRow).where(ProjectOperationRow.idempotency_key == key)
            )
            return _operation(row) if row else None

    def load_bind_targets(self, project_id: str, requested: builtins.list[dict[str, Any]]):
        from autoflow.domain.environments.models import BindTarget

        with self._session_factory() as session:
            targets: builtins.list[BindTarget] = []
            for item in requested:
                record_ref = item["recordRef"]
                row = session.get(
                    DataRecordRow,
                    (
                        record_ref["datasetGeneration"],
                        record_ref["recordKey"]["type"],
                        record_ref["recordKey"]["value"],
                    ),
                )
                if (
                    row is None
                    or row.project_id != project_id
                    or row.table_id != record_ref["tableId"]
                    or row.deleted
                ):
                    raise environment_error(
                        "ASSOCIATION_TARGET_MISSING",
                        "Association target was not found",
                        404,
                        {"domainCode": "association_target_missing", "record": record_ref},
                    )
                targets.append(
                    BindTarget(
                        record_ref,
                        item["expectedLinkRevision"],
                        bool(item.get("replaceAllowed")),
                        row.current_environment_id,
                        row.link_revision,
                    )
                )
            return targets

    def record_save(
        self,
        save_id: str,
        project_id: str,
        instance_id: str,
        environment_id: str | None,
        mode: str,
        phase: str,
        expected_content_generation: int | None,
        published_content_generation: int | None,
        candidate_digest: str | None,
        name: str | None,
        operation_id: str,
        now,
    ) -> None:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(ProjectEnvironmentSaveRow, save_id)
            if row is None:
                session.add(
                    ProjectEnvironmentSaveRow(
                        id=save_id,
                        project_id=project_id,
                        instance_id=instance_id,
                        environment_id=environment_id,
                        mode=mode,
                        phase=phase,
                        expected_content_generation=expected_content_generation,
                        published_content_generation=published_content_generation,
                        candidate_digest=candidate_digest,
                        name=name,
                        operation_id=operation_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                row.environment_id = environment_id
                row.phase = phase
                row.published_content_generation = published_content_generation
                row.candidate_digest = candidate_digest
                row.updated_at = now
            session.commit()

    def save_by_operation(self, operation_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ProjectEnvironmentSaveRow).where(
                    ProjectEnvironmentSaveRow.operation_id == operation_id
                )
            )
            if row is None:
                return None
            return {
                "id": row.id,
                "projectId": row.project_id,
                "instanceId": row.instance_id,
                "environmentId": row.environment_id,
                "mode": row.mode,
                "phase": row.phase,
                "expectedContentGeneration": row.expected_content_generation,
                "publishedContentGeneration": row.published_content_generation,
                "candidateDigest": row.candidate_digest,
                "name": row.name,
                "operationId": row.operation_id,
            }

    def record_end(
        self,
        end_id: str,
        project_id: str,
        task_id: str,
        run_id: str,
        phase: str,
        retain_environment: bool,
        save_operation_id: str | None,
        intended_result: dict[str, Any],
        targets: builtins.list[Any],
        association_result: dict[str, Any] | None,
        operation_id: str,
        now,
    ) -> None:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(ProjectEndOperationRow, end_id)
            if row is None:
                session.add(
                    ProjectEndOperationRow(
                        id=end_id,
                        project_id=project_id,
                        task_id=task_id,
                        run_id=run_id,
                        phase=phase,
                        retain_environment=retain_environment,
                        save_operation_id=save_operation_id,
                        intended_result=intended_result,
                        targets=targets,
                        association_result=association_result,
                        operation_id=operation_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                row.phase = phase
                row.save_operation_id = save_operation_id
                row.association_result = association_result
                row.updated_at = now
            session.commit()

    def end_by_operation(self, operation_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ProjectEndOperationRow).where(
                    ProjectEndOperationRow.operation_id == operation_id
                )
            )
            if row is None:
                return None
            return {
                "id": row.id,
                "projectId": row.project_id,
                "taskId": row.task_id,
                "runId": row.run_id,
                "phase": row.phase,
                "retainEnvironment": row.retain_environment,
                "saveOperationId": row.save_operation_id,
                "intendedResult": row.intended_result,
                "targets": row.targets,
                "associationResult": row.association_result,
                "operationId": row.operation_id,
            }

    def accept_operation(self, operation: ProjectOperation):
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == operation.idempotency_key
                )
            )
            if existing:
                self._match(existing, operation)
                session.rollback()
                return _operation(existing), True
            session.add(_operation_row(operation))
            session.commit()
            return operation, False

    def complete_operation(self, operation: ProjectOperation, result: dict[str, Any] | None, error: dict[str, Any] | None, now):
        from dataclasses import replace

        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == operation.idempotency_key
                )
            )
            done = replace(
                operation,
                status="failed" if error else "succeeded",
                status_revision=2,
                result=_jsonable(result) if result is not None else None,
                error=error,
                updated_at=now,
                completed_at=now,
            )
            if existing:
                existing.status = done.status
                existing.status_revision = done.status_revision
                existing.result = done.result
                existing.error = done.error
                existing.updated_at = now
                existing.completed_at = now
            else:
                session.add(_operation_row(done))
            session.commit()
            return done


    def delete_impact(
        self, project_id: str, environment_id: str, action: str
    ) -> dict[str, Any]:
        if action != "delete":
            raise environment_error(
                "VALIDATION_ERROR",
                "Unsupported impact action",
                422,
                {"fields": {"action": "Only delete impact is available"}},
            )
        with self._session_factory() as session:
            session.execute(text("BEGIN"))
            row = self._environment(session, project_id, environment_id, writable=False)
            facts = _delete_facts(session, project_id, row)
            revision, generation = row.metadata_revision, row.content_generation
            session.rollback()
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            saved = DataImpactRow(
                project_id=project_id,
                action="deleteEnvironment",
                target={
                    "type": "environment",
                    "projectId": project_id,
                    "environmentId": environment_id,
                },
                change_digest=hashlib.sha256(b"deleteEnvironment").hexdigest(),
                expected_revisions={
                    "metadataRevision": revision,
                    "contentGeneration": generation,
                },
                facts_digest=_digest(facts),
                report={},
                expires_at=datetime.now(UTC) + IMPACT_TTL,
            )
            session.add(saved)
            session.flush()
            saved.report = {
                "impacts": facts["impacts"],
                "blockers": facts["blockers"],
                "impactRevision": saved.id,
            }
            session.commit()
            return saved.report

    def delete_environment(
        self,
        project_id: str,
        environment_id: str,
        operation: ProjectOperation,
        *,
        impact_revision: int,
        expected_metadata_revision: int,
        expected_content_generation: int,
    ) -> tuple[dict[str, Any], ProjectOperation]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == operation.idempotency_key
                )
            )
            if existing:
                self._match(existing, operation)
                result = existing.result or {}
                session.rollback()
                return result, _operation(existing)
            row = self._environment(session, project_id, environment_id, writable=True)
            if row.metadata_revision != expected_metadata_revision:
                session.rollback()
                raise environment_error(
                    "ENVIRONMENT_METADATA_CONFLICT",
                    "Environment metadata has changed",
                    409,
                    {
                        "domainCode": "environment_metadata_conflict",
                        "expectedRevision": expected_metadata_revision,
                        "currentRevision": row.metadata_revision,
                    },
                )
            if row.content_generation != expected_content_generation:
                session.rollback()
                raise environment_error(
                    "ENVIRONMENT_CONTENT_CONFLICT",
                    "Environment content has changed",
                    409,
                    {
                        "domainCode": "environment_content_conflict",
                        "expectedGeneration": expected_content_generation,
                        "currentGeneration": row.content_generation,
                    },
                )
            facts = _delete_facts(session, project_id, row)
            saved = session.get(DataImpactRow, impact_revision)
            if (
                type(impact_revision) is not int
                or saved is None
                or saved.project_id != project_id
                or saved.action != "deleteEnvironment"
                or (saved.target or {}).get("environmentId") != environment_id
                or _aware(saved.expires_at) <= datetime.now(UTC)
                or saved.facts_digest != _digest(facts)
            ):
                session.rollback()
                raise environment_error(
                    "PRECONDITION_FAILED",
                    "重新执行删除影响检查后再提交",
                    412,
                    {"blockers": facts["blockers"], "retryable": False},
                )
            if facts["blockers"]:
                session.rollback()
                raise environment_error(
                    "ENVIRONMENT_BUSY",
                    "Environment still has unresolved work",
                    409,
                    {
                        "blockers": facts["blockers"],
                        "domainCode": "environment_busy",
                        "retryable": False,
                    },
                )
            now = datetime.now(UTC)
            detached = 0
            for record in session.scalars(
                select(DataRecordRow).where(
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.current_environment_id == environment_id,
                )
            ):
                record.current_environment_id = None
                record.link_revision += 1
                detached += 1
            session.execute(
                delete(ProjectEnvironmentOccupancyRow).where(
                    ProjectEnvironmentOccupancyRow.environment_id == environment_id
                )
            )
            for save in session.scalars(
                select(ProjectEnvironmentSaveRow).where(
                    ProjectEnvironmentSaveRow.environment_id == environment_id
                )
            ):
                save.environment_id = None
            for instance in session.scalars(
                select(ProjectEnvironmentInstanceRow).where(
                    ProjectEnvironmentInstanceRow.environment_id == environment_id
                )
            ):
                instance.environment_id = None
            session.execute(
                delete(ProjectEnvironmentRow).where(ProjectEnvironmentRow.id == environment_id)
            )
            result = {
                "target": {
                    "type": "environment",
                    "projectId": project_id,
                    "environmentId": environment_id,
                },
                "deleted": True,
                "detachedRecordCount": detached,
            }
            done = replace(
                operation,
                status="succeeded",
                status_revision=2,
                result=result,
                updated_at=now,
                completed_at=now,
            )
            session.add(_operation_row(done))
            session.commit()
            return result, done

    def linked_record_count(self, project_id: str, environment_id: str) -> int:
        return len(self.list_linked_records(project_id, environment_id))

    def linked_record_counts(
        self, project_id: str, environment_ids: builtins.list[str]
    ) -> dict[str, int]:
        if not environment_ids:
            return {}
        with self._session_factory() as session:
            rows = session.execute(
                select(
                    DataRecordRow.current_environment_id,
                    func.count(),
                )
                .where(
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.current_environment_id.in_(environment_ids),
                    DataRecordRow.deleted.is_(False),
                )
                .group_by(DataRecordRow.current_environment_id)
            ).all()
            return {str(environment_id): int(count) for environment_id, count in rows}

    def list_linked_records(self, project_id: str, environment_id: str) -> builtins.list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(DataRecordRow).where(
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.current_environment_id == environment_id,
                    DataRecordRow.deleted.is_(False),
                )
            ).all()
            return [
                {
                    "recordRef": {
                        "projectId": row.project_id,
                        "tableId": row.table_id,
                        "datasetGeneration": row.dataset_generation,
                        "recordKey": {"type": row.key_type, "value": row.key_value},
                    },
                    "linkRevision": row.link_revision,
                }
                for row in rows
            ]

    def create_manual_item(self, item: dict[str, Any]) -> dict[str, Any]:
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = ProjectManualItemRow(
                id=item["manualItemId"],
                project_id=item["projectId"],
                task_id=item["taskId"],
                run_id=item["runId"],
                instance_id=item.get("instanceId"),
                checkpoint_revision=item["checkpointRevision"],
                status=item["status"],
                status_revision=item["statusRevision"],
                expires_at=item.get("expiresAt"),
                allowed_targets=item.get("allowedTargets") or [],
                resume_started=bool(item.get("resumeStarted")),
                reason=item.get("reason"),
                created_at=item["createdAt"],
                updated_at=item["updatedAt"],
            )
            session.add(row)
            session.commit()
            return _manual(row)

    def get_manual_item(self, project_id: str, manual_item_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(ProjectManualItemRow, manual_item_id)
            if row is None or row.project_id != project_id:
                raise environment_error("NOT_FOUND", "Manual item was not found", 404)
            return _manual(row)

    def list_manual_items(self, project_id: str, **query) -> tuple[builtins.list[dict[str, Any]], int]:
        with self._session_factory() as session:
            self._project(session, project_id)
            statement = select(ProjectManualItemRow).where(
                ProjectManualItemRow.project_id == project_id
            )
            status = query.get("status")
            if status:
                statement = statement.where(ProjectManualItemRow.status == status)
            search = (query.get("q") or "").strip()
            if search:
                # Prototype 003-runs searches "任务或等待原因"; both are text facts of
                # the manual item itself, so the filter stays inside the same query.
                like = f"%{search}%"
                statement = statement.where(
                    or_(
                        ProjectManualItemRow.task_id.ilike(like),
                        ProjectManualItemRow.reason.ilike(like),
                    )
                )
            order = _manual_order(query.get("sort"))
            page = query.get("page") or 1
            page_size = query.get("page_size") or 50
            total = session.scalar(select(func.count()).select_from(statement.subquery()))
            rows = session.scalars(
                statement.order_by(*order)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return [_manual(row) for row in rows], int(total or 0)

    def transition_manual(
        self,
        project_id: str,
        manual_item_id: str,
        nxt: ManualStatus,
        *,
        expected_status_revision: int,
        expected_checkpoint_revision: int | None = None,
        resume_started: bool | None = None,
    ) -> dict[str, Any]:
        from autoflow.domain.environments.rules import validate_manual_transition

        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(ProjectManualItemRow, manual_item_id)
            if row is None or row.project_id != project_id:
                session.rollback()
                raise environment_error("NOT_FOUND", "Manual item was not found", 404)
            if row.status_revision != expected_status_revision:
                session.rollback()
                raise environment_error(
                    "MANUAL_TRANSITION_LOST",
                    "Manual transition lost the race",
                    409,
                    {
                        "domainCode": "manual_transition_lost",
                        "expectedRevision": expected_status_revision,
                        "currentRevision": row.status_revision,
                    },
                )
            if (
                expected_checkpoint_revision is not None
                and row.checkpoint_revision != expected_checkpoint_revision
            ):
                session.rollback()
                raise environment_error(
                    "MANUAL_TRANSITION_LOST",
                    "Manual checkpoint has changed",
                    409,
                    {"domainCode": "manual_transition_lost"},
                )
            started = row.resume_started if resume_started is None else resume_started
            status = validate_manual_transition(
                # The column is a plain string; the domain owns the allowed values.
                cast(ManualStatus, row.status),
                nxt,
                resume_started=started,
            )
            row.status = status
            row.resume_started = started
            row.status_revision = row.status_revision + 1
            row.updated_at = datetime.now(UTC)
            session.commit()
            return _manual(row)

    def _project(self, session: Session, project_id: str) -> ProjectRow:
        row = session.get(ProjectRow, project_id)
        if row is None or row.lifecycle_state == "deleted":
            raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
        return row

    def _environment(
        self,
        session: Session,
        project_id: str,
        environment_id: str,
        *,
        writable: bool = False,
    ) -> ProjectEnvironmentRow:
        self._project(session, project_id)
        row = session.get(ProjectEnvironmentRow, environment_id)
        if row is None or row.project_id != project_id or row.state == "deleted":
            raise environment_error(
                "ENVIRONMENT_NOT_FOUND",
                "Saved environment was not found",
                404,
                {"domainCode": "environment_not_found"},
            )
        if writable and row.state != "ready":
            raise environment_error(
                "ENVIRONMENT_UNAVAILABLE",
                "Saved environment is not ready",
                409,
                {"domainCode": "environment_unavailable"},
            )
        return row

    def _match(self, existing: ProjectOperationRow, operation: ProjectOperation) -> None:
        if existing.request_digest != operation.request_digest:
            raise ProjectError(
                "OPERATION_PAYLOAD_MISMATCH",
                "Idempotent command payload does not match",
                409,
                {"domainCode": "operation_payload_mismatch"},
            )


def _environment(row: ProjectEnvironmentRow) -> PersistentEnvironment:
    return PersistentEnvironment(
        EnvironmentRef(
            row.project_id, row.id, row.content_generation, row.metadata_revision
        ),
        row.name,
        row.notes,
        row.state,  # type: ignore[arg-type]
        row.profile_id,
        row.unavailable_reason,
        row.created_at,
        row.updated_at,
        row.created_from_source,
        row.created_from_task_id,
    )


def _instance(row: ProjectEnvironmentInstanceRow) -> EnvironmentInstance:
    return EnvironmentInstance(
        row.id,
        row.project_id,
        row.environment_id,
        row.state,  # type: ignore[arg-type]
        row.source,  # type: ignore[arg-type]
        row.source_content_generation,
        row.instance_use_generation,
        row.active_task_id,
        row.active_run_id,
        row.maintenance_operation_id,
        row.profile_id,
        row.created_at,
        row.updated_at,
    )


def _instance_row(record: EnvironmentInstance) -> ProjectEnvironmentInstanceRow:
    return ProjectEnvironmentInstanceRow(
        id=record.instance_id,
        project_id=record.project_id,
        environment_id=record.environment_id,
        state=record.state,
        source=record.source,
        source_content_generation=record.source_content_generation,
        instance_use_generation=record.instance_use_generation,
        active_task_id=record.active_task_id,
        active_run_id=record.active_run_id,
        maintenance_operation_id=record.maintenance_operation_id,
        profile_id=record.profile_id,
        identity_package={"source": record.source, "profileId": record.profile_id},
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _manual(row: ProjectManualItemRow) -> dict[str, Any]:
    return {
        "manualItemId": row.id,
        "projectId": row.project_id,
        "taskId": row.task_id,
        "runId": row.run_id,
        "instanceId": row.instance_id,
        "checkpointRevision": row.checkpoint_revision,
        "status": row.status,
        "statusRevision": row.status_revision,
        "expiresAt": row.expires_at,
        "allowedTargets": row.allowed_targets,
        "resumeStarted": row.resume_started,
        "reason": row.reason,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


def _occupancy(row: ProjectEnvironmentOccupancyRow) -> EnvironmentOccupancy:
    return EnvironmentOccupancy(
        row.environment_id, row.instance_id, row.holder_kind, row.holder_id  # type: ignore[arg-type]
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _complete(operation: ProjectOperation, result: dict[str, Any], now: datetime):
    from dataclasses import replace

    return replace(
        operation,
        status="succeeded",
        status_revision=2,
        result=result,
        updated_at=now,
        completed_at=now,
    )


def _operation(row: ProjectOperationRow) -> ProjectOperation:
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
        row.created_at,
        row.updated_at,
        row.completed_at,
    )


def _operation_row(value: ProjectOperation) -> ProjectOperationRow:
    return ProjectOperationRow(
        id=value.operation_id,
        project_id=value.project_id,
        idempotency_key=value.idempotency_key,
        kind=value.kind,
        request_digest=value.request_digest,
        status=value.status,
        status_revision=value.status_revision,
        resource=value.resource,
        result=value.result,
        error=value.error,
        created_at=value.created_at,
        updated_at=value.updated_at,
        completed_at=value.completed_at,
    )


IMPACT_TTL = timedelta(minutes=10)
# A live, unpublished or unreconciled work copy still owns this environment.
BUSY_ENVIRONMENT_STATES = (
    "reserved",
    "starting",
    "active",
    "waiting_manual",
    "closing",
    "saving",
    "cleaning",
    "cleanup_failed",
)
OPEN_OPERATION_STATUSES = ("accepted", "running", "reconciling")


def _delete_facts(
    session: Session, project_id: str, row: ProjectEnvironmentRow
) -> dict[str, Any]:
    """Real references to one environment; nothing here is estimated."""
    resource = {
        "type": "environment",
        "projectId": project_id,
        "environmentId": row.id,
    }
    linked = session.scalars(
        select(DataRecordRow).where(
            DataRecordRow.project_id == project_id,
            DataRecordRow.current_environment_id == row.id,
            DataRecordRow.deleted.is_(False),
        )
    ).all()
    fixed: list[ProjectAutomationRow] = []
    for automation in session.scalars(
        select(ProjectAutomationRow).where(ProjectAutomationRow.project_id == project_id)
    ):
        policy = automation.environment_policy or {}
        if (
            policy.get("source") == "fixedEnvironment"
            and policy.get("environmentId") == row.id
        ):
            fixed.append(automation)
    instances = list(
        session.execute(
            select(ProjectEnvironmentInstanceRow.id, ProjectEnvironmentInstanceRow.state).where(
                ProjectEnvironmentInstanceRow.environment_id == row.id
            )
        )
    )
    pending = list(
        session.execute(
            select(ProjectOperationRow.id, ProjectOperationRow.kind).where(
                ProjectOperationRow.project_id == project_id,
                ProjectOperationRow.status.in_(OPEN_OPERATION_STATUSES),
                ProjectOperationRow.resource["environmentId"].as_string() == row.id,
            )
        )
    )
    impacts = [
        _impact(resource, "ENVIRONMENT_RECORDS", f"记录关联 {len(linked)} 条"),
        _impact(resource, "AUTOMATION_FIXED_CHOICE", f"自动化固定选择 {len(fixed)} 个"),
        _impact(
            resource,
            "REFERENCED_RESOURCES_KEPT",
            "历史任务、Profile、记录内容与其它项目资源保留",
        ),
    ]
    blockers = [
        _blocker(
            "ENVIRONMENT_BUSY",
            resource,
            state,
            "环境现场仍在使用或待清理",
        )
        for _instance_id, state in instances
        if state not in {"closed", "cleaned"}
    ]
    blockers.extend(
        _blocker(
            "ENVIRONMENT_OPERATION_ACTIVE",
            resource,
            kind,
            "环境操作尚未结束",
            operation_id=operation_id,
        )
        for operation_id, kind in pending
    )
    return {"impacts": impacts, "blockers": blockers}


def _impact(resource: dict[str, Any], code: str, message: str) -> dict[str, Any]:
    return {"code": code, "resource": resource, "message": message, "blocking": False}


def _blocker(
    code: str,
    resource: dict[str, Any],
    state: str,
    message: str,
    *,
    operation_id: str | None = None,
) -> dict[str, Any]:
    blocker = {"code": code, "resource": resource, "state": state, "message": message}
    if operation_id is not None:
        blocker["operationId"] = operation_id
    return blocker


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
