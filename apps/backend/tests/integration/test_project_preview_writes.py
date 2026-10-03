"""Remediation M2 R2-30: preview runs see their own writes; real data, versions and sync stay untouched."""

from dataclasses import replace

import pytest
from sqlalchemy import func, select

from autoflow.domain.project_data.capabilities import (
    CreateProjectRecordCommand,
    QueryProjectRecordsRequest,
    ReadProjectRecordRequest,
    RecordReadGrant,
    TableCapabilityGrant,
    TaskCapabilityScope,
    UpdateProjectRecordCommand,
)
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_sync_models import SyncOperationRow
from tests.integration.test_project_capability_fencing import (  # noqa: F401
    _record_ref,
    _service,
    capability_context,
)
from tests.integration.test_project_run_data_start import uid


@pytest.fixture
def preview(capability_context):  # noqa: F811
    factory, project_id, task, table, field, record = capability_context
    ref = _record_ref(project_id, record)
    field_id = field["ref"]["fieldId"]
    scope = TaskCapabilityScope(
        project_id, task.task_id, task.run_id, 1, frozenset(), frozenset({(table["tableId"], table["datasetGeneration"])}),
        frozenset({RecordReadGrant(ref, frozenset({field_id}), frozenset({"workflow"}))}), frozenset(),
        frozenset({TableCapabilityGrant(table["tableId"], table["datasetGeneration"],
                                        frozenset({"updateRecord", "queryRecords", "createRecord"}),
                                        frozenset({field_id}), frozenset({"workflow"}))}),
        preview=True,
    )
    service = _service(factory)
    service.read_record(scope, ReadProjectRecordRequest(1, ref, [field_id], "workflow"))
    return factory, project_id, table, ref, field_id, scope, service


def real_rows(factory):
    with factory() as session:
        return [(row.key_value, dict(row.values_json), row.content_revision) for row in session.scalars(select(DataRecordRow))]


def value(snapshot, field_id):
    return next(item["value"] for item in snapshot["values"] if item["fieldId"] == field_id)


def query(service, scope, table, field_id):
    return service.query_records(scope, QueryProjectRecordsRequest(
        1, scope.project_id, table["tableId"], table["datasetGeneration"], [field_id], "workflow", None, [], None, 100))


def test_a_preview_update_is_visible_to_later_reads_and_queries_only(preview):
    factory, _project, table, ref, field_id, scope, service = preview
    before = real_rows(factory)
    updated, _ = service.update_record(scope, UpdateProjectRecordCommand(uid(), 1, ref, {field_id: "预览值"}))
    assert value(updated, field_id) == "预览值"
    assert value(service.read_record(scope, ReadProjectRecordRequest(1, ref, [field_id], "workflow")), field_id) == "预览值"
    assert [value(item, field_id) for item in query(service, scope, table, field_id)["items"]] == ["预览值"]
    assert real_rows(factory) == before
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SyncOperationRow)) == 0


def test_a_preview_created_record_is_queryable_but_cannot_reach_real_writes(preview):
    factory, project_id, table, _ref, field_id, scope, service = preview
    before = real_rows(factory)
    created, _ = service.create_record(scope, CreateProjectRecordCommand(
        uid(), 1, project_id, table["tableId"], table["datasetGeneration"], {field_id: "预览新建"}))
    assert value(created, field_id) == "预览新建"
    assert sorted(value(item, field_id) for item in query(service, scope, table, field_id)["items"]) == ["original", "预览新建"]
    assert real_rows(factory) == before
    key = created["ref"]["recordKey"]
    preview_ref = RecordRef(project_id, table["tableId"], table["datasetGeneration"], RecordKey(key["type"], key["value"]))
    real_scope = replace(scope, preview=False)
    with pytest.raises(ProjectError):
        service.update_record(real_scope, UpdateProjectRecordCommand(uid(), 1, preview_ref, {field_id: "真实写入"}))
    assert real_rows(factory) == before


def test_preview_writes_replay_like_real_ones(preview):
    _factory, _project, _table, ref, field_id, scope, service = preview
    command = UpdateProjectRecordCommand(uid(), 1, ref, {field_id: "一次"})
    first, replayed_first = service.update_record(scope, command)
    again, replayed = service.update_record(scope, command)
    assert (replayed_first, replayed) == (False, True) and again == first


@pytest.mark.parametrize(("mode", "expected"), [(None, False), ("realWrites", False), ("previewWrites", True)])
def test_the_start_request_freezes_the_write_mode_into_the_capability_scope(tmp_path, mode, expected):
    from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
    from autoflow.infrastructure.database.project_capabilities import (
        SqlAlchemyProjectDataCapabilities,
    )
    from autoflow.infrastructure.database.record_ledger_models import (
        AutomationRecordLedgerRow,
    )
    from tests.integration.test_project_run_data_start import _setup

    factory, project_id, automation, coordinator = _setup(
        tmp_path, resolve_create_record_targets=lambda _session, _automation: [])
    payload = {"expectedAutomationRevision": automation.management_revision, "parameters": {}, "maxTasks": 1, "concurrency": 1}
    if mode is not None:
        payload["executionMode"] = mode
    batch = coordinator.start(project_id, automation.automation_id, uid(), payload)[0]
    assert ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id) == "ready"
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    with factory.begin() as session:
        from autoflow.infrastructure.database.workflow_runtime_models import (
            WorkflowRunRow,
        )
        run = session.get(WorkflowRunRow, task.run_id)
        run.execution_generation, run.status = 1, "running"
        binding = dict(run.capability_bindings[0])
        binding["executionGeneration"] = 1
        run.capability_bindings = [binding]
    scope = SqlAlchemyProjectDataCapabilities(factory).scope(project_id, task.task_id, task.run_id)
    assert scope.preview is expected
    with factory() as session:
        units = session.scalar(select(func.count()).select_from(AutomationRecordLedgerRow))
    assert units == (0 if expected else 1), "a preview never consumes processing records"
    factory.dispose()


def test_an_unknown_write_mode_is_refused(tmp_path):
    from autoflow.domain.project_runs.models import ProjectRunError
    from tests.integration.test_project_run_data_start import _setup

    factory, project_id, automation, coordinator = _setup(tmp_path)
    with pytest.raises(ProjectRunError) as refused:
        coordinator.start(project_id, automation.automation_id, uid(), {
            "expectedAutomationRevision": automation.management_revision, "parameters": {},
            "maxTasks": 1, "concurrency": 1, "executionMode": "maybe"})
    assert refused.value.status == 422
    factory.dispose()
