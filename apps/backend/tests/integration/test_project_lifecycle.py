"""PM8-A: the project lifecycle state machine against real migrations.

Every case runs on a migrated SQLite database and drives the real application
services; nothing here re-implements the rules it verifies.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.lifecycle import (
    ProjectLifecycleCoordinator,
    ProjectLifecycleService,
)
from autoflow.application.projects.service import ProjectService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
    ProjectManualItemRow,
)
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_models import (
    DataImpactRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_lifecycle import (
    SqlAlchemyProjectLifecycle,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def key() -> str:
    return str(uuid4())


class Context:
    def __init__(self, tmp_path, *, name="生命周期项目", environment_root=None):
        self.database = tmp_path / "lifecycle.sqlite3"
        migrate_database(self.database)
        self.factory = create_session_factory(self.database)
        self.projects = ProjectService(SqlAlchemyProjects(self.factory))
        self.record, _, _ = self.projects.create(
            key(), {"name": name, "description": ""}
        )
        self.project_id = self.record.project_id
        self.environment_root = environment_root
        self.repository = SqlAlchemyProjectLifecycle(
            self.factory, environment_root=environment_root
        )
        self.coordinator = ProjectLifecycleCoordinator(self.repository, QuiesceGate())
        self.service = ProjectLifecycleService(
            SqlAlchemyProjects(self.factory), self.repository, self.coordinator
        )

    def state(self) -> str:
        with self.factory() as session:
            return session.get(ProjectRow, self.project_id).lifecycle_state

    def archive(self, replay: str | None = None, **overrides):
        """A retry re-sends the very same body; only the key decides identity."""
        if replay is not None:
            return self.service.archive(self.project_id, replay, self.archive_body)
        operation_key = overrides.pop("key", key())
        impact = self.service.impact(self.project_id, "archive")
        self.archive_body = {
            "impactRevision": impact["impactRevision"],
            "expectedManagementRevision": self.record.management_revision,
            **overrides,
        }
        return self.service.archive(self.project_id, operation_key, self.archive_body)

    def delete(self, replay: str | None = None, impact_revision=None, **overrides):
        if replay is not None:
            return self.service.delete(self.project_id, replay, self.delete_body)
        revision = (
            impact_revision
            if impact_revision is not None
            else self.service.impact(self.project_id, "delete")["impactRevision"]
        )
        payload = {
            "confirmationName": self.record.name,
            "impactRevision": revision,
            "expectedManagementRevision": self.record.management_revision,
            **overrides,
        }
        operation_key = payload.pop("key", key())
        self.delete_body = payload
        return self.service.delete(self.project_id, operation_key, payload)

    def archive_to_settled(self):
        operation = self.archive()
        self.repository.advance(self.project_id)
        return operation

    def operation(self, operation_id: str):
        return self.projects.projects.get_operation(
            operation_id=operation_id, project_id=self.project_id
        )


def _busy_environment(factory, project_id, *, state="active") -> str:
    instance_id = str(uuid4())
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            ProjectEnvironmentInstanceRow(
                id=instance_id,
                project_id=project_id,
                environment_id=None,
                state=state,
                source="newFromProfile",
                source_content_generation=None,
                instance_use_generation=1,
                active_task_id=None,
                active_run_id=None,
                maintenance_operation_id=None,
                profile_id=str(uuid4()),
                identity_package={},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    return instance_id


def _waiting_manual(factory, project_id) -> str:
    task_id = str(uuid4())
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            ProjectManualItemRow(
                id=str(uuid4()),
                project_id=project_id,
                task_id=task_id,
                run_id=str(uuid4()),
                instance_id=None,
                checkpoint_revision=1,
                status="waiting",
                status_revision=1,
                expires_at=None,
                allowed_targets=[],
                resume_started=False,
                reason=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    return task_id


def test_archive_impact_lists_real_blockers_and_changes_nothing(tmp_path):
    context = Context(tmp_path)
    instance_id = _busy_environment(context.factory, context.project_id)
    _waiting_manual(context.factory, context.project_id)

    report = context.service.impact(context.project_id, "archive")

    assert {blocker["code"] for blocker in report["blockers"]} == {
        "ENVIRONMENT_ACTIVE",
        "MANUAL_PENDING",
    }
    environment = next(
        blocker
        for blocker in report["blockers"]
        if blocker["code"] == "ENVIRONMENT_ACTIVE"
    )
    assert environment["resource"] == {
        "type": "environment",
        "projectId": context.project_id,
        "environmentId": instance_id,
    }
    assert report["unsyncedCount"] == 0 and report["impactRevision"] >= 1
    assert [impact["code"] for impact in report["impacts"]] == [
        "PROJECT_TABLES",
        "PROJECT_AUTOMATIONS",
    ]
    assert context.state() == "active"
    with context.factory() as session:
        assert session.scalar(select(func.count()).select_from(DataImpactRow)) == 1
        assert list(
            session.scalars(select(ProjectOperationRow.kind))
        ) == ["createProject"]


def test_archive_settles_only_after_the_blockers_clear(tmp_path):
    context = Context(tmp_path)
    instance_id = _busy_environment(context.factory, context.project_id)
    operation = context.archive()

    assert operation.status == "running" and context.state() == "closing"
    context.repository.advance(context.project_id)
    assert context.state() == "closing"
    assert context.operation(operation.operation_id).status == "running"

    with context.factory() as session:
        row = session.get(ProjectEnvironmentInstanceRow, instance_id)
        row.state = "cleaned"
        session.commit()
    context.repository.advance(context.project_id)

    assert context.state() == "archived"
    saved = context.operation(operation.operation_id)
    assert saved.status == "succeeded"
    assert saved.result["lifecycleState"] == "archived"
    assert saved.completed_at is not None


def test_closing_rejects_new_work_and_still_accepts_stop(tmp_path):
    from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
    from autoflow.domain.project_runs.models import ProjectRunError
    from tests.integration.test_project_run_start import setup, start_payload

    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    run_tables = DataTableService(SqlAlchemyProjectData(factory))
    run_records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
    table, _, _ = run_tables.create(
        project.project_id, key(), {"name": "资料", "sourceKind": "local"}
    )
    batch, _, _ = coordinator.start(
        project.project_id,
        automation.automation_id,
        key(),
        start_payload(automation),
    )
    repository = SqlAlchemyProjectLifecycle(factory)
    service = ProjectLifecycleService(
        SqlAlchemyProjects(factory),
        repository,
        ProjectLifecycleCoordinator(repository, QuiesceGate()),
    )
    report = service.impact(project.project_id, "archive")
    assert {
        blocker["code"] for blocker in report["blockers"]
    } == {"BATCH_ACTIVE", "TASK_ACTIVE"} or {
        blocker["code"] for blocker in report["blockers"]
    } == {"BATCH_ACTIVE"}
    service.archive(
        project.project_id,
        key(),
        {
            "impactRevision": report["impactRevision"],
            "expectedManagementRevision": project.management_revision,
        },
    )
    with factory() as session:
        assert (
            session.get(ProjectRow, project.project_id).lifecycle_state == "closing"
        )

    for rejected in (
        lambda: coordinator.start(
            project.project_id,
            automation.automation_id,
            key(),
            start_payload(automation),
        ),
        lambda: run_tables.create(
            project.project_id, key(), {"name": "新的", "sourceKind": "local"}
        ),
        lambda: run_records.create(
            project.project_id,
            table["tableId"],
            key(),
            {"datasetGeneration": table["datasetGeneration"], "values": []},
        ),
    ):
        with pytest.raises((ProjectRunError, ProjectError)) as error:
            rejected()
        assert error.value.status == 423
        assert error.value.code == "PROJECT_CLOSING"

    # Stopping is收尾, not new work: it must survive the closing gate.
    scheduler = ProjectBatchScheduler(factory, None, QuiesceGate())
    stop = scheduler._accept_stop(
        project.project_id,
        batch.batch_id,
        key(),
        {"expectedStatusRevision": batch.status_revision, "reason": "归档收尾"},
    )
    assert stop.kind == "stopBatch" and stop.status == "running"


def test_archived_is_read_only_and_can_be_restored_without_replay(tmp_path):
    context = Context(tmp_path)
    DataTableService(SqlAlchemyProjectData(context.factory)).create(
        context.project_id, key(), {"name": "资料", "sourceKind": "local"}
    )
    context.archive_to_settled()
    assert context.state() == "archived"

    with pytest.raises(ProjectError) as rejected:
        DataTableService(SqlAlchemyProjectData(context.factory)).create(
            context.project_id, key(), {"name": "新的", "sourceKind": "local"}
        )
    assert rejected.value.status == 409 and rejected.value.code == "LIFECYCLE_CONFLICT"

    with pytest.raises(ProjectError) as conflict:
        context.service.impact(context.project_id, "archive")
    assert conflict.value.status == 409

    before = _history(context)
    restore = context.service.restore(
        context.project_id,
        key(),
        {"expectedManagementRevision": context.record.management_revision},
    )
    assert restore.status == "succeeded"
    assert restore.result["lifecycleState"] == "active"
    assert context.state() == "active"
    assert _history(context) == before
    # Reading an archived project and its tables is still allowed.
    assert context.projects.get(context.project_id).name
    assert DataTableService(SqlAlchemyProjectData(context.factory)).list(
        context.project_id, page=1, page_size=50, sort="-updatedAt"
    )


def _history(context):
    with context.factory() as session:
        return {
            "batches": session.scalar(
                select(func.count()).select_from(ProjectBatchRow)
            )
            + session.scalar(select(func.count()).select_from(ProjectTaskRow)),
            "tables": session.scalar(
                select(func.count())
                .select_from(DataTableRow)
                .where(DataTableRow.project_id == context.project_id)
            ),
        }


def test_delete_needs_archive_name_and_a_fresh_impact(tmp_path):
    context = Context(tmp_path)
    with pytest.raises(ProjectError) as early:
        context.service.impact(context.project_id, "delete")
    assert early.value.status == 409

    context.archive_to_settled()
    impact = context.service.impact(context.project_id, "delete")

    with pytest.raises(ProjectError) as wrong_name:
        context.service.delete(
            context.project_id,
            key(),
            {
                "confirmationName": "别的名字",
                "impactRevision": impact["impactRevision"],
                "expectedManagementRevision": context.record.management_revision,
            },
        )
    assert wrong_name.value.status == 422
    assert context.state() == "archived"

    with context.factory() as session:
        row = session.get(DataImpactRow, impact["impactRevision"])
        row.expires_at = datetime(2020, 1, 1, tzinfo=UTC)
        session.commit()
    with pytest.raises(ProjectError) as stale:
        context.delete(impact_revision=impact["impactRevision"])
    assert stale.value.status == 412
    assert context.state() == "archived"

    with pytest.raises(ProjectError) as wrong_revision:
        context.delete(expectedManagementRevision=99)
    assert wrong_revision.value.status == 409
    assert context.state() == "archived"

    operation = context.delete()
    assert operation.kind == "deleteProject" and operation.status == "running"
    assert context.state() == "deleting"
    context.repository.advance(context.project_id)
    assert context.state() == "deleted"


def test_delete_purges_only_this_project_and_keeps_external_files(tmp_path):
    environment_root = tmp_path / "environments"
    context = Context(tmp_path, environment_root=environment_root)
    other = Context(tmp_path, name="保留项目")
    tables = DataTableService(SqlAlchemyProjectData(context.factory))
    mine, _, _ = tables.create(
        context.project_id, key(), {"name": "资料", "sourceKind": "local"}
    )
    other_table, _, _ = DataTableService(
        SqlAlchemyProjectData(other.factory)
    ).create(other.project_id, key(), {"name": "别人的", "sourceKind": "local"})
    instance_id = _busy_environment(context.factory, context.project_id, state="closed")
    work_dir = environment_root / "instances" / instance_id
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "cookies.json").write_text("{}", encoding="utf-8")
    external = tmp_path / "来源.xlsx"
    external.write_bytes(b"external-source")

    context.archive_to_settled()
    context.delete()
    context.repository.advance(context.project_id)

    assert context.state() == "deleted"
    assert not work_dir.exists()
    assert external.read_bytes() == b"external-source"
    with context.factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DataTableRow)
                .where(DataTableRow.project_id == context.project_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(DataImpactRow)
                .where(DataImpactRow.project_id == context.project_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProjectOperationRow)
                .where(
                    ProjectOperationRow.project_id == context.project_id,
                    ProjectOperationRow.kind == "createPlan",
                )
            )
            == 0
        )
    assert other.state() == "active"
    assert other.projects.get(other.project_id).name == "保留项目"
    with other.factory() as session:
        assert session.get(DataTableRow, other_table["tableId"]) is not None
    assert mine["tableId"]
    # The tombstone frees the name for a fresh project.
    recreated, _, _ = context.projects.create(key(), {"name": context.record.name})
    assert recreated.name == context.record.name


def test_delete_cleanup_failure_keeps_the_project_deleting_with_residue(tmp_path, monkeypatch):
    environment_root = tmp_path / "environments"
    context = Context(tmp_path, environment_root=environment_root)
    instance_id = _busy_environment(context.factory, context.project_id, state="closed")
    work_dir = environment_root / "instances" / instance_id
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "payload").write_text("x", encoding="utf-8")
    context.archive_to_settled()
    operation = context.delete()
    container = environment_root / "instances"
    original_rmtree = shutil.rmtree
    monkeypatch.setattr(shutil, "rmtree", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("injected deletion denial")))
    try:
        context.repository.advance(context.project_id)
    finally:
        monkeypatch.setattr(shutil, "rmtree", original_rmtree)

    assert context.state() == "deleting"
    saved = context.operation(operation.operation_id)
    assert saved.status == "failed"
    assert saved.error["code"] == "DELETE_CLEANUP_FAILED"
    assert str(work_dir) in saved.error["details"]["cleanup"]["residue"]

    # `deleting` is the state the retry converges to, never a reason to refuse it.
    retry_impact = context.service.impact(context.project_id, "delete")
    assert [item["code"] for item in retry_impact["blockers"]] == []
    assert retry_impact["impacts"], "the retry still reports what will be removed"

    retry = context.delete()
    with pytest.raises(ProjectError) as blocked:
        context.delete()
    assert blocked.value.status == 409 and context.state() == "deleting"

    context.repository.advance(context.project_id)
    assert context.state() == "deleted"
    assert retry.status == "running"
    assert not work_dir.exists()
    shutil.rmtree(container, ignore_errors=True)


def test_archive_directory_lists_a_project_stuck_in_deleting(tmp_path, monkeypatch):
    environment_root = tmp_path / "environments"
    context = Context(tmp_path, environment_root=environment_root)
    instance_id = _busy_environment(context.factory, context.project_id, state="closed")
    work_dir = environment_root / "instances" / instance_id
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "payload").write_text("x", encoding="utf-8")

    def listed(lifecycle_state):
        items, total = context.projects.projects.list(
            lifecycle_state=lifecycle_state, page=1, page_size=50
        )
        return [item.project_id for item in items], total

    context.archive_to_settled()
    assert listed("archived") == ([context.project_id], 1)
    assert listed("active") == ([], 0)

    context.delete()
    container = environment_root / "instances"
    try:
        original_rmtree = shutil.rmtree
        monkeypatch.setattr(shutil, "rmtree", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("injected deletion denial")))
        try:
            context.repository.advance(context.project_id)
        finally:
            monkeypatch.setattr(shutil, "rmtree", original_rmtree)

        # The stuck project stays inside the archive directory, not only "all".
        assert listed("archived") == ([context.project_id], 1)
        assert listed(None) == ([context.project_id], 1)
        assert listed("active") == ([], 0)

        context.delete()
        context.repository.advance(context.project_id)
        assert listed("archived") == ([], 0)
    finally:
        monkeypatch.setattr(shutil, "rmtree", original_rmtree)
        shutil.rmtree(container, ignore_errors=True)


def test_lifecycle_commands_replay_on_the_same_key(tmp_path):
    context = Context(tmp_path)
    first = context.archive()
    second = context.archive(replay=first.idempotency_key)
    assert second.operation_id == first.operation_id
    assert context.state() == "closing"
    with context.factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProjectOperationRow)
                .where(ProjectOperationRow.kind == "archiveProject")
            )
            == 1
        )

    context.repository.advance(context.project_id)
    assert context.state() == "archived"
    replayed = context.archive(replay=first.idempotency_key)
    assert replayed.status == "succeeded" and replayed.operation_id == first.operation_id

    restored = context.service.restore(
        context.project_id,
        key(),
        {"expectedManagementRevision": context.record.management_revision},
    )
    again = context.service.restore(
        context.project_id,
        restored.idempotency_key,
        {"expectedManagementRevision": context.record.management_revision},
    )
    assert again.operation_id == restored.operation_id

    context.archive_to_settled()
    deleted = context.delete()
    replay = context.delete(replay=deleted.idempotency_key)
    assert replay.operation_id == deleted.operation_id
    context.repository.advance(context.project_id)
    assert context.state() == "deleted"

    # The delete result survives the project: workspace scope still finds it.
    recovered = context.projects.workspace_operation(deleted.idempotency_key)
    assert recovered.result == {
        "target": {"type": "project", "projectId": context.project_id},
        "deleted": True,
    }
    with pytest.raises(ProjectError) as gone:
        context.projects.operation(
            operation_id=deleted.operation_id, project_id=context.project_id
        )
    assert gone.value.status == 404
