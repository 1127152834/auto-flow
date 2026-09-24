from __future__ import annotations

import hashlib
import json
import logging
from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock, RLock
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from autoflow.application.environments.manual import (
    begin_resume,
    cancel_manual,
    expire_manual,
    finish_manual,
    open_manual,
    resume_manual,
)
from autoflow.application.environments.retention import (
    _jsonable,
    end_task,
    repair_association,
    save_environment,
)
from autoflow.domain.environments.models import (
    EnvironmentInstance,
    EnvironmentRef,
    PersistentEnvironment,
)
from autoflow.domain.environments.rules import (
    check_live_capacity,
    environment_error,
    occupy_environment,
    resolve_environment_source,
    validate_metadata,
    validate_open_instance,
)
from autoflow.domain.projects.models import ProjectError, ProjectOperation
from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore


class EnvironmentService:
    def __init__(
        self,
        projects,
        environments: SqlAlchemyEnvironments,
        store: EnvironmentStore,
        *,
        max_live_instances: int = 32,
        opener=None,
        closer=None,
        execution_generation_lookup=None,
        validate_browser_configuration=None,
    ):
        self._validate_browser_configuration = validate_browser_configuration
        self.manual_runtime: Any = None
        self.projects = projects
        self.environments = environments
        self.store = store
        self._max_live_instances = max_live_instances
        self._opener = opener
        self._closer = closer
        self._execution_generation_lookup = execution_generation_lookup
        self._opened: set[str] = set()
        # Opening and closing one work copy must not interleave. A start that is
        # still in flight owns the directory the save is about to copy, and a
        # close must never report success while that start is still writing.
        self._lifecycle_locks: dict[str, RLock] = {}
        self._lifecycle_guard = Lock()

    def _lifecycle_lock(self, instance_id: str) -> RLock:
        with self._lifecycle_guard:
            lock = self._lifecycle_locks.get(instance_id)
            if lock is None:
                lock = RLock()
                self._lifecycle_locks[instance_id] = lock
            return lock

    def execution_generation_of(self, instance) -> int | None:
        """Authoritative execution generation of the run that holds the instance.

        Returns ``None`` when no reader is wired or the run is unknown, so an
        isolated data test is not forced to fabricate a run row. Production
        always wires the reader and then the stored generation wins over the
        generation a request claims for itself.
        """

        run_id = getattr(instance, "active_run_id", None)
        if self._execution_generation_lookup is None or not run_id:
            return None
        run = self._execution_generation_lookup(run_id)
        if run is None:
            return None
        generation = getattr(run, "execution_generation", None)
        return generation if type(generation) is int else None

    def list(self, project_id: str, **query):
        self._project(project_id)
        return self.environments.list(project_id, **query)

    def list_with_counts(self, project_id: str, **query):
        items, total = self.list(project_id, **query)
        counts = self.environments.linked_record_counts(
            project_id, [item.ref.environment_id for item in items]
        )
        return items, total, counts

    def get(self, project_id: str, environment_id: str):
        environment, instance = self.environments.get_with_instance(project_id, environment_id)
        return environment, instance, self.environments.linked_record_count(project_id, environment_id)

    def impact(self, project_id: str, environment_id: str, action: str):
        self._project(project_id)
        return self.environments.delete_impact(project_id, environment_id, action)

    def delete(self, project_id: str, environment_id: str, key: str, payload: dict[str, Any]):
        self._writable(project_id)
        impact_revision = _positive_int(payload, "impactRevision")
        metadata_revision = _positive_int(payload, "expectedMetadataRevision")
        content_generation = _positive_int(payload, "expectedContentGeneration")
        if set(payload) != {
            "impactRevision",
            "expectedMetadataRevision",
            "expectedContentGeneration",
        }:
            raise environment_error(
                "VALIDATION_ERROR",
                "Unexpected field",
                422,
                {"fields": {"form": "Unexpected field"}},
            )
        operation = self._command(
            key,
            "deleteEnvironment",
            project_id,
            environment_id,
            {
                "scope": "environment",
                "projectId": project_id,
                "environmentId": environment_id,
                "request": {
                    "impactRevision": impact_revision,
                    "expectedMetadataRevision": metadata_revision,
                    "expectedContentGeneration": content_generation,
                },
            },
            datetime.now(UTC),
        )
        result, done = self.environments.delete_environment(
            project_id,
            environment_id,
            operation,
            impact_revision=impact_revision,
            expected_metadata_revision=metadata_revision,
            expected_content_generation=content_generation,
        )
        return result, done

    def patch(self, project_id: str, environment_id: str, key: str, payload: dict[str, Any]):
        self._writable(project_id)
        if "browserConfiguration" in payload:
            from .configuration import patch_browser_configuration
            with self._lifecycle_lock(environment_id):
                return patch_browser_configuration(self, project_id, environment_id, key, payload)
        expected = payload.get("expectedMetadataRevision")
        if type(expected) is not int or expected < 1:
            raise environment_error(
                "VALIDATION_ERROR",
                "Invalid environment metadata",
                422,
                {"fields": {"expectedMetadataRevision": "Must be a positive integer"}},
            )
        patch = validate_metadata(payload.get("name"), payload.get("notes"))
        if set(payload) - {"name", "notes", "expectedMetadataRevision"}:
            raise environment_error(
                "VALIDATION_ERROR",
                "Unexpected field",
                422,
                {"fields": {"form": "Unexpected field"}},
            )
        now = datetime.now(UTC)
        operation = self._command(
            key,
            "updateEnvironment",
            project_id,
            environment_id,
            {
                "scope": "environment",
                "projectId": project_id,
                "environmentId": environment_id,
                "request": {**patch, "expectedMetadataRevision": expected},
            },
            now,
        )
        return self.environments.update_metadata(
            project_id, environment_id, patch, expected, operation
        )

    def list_instances(self, project_id: str, **query):
        self._project(project_id)
        return self.environments.list_instances(project_id, **query)

    def get_instance(self, project_id: str, instance_id: str):
        self._project(project_id)
        return self.environments.get_instance(project_id, instance_id)

    def query_task_end(self, project_id: str, task_id: str):
        self._project(project_id)
        operation_id = self.environments.latest_end_operation(project_id, task_id)
        if operation_id is None:
            return None
        recorded = self.environments.end_by_operation(operation_id)
        if recorded is None:
            return None
        operation = self.projects.operation(operation_id=operation_id, project_id=project_id)
        save_id = recorded['saveOperationId']
        save = self.environments.save_by_operation(save_id) if save_id else None
        # A repair changes the association phase, never the original End verdict.
        return operation, save_id, save['phase'] if save else None, recorded['targets']

    def resolve(self, project_id: str, policy: dict[str, Any], inputs: dict[str, dict[str, Any]] | None = None):
        project = self._project(project_id)
        defaults = project.default_resources or {}
        return resolve_environment_source(
            policy,
            project_id=project_id,
            project_default_profile_id=defaults.get("profileId"),
            inputs=inputs,
            environments=self.environments.map_environments(project_id),
        )

    def prepare_studio_copy(self, frozen: dict[str, Any], target) -> None:
        """Copy a frozen saved generation into the owned Studio worker's scratch space."""
        from sqlalchemy import text

        from autoflow.infrastructure.database.environment_models import (
            ProjectEnvironmentOccupancyRow,
        )
        ref = frozen['environmentRef']
        # ponytail: hold the write fence during copy; a generation read lease can
        # shorten this transaction if large-profile preview copying becomes common.
        with self.environments._session_factory() as session:
            session.execute(text('BEGIN IMMEDIATE'))
            selected = self.environments.resolve_source_in_session(session, ref['projectId'], {'source': 'fixedEnvironment', 'environmentId': ref['environmentId']})
            if selected.environment_ref.to_dict() != ref or selected.identity_package != frozen['identityPackage']:
                raise environment_error('ENVIRONMENT_CHANGED', '环境已改变，请重新运行以冻结新版本', 409)
            if session.get(ProjectEnvironmentOccupancyRow, ref['environmentId']) is not None:
                raise environment_error('ENVIRONMENT_BUSY', '环境正在使用', 409)
            if self.store.generation_identity(ref['environmentId'], ref['contentGeneration']) != selected.identity_package:
                raise environment_error('ENVIRONMENT_IDENTITY_UNVERIFIED', '环境内容与身份资料不一致', 409)
            EnvironmentStore(target.parent.parent).prepare_instance(target.name, self.store.generation_dir(ref['environmentId'], ref['contentGeneration']))

    def reserve(
        self,
        project_id: str,
        resolved,
        *,
        task_id: str | None,
        run_id: str | None,
        holder_kind: str,
        holder_id: str,
    ) -> EnvironmentInstance:
        self._writable(project_id)
        now = datetime.now(UTC)
        check_live_capacity(
            self.environments.count_live_instances(), self._max_live_instances
        )
        instance = EnvironmentInstance(
            str(uuid4()),
            project_id,
            resolved.environment_ref.environment_id if resolved.environment_ref else None,
            "reserved",
            resolved.source,
            resolved.environment_ref.content_generation if resolved.environment_ref else None,
            1,
            task_id if holder_kind == "task" else None,
            run_id,
            holder_id if holder_kind == "maintenance" else None,
            resolved.profile_id,
            now,
            now,
            deepcopy(resolved.identity_package) if resolved.identity_package.get("schemaVersion") else None,
        )
        occupancy = None
        if resolved.environment_ref is not None:
            occupancy = occupy_environment(
                resolved.environment_ref.environment_id,
                instance.instance_id,
                holder_kind,
                holder_id,
                None,
            )
        saved = self.environments.reserve_instance(instance, occupancy)
        if resolved.environment_ref is None:
            self.store.prepare_instance(saved.instance_id)
        else:
            self.store.restore_generation(
                resolved.environment_ref.environment_id,
                resolved.environment_ref.content_generation,
                saved.instance_id,
                identity_package=saved.identity_package,
            )
        return self.environments.set_instance_state(saved.instance_id, "active")

    def publish_new(
        self,
        project_id: str,
        *,
        name: str,
        notes: str,
        profile_id: str,
        instance_id: str,
        task_id: str | None = None,
    ) -> PersistentEnvironment:
        metadata = validate_metadata(name, notes)
        now = datetime.now(UTC)
        environment_id = str(uuid4())
        identity = self.environments.get_instance(project_id, instance_id).identity_package
        digest = self.store.stage_candidate(environment_id, instance_id, identity_package=identity)
        self.store.publish(environment_id, 1, environment_id)
        record = PersistentEnvironment(
            EnvironmentRef(project_id, environment_id, 1, 1),
            metadata["name"],
            metadata.get("notes", ""),
            "ready",
            profile_id,
            None,
            now,
            now,
            identity_package=identity,
        )
        return self.environments.create_ready(
            record, digest, created_from_source="newFromProfile", created_from_task_id=task_id
        )

    def publish_update(self, project_id: str, environment_id: str, instance_id: str) -> PersistentEnvironment:
        current, _instance = self.environments.get_with_instance(project_id, environment_id)
        identity = self.environments.get_instance(project_id, instance_id).identity_package
        digest = self.store.stage_candidate(f"{environment_id}:{current.ref.content_generation + 1}", instance_id, identity_package=identity)
        self.store.publish(
            environment_id,
            current.ref.content_generation + 1,
            f"{environment_id}:{current.ref.content_generation + 1}",
        )
        return self.environments.publish_update(project_id, environment_id, digest, generation=current.ref.content_generation + 1, identity_package=identity)

    def close_instance(self, project_id: str, instance_id: str, environment_id: str | None) -> None:
        with self._lifecycle_lock(instance_id):
            instance = self.quiesce_instance(project_id, instance_id)
            if environment_id != instance.environment_id:
                raise environment_error("INSTANCE_OWNERSHIP_UNKNOWN", "环境实例归属不一致", 409)
            self.environments.set_instance_state(instance_id, "cleaning")
            try:
                self.store.close_instance(instance_id)
            except OSError:
                self.environments.set_instance_state(instance_id, "cleanup_failed")
                raise
            if environment_id:
                self.environments.release_occupancy(environment_id, instance_id)
            self.environments.set_instance_state(instance_id, "cleaned")

    def cleanup_terminal_tasks(self) -> None:
        for candidate in self.environments.disposable_task_instances():
            with self._lifecycle_lock(candidate.instance_id):
                # A save/End may have been accepted since the candidate scan.
                if not self.environments.disposable_task_instances(candidate.instance_id):
                    continue
                try:
                    self.close_instance(candidate.project_id, candidate.instance_id, candidate.environment_id)
                except (OSError, ProjectError):
                    self.environments.set_instance_state(candidate.instance_id, "cleanup_failed")
                    logging.getLogger(__name__).exception(
                        "Task environment cleanup deferred: %s", candidate.instance_id,
                    )

    def quiesce_instance(self, project_id: str, instance_id: str) -> EnvironmentInstance:
        with self._lifecycle_lock(instance_id):
            instance = self.environments.get_instance(project_id, instance_id)
            if instance.state in {"closed", "cleaned", "retained_unsaved"}:
                return instance
            if self._closer is None:
                raise environment_error("INSTANCE_OWNERSHIP_UNKNOWN", "无法确认浏览器已关闭，请核验运行现场", 409)
            self._closer(self, instance)
            self._opened.discard(instance_id)
            return self.environments.set_instance_state(instance_id, "closed")

    def instance_path(self, instance_id: str):
        return self.store.instance_dir(instance_id)

    def run_work_directory(self, run_request_id: str):
        instance = self.environments.active_instance_for_run_request(run_request_id)
        if instance is None:
            return None
        directory = self.store.root / "instances" / instance.instance_id
        if not directory.is_dir():
            raise environment_error("ENVIRONMENT_UNAVAILABLE", "任务环境工作副本不存在", 409)
        return directory

    def open_instance(self, project_id: str, instance_id: str, key: str, payload: dict[str, Any]):
        self._writable(project_id)
        now = datetime.now(UTC)
        instance = self.environments.get_instance(project_id, instance_id)
        validate_open_instance(
            instance_state=instance.state,
            instance_use_generation=instance.instance_use_generation,
            expected_use_generation=payload["expectedUseGeneration"],
        )
        operation = self._command(
            key,
            "openInstance",
            project_id,
            instance.environment_id,
            {
                "scope": "openInstance",
                "projectId": project_id,
                "instanceId": instance_id,
                "request": payload,
            },
            now,
        )
        if self._opener is None and instance.instance_id not in self._opened:
            raise environment_error("ENVIRONMENT_UNAVAILABLE", "浏览器现场打开能力尚未就绪", 503)
        accepted, replayed = self.environments.accept_operation(operation)
        if replayed:
            return accepted.result, accepted, True
        try:
            with self._lifecycle_lock(instance_id):
                # A start that is still in flight must finish before an End may copy
                # or claim the work copy; otherwise End refuses with
                # INSTANCE_NOT_QUIESCENT or saves a profile mid-write, and a stale
                # ``_opened`` entry would later fake a window nobody owns.
                current = self.environments.get_instance(project_id, instance_id)
                launched = instance_id in self._opened
                if not launched:
                    if self._opener is None:
                        raise environment_error(
                            "ENVIRONMENT_UNAVAILABLE", "浏览器现场打开能力尚未就绪", 503
                        )
                    self._opener(self, current)
                    launched = True
                live = self.environments.get_instance(project_id, instance_id)
                if live.state in {"closed", "cleaned"}:
                    self._opened.discard(instance_id)
                    raise environment_error(
                        "INSTANCE_NOT_ACTIVE",
                        "环境实例已关闭，请重新打开",
                        409,
                        {"domainCode": "instance_not_active", "retryable": False},
                    )
                if live.state in {"reserved", "starting"}:
                    live = self.environments.set_instance_state(instance_id, "active")
                self._opened.add(instance_id)
                outcome = {
                    "phase": "open",
                    "complete": False,
                    "instance": live.to_dict(),
                    "source": None,
                    "saved": None,
                    "targets": [],
                    "conflicts": [],
                    "launched": launched,
                }
        except (ProjectError, WorkflowRuntimeError) as error:
            # An accepted operation that never completes leaves the user with a
            # request that can only ever answer "still running".
            self._opened.discard(instance_id)
            self._fail_operation(
                accepted,
                {
                    "code": error.code,
                    "message": error.message,
                    "status": error.status,
                    "details": error.details,
                },
            )
            raise
        except Exception as error:
            # Chromium, the filesystem and the thread pool fail in ways the domain
            # does not name. The ledger still has to answer for this request, and
            # the window must never be recorded as open.
            self._opened.discard(instance_id)
            self._fail_operation(
                accepted,
                {
                    "code": "INSTANCE_OPEN_FAILED",
                    "message": "浏览器现场打开失败，请稍后按原操作查询结果",
                    "details": {
                        "domainCode": "instance_open_failed",
                        "retryable": True,
                        "cause": type(error).__name__,
                    },
                },
            )
            raise
        outcome = _jsonable(outcome)
        done = self.environments.complete_operation(accepted, outcome, None, datetime.now(UTC))
        return outcome, done, False

    def _fail_operation(self, accepted, failure: dict[str, Any]) -> None:
        self.environments.complete_operation(accepted, None, failure, datetime.now(UTC))

    def attach_task_instance(
        self,
        project_id: str,
        task_id: str,
        run_id: str,
        policy: dict[str, Any],
        inputs: dict[str, dict[str, Any]] | None = None,
    ) -> EnvironmentInstance:
        existing = self.environments.find_instance_by_task(project_id, task_id)
        if existing is not None:
            if existing.state == "reserved":
                if existing.environment_id is None:
                    self.store.prepare_instance(existing.instance_id)
                else:
                    if existing.source_content_generation is None:
                        raise environment_error("ENVIRONMENT_UNAVAILABLE", "环境内容代次缺失", 409)
                    self.store.restore_generation(
                        existing.environment_id, existing.source_content_generation,
                        existing.instance_id,
                        identity_package=existing.identity_package,
                    )
                return self.environments.set_instance_state(existing.instance_id, "active")
            return existing
        resolved = self.resolve(project_id, policy, inputs)
        return self.reserve(
            project_id,
            resolved,
            task_id=task_id,
            run_id=run_id,
            holder_kind="task",
            holder_id=task_id,
        )

    def reserve_task_instance(
        self, session: Session, project_id: str, task_id: str, run_id: str,
        policy: dict[str, Any],
        inputs: dict[str, dict[str, Any]] | None = None,
        *, resource_request: dict[str, Any] | None = None, instance_id: str | None = None,
    ) -> EnvironmentInstance:
        resolved = self.environments.resolve_source_in_session(session, project_id, policy, inputs)
        from autoflow.domain.environments.identity import identity_from_request

        identity = resolved.identity_package if resolved.identity_package.get("schemaVersion") else None
        if resource_request is not None:
            identity = identity_from_request(resource_request)
            if resolved.environment_ref and resource_request.get("environmentRef") != resolved.environment_ref.to_dict():
                raise environment_error("SAVE_GENERATION_CONFLICT", "环境已变化，请重新准备任务", 409)
        now = datetime.now(UTC)
        reference = resolved.environment_ref
        instance = EnvironmentInstance(
            instance_id or str(uuid4()), project_id, reference.environment_id if reference else None,
            "reserved", resolved.source, reference.content_generation if reference else None,
            1, task_id, run_id, None, resolved.profile_id, now, now, deepcopy(identity),
        )
        occupancy = (
            occupy_environment(reference.environment_id, instance.instance_id, "task", task_id, None)
            if reference else None
        )
        return self.environments.reserve_instance_in_session(
            session, instance, occupancy, max_live_instances=self._max_live_instances,
        )

    def save(self, project_id: str, key: str, payload: dict[str, Any]):
        with self._lifecycle_lock(payload["instanceId"]):
            return save_environment(self, project_id, key, payload)

    def repair(self, project_id: str, key: str, save_operation_id: str, payload: dict[str, Any]):
        return repair_association(self, project_id, key, save_operation_id, payload)

    def end(self, project_id: str, key: str, payload: dict[str, Any]):
        with self._lifecycle_lock(payload["instanceId"]):
            return end_task(self, project_id, key, payload)

    def open_manual(self, project_id: str, payload: dict[str, Any]):
        if payload.get("instanceId"):
            with self._lifecycle_lock(payload["instanceId"]):
                instance = self.environments.get_instance(project_id, payload["instanceId"])
                if instance.state in {"cleaning", "cleaned"}:
                    raise environment_error("ENVIRONMENT_UNAVAILABLE", "任务环境已清理，无法转入人工处理", 409)
                return open_manual(self, project_id, payload)
        return open_manual(self, project_id, payload)

    def list_manual(self, project_id: str, **query):
        self._project(project_id)
        items, total = self.environments.list_manual_items(project_id, **query)
        # ponytail: at most 200 checkpoints per page; batch this lookup if it becomes measurable.
        if self.manual_runtime is not None:
            items = [self.manual_runtime.describe(item) for item in items]
        return items, total

    def get_manual(self, project_id: str, manual_item_id: str):
        item = self.environments.get_manual_item(project_id, manual_item_id)
        return self.manual_runtime.describe(item) if self.manual_runtime is not None else item

    def resume_manual(self, project_id: str, key: str, manual_item_id: str, payload: dict[str, Any]):
        item = self.get_manual(project_id, manual_item_id)
        if self.manual_runtime is not None and self.manual_runtime.owns(item):
            return self.manual_runtime.command(project_id, key, item, payload, 'resume')
        return resume_manual(self, project_id, key, manual_item_id, payload)

    def begin_resume(self, project_id: str, manual_item_id: str, expected_status_revision: int):
        return begin_resume(self, project_id, manual_item_id, expected_status_revision)

    def finish_manual(self, project_id: str, key: str, manual_item_id: str, payload: dict[str, Any]):
        item = self.get_manual(project_id, manual_item_id)
        if self.manual_runtime is not None and self.manual_runtime.owns(item):
            return self.manual_runtime.command(project_id, key, item, payload, 'finish')
        return finish_manual(self, project_id, key, manual_item_id, payload)

    def expire_manual(self, project_id: str, manual_item_id: str, expected_status_revision: int):
        return expire_manual(self, project_id, manual_item_id, expected_status_revision)

    def cancel_manual(self, project_id: str, manual_item_id: str, expected_status_revision: int):
        return cancel_manual(self, project_id, manual_item_id, expected_status_revision)

    def start_maintenance(self, project_id: str, environment_id: str, key: str, expected_content_generation: int):
        self._writable(project_id)
        now = datetime.now(UTC)
        environment, active = self.environments.get_with_instance(project_id, environment_id)
        if environment.ref.content_generation != expected_content_generation:
            raise environment_error(
                "SAVE_GENERATION_CONFLICT",
                "Saved environment content has changed",
                409,
                {
                    "domainCode": "save_generation_conflict",
                    "expectedRevision": expected_content_generation,
                    "currentRevision": environment.ref.content_generation,
                },
            )
        operation = self._command(
            key,
            "startMaintenance",
            project_id,
            environment_id,
            {
                "scope": "maintenance",
                "projectId": project_id,
                "environmentId": environment_id,
                "expectedContentGeneration": expected_content_generation,
            },
            now,
        )
        accepted, replayed = self.environments.accept_operation(operation)
        if replayed:
            return accepted.result, accepted, True
        try:
            if active is not None:
                raise environment_error(
                    "ENVIRONMENT_BUSY",
                    "Saved environment is already in use",
                    423,
                    {"domainCode": "environment_busy", "instanceId": active.instance_id},
                )
            from autoflow.domain.environments.models import ResolvedEnvironmentSource

            resolved = ResolvedEnvironmentSource(
                "fixedEnvironment",
                environment.ref,
                environment.profile_id,
                environment.identity_package or {},
            )
            instance = self.reserve(
                project_id,
                resolved,
                task_id=None,
                run_id=None,
                holder_kind="maintenance",
                holder_id=accepted.operation_id,
            )
        except (ProjectError, WorkflowRuntimeError) as error:
            self.environments.complete_operation(
                accepted,
                None,
                {"code": error.code, "message": error.message, "details": error.details},
                datetime.now(UTC),
            )
            raise
        outcome = {
            "phase": "open",
            "complete": False,
            "instance": instance.to_dict(),
            "source": environment.ref.to_dict(),
            "saved": None,
            "targets": [],
            "conflicts": [],
        }
        outcome = _jsonable(outcome)
        done = self.environments.complete_operation(accepted, outcome, None, datetime.now(UTC))
        return outcome, done, False

    def discard_maintenance(self, project_id: str, key: str, instance_id: str, maintenance_operation_id: str):
        self._writable(project_id)
        now = datetime.now(UTC)
        instance = self.environments.get_instance(project_id, instance_id)
        if instance.maintenance_operation_id != maintenance_operation_id:
            raise environment_error(
                "INSTANCE_OWNERSHIP_UNKNOWN",
                "Instance use generation does not match",
                409,
                {"domainCode": "instance_ownership_unknown"},
            )
        operation = self._command(
            key,
            "discardEnvironment",
            project_id,
            instance.environment_id,
            {
                "scope": "discard",
                "projectId": project_id,
                "instanceId": instance_id,
                "maintenanceOperationId": maintenance_operation_id,
            },
            now,
        )
        accepted, replayed = self.environments.accept_operation(operation)
        if replayed:
            return accepted.result, accepted, True
        self.close_instance(project_id, instance_id, instance.environment_id)
        closed = self.environments.get_instance(project_id, instance_id)
        outcome = {
            "phase": "cleanup",
            "complete": True,
            "instance": closed.to_dict(),
            "source": None,
            "saved": None,
            "targets": [],
            "conflicts": [],
        }
        outcome = _jsonable(outcome)
        done = self.environments.complete_operation(accepted, outcome, None, datetime.now(UTC))
        return outcome, done, False

    def _command(self, key, kind, project_id, environment_id, canonical, now):
        return _operation(key, kind, project_id, environment_id, canonical, now)

    def _project(self, project_id: str):
        value = self.projects.get(project_id)
        if value is None or value.lifecycle_state == "deleted":
            raise ProjectError("PROJECT_NOT_FOUND", "Project was not found", 404)
        return value

    def _writable(self, project_id: str):
        project = self._project(project_id)
        if project.lifecycle_state == "closing":
            raise ProjectError("PROJECT_CLOSING", "Project is closing", 423)
        if project.lifecycle_state != "active":
            raise ProjectError("LIFECYCLE_CONFLICT", "Project cannot be edited", 409)
        return project


def _positive_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if type(value) is not int or value < 1:
        raise environment_error(
            "VALIDATION_ERROR",
            "Invalid environment delete",
            422,
            {"fields": {field: "Must be a positive integer"}},
        )
    return value


def _operation(key, kind, project_id, environment_id, canonical, now):
    digest = hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()
    resource = {"type": "environment", "projectId": project_id, "environmentId": environment_id}
    if canonical.get("scope") == "environmentConfiguration":
        resource["browserConfigurationChange"] = True
    if kind == "saveEnvironment":
        request = canonical.get("request") or {}
        resource["instanceId"] = canonical.get("instanceId") or request.get("instanceId")
        resource["retainEnvironment"] = (
            canonical.get("scope") == "environmentSave"
            or bool((request.get("retainEnvironment") or {}).get("enabled"))
        )
    return ProjectOperation(
        str(uuid4()),
        project_id,
        key.strip(),
        kind,
        digest,
        "running",
        1,
        resource,
        None,
        None,
        now,
        now,
        None,
    )
