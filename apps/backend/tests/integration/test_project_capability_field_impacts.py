"""Active task field contracts participate in field-change impact checks."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_impacts import (
    SqlAlchemyProjectDataImpacts,
)
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.integration.test_project_run_data_start import _setup, uid


def _field_ref(automation, index: int = 0) -> dict:
    return dict(automation.input_plan["inputs"][index]["fieldBindings"][0]["fieldRef"])


def _definition(factory, ref: dict) -> dict:
    with factory() as session:
        field = session.get(DataFieldRow, (ref["fieldId"], ref["datasetGeneration"]))
        assert field is not None
        return {
            "key": field.key,
            "name": field.name,
            "type": field.type,
            "required": field.required,
            "validation": field.validation,
        }


def _activate_task(
    factory, project_id: str, automation, table_grants: list[dict] | None = None
):
    runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
    prepared = runtime.prepare_content(
        prepare_operation_id=uid(),
        workflow_id=automation.workflow_id,
        source_revision=1,
        available_capabilities=["browser.cloakbrowser", "project.data"],
    )
    now = datetime.now(UTC)
    batch_id, task_id, snapshot_id, operation_id = uid(), uid(), uid(), uid()
    bindings = [
        {
            "capability": "project.data",
            "projectId": project_id,
            "taskId": task_id,
            # The queued run is generation 0; its first dispatch authority is 1.
            "executionGeneration": 1,
            "createRecordTargets": [],
            "tableGrants": table_grants or [],
            "writeInputIds": [],
            "statusInputIds": [],
        }
    ]
    with factory.begin() as session:
        operation = ProjectOperationRow(
            id=operation_id,
            project_id=project_id,
            idempotency_key=uid(),
            kind="startBatch",
            request_digest="a" * 64,
            status="succeeded",
            status_revision=2,
            resource={
                "type": "batch",
                "projectId": project_id,
                "batchId": batch_id,
            },
            result={"batch": {"batchId": batch_id}},
            error=None,
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        session.add(operation)
        session.flush()
        session.add(
            ProjectBatchRow(
                id=batch_id,
                project_id=project_id,
                automation_id=automation.automation_id,
                start_operation_id=operation_id,
                prepared_content_id=prepared.prepared_content_id,
                automation_revision=automation.management_revision,
                workflow_revision=1,
                status="accepted",
                status_revision=1,
                frozen_request={"maxTasks": 1, "concurrency": 1},
                created_at=now,
                completed_at=None,
            )
        )
        session.flush()
        run = runtime.prepare_run(
            run_request_id=uid(),
            prepared_content_id=prepared.prepared_content_id,
            parameters={},
            input_snapshot_ref={
                "projectId": project_id,
                "batchId": batch_id,
                "taskId": task_id,
                "inputSnapshotId": snapshot_id,
            },
            resource_request={"browser": "none"},
            capability_bindings=bindings,
            uow=session,
            created_at=now,
        )
        task = ProjectTaskRow(
            id=task_id,
            project_id=project_id,
            batch_id=batch_id,
            run_id=run.run_id,
            run_request_id=run.run_request_id,
            ordinal=0,
            created_at=now,
        )
        session.add(task)
        session.flush()
        inputs = []
        for configured in automation.input_plan["inputs"]:
            record = session.scalar(
                select(DataRecordRow).where(
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.table_id == configured["tableId"],
                    DataRecordRow.dataset_generation == configured["datasetGeneration"],
                )
            )
            assert record is not None
            inputs.append(
                {
                    "inputId": configured["inputId"],
                    "recordRef": {
                        "projectId": project_id,
                        "tableId": record.table_id,
                        "datasetGeneration": record.dataset_generation,
                        "recordKey": {
                            "type": record.key_type,
                            "value": record.key_value,
                        },
                    },
                    "fieldMappings": deepcopy(configured["fieldBindings"]),
                    "values": [
                        {
                            "fieldId": mapping["fieldRef"]["fieldId"],
                            "value": record.values_json[mapping["fieldRef"]["fieldId"]],
                        }
                        for mapping in configured["fieldBindings"]
                    ],
                }
            )
        session.add(
            ProjectTaskInputSnapshotRow(
                id=snapshot_id,
                task_id=task_id,
                batch_id=batch_id,
                parameters={},
                inputs=inputs,
                captured_at=now,
            )
        )
        return task


def _active_blockers(report: dict) -> list[dict]:
    return [
        blocker
        for blocker in report["blockers"]
        if blocker["code"] == "ACTIVE_TASK_FIELD_DEPENDENCY"
    ]


@pytest.mark.parametrize(
    ("property_name", "new_value"),
    [
        ("key", "renamed_value"),
        ("type", "number"),
        ("required", False),
        ("validation", {"minLength": 1}),
    ],
)
def test_active_input_snapshot_blocks_structural_field_changes(
    tmp_path, property_name, new_value
):
    factory, project_id, automation, _coordinator = _setup(tmp_path)
    task = _activate_task(factory, project_id, automation)
    ref = _field_ref(automation)
    change = {**_definition(factory, ref), property_name: new_value}

    report = SqlAlchemyProjectDataImpacts(factory).preview_field_update(
        project_id, ref, change
    )

    blocker = _active_blockers(report)[0]
    assert blocker["resource"] == {
        "type": "task",
        "projectId": project_id,
        "taskId": task.id,
        "runId": task.run_id,
        "references": ["input.fieldMappings", "input.values"],
    }
    factory.dispose()


def test_active_table_grant_blocks_structural_change_to_its_field(tmp_path):
    manifest: dict = {"tableGrants": [], "writeInputIds": []}
    factory, project_id, automation, _coordinator = _setup(
        tmp_path,
        resolve_data_capability_manifest=lambda _session, _automation: deepcopy(
            manifest
        ),
    )
    source_ref = _field_ref(automation)
    source = _definition(factory, source_ref)
    extra = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
        project_id,
        source_ref["tableId"],
        uid(),
        {
            "definition": {
                "key": "grant_only",
                "name": "仅能力引用",
                "type": "string",
                "required": False,
                "validation": {},
            },
            "expectedTableRevision": 2,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    ref = extra["ref"]
    manifest["tableGrants"] = [
        {
            "tableId": ref["tableId"],
            "datasetGeneration": ref["datasetGeneration"],
            "operations": ["queryRecords", "updateRecord"],
            "fieldIds": [ref["fieldId"]],
            "readPurposes": ["workflow"],
        }
    ]
    task = _activate_task(factory, project_id, automation, manifest["tableGrants"])

    report = SqlAlchemyProjectDataImpacts(factory).preview_field_update(
        project_id,
        ref,
        {
            "key": "grant_only_changed",
            "name": extra["name"],
            "type": extra["type"],
            "required": extra["required"],
            "validation": extra["validation"],
        },
    )

    assert source["key"] == "value"
    assert _active_blockers(report)[0]["resource"] == {
        "type": "task",
        "projectId": project_id,
        "taskId": task.id,
        "runId": task.run_id,
        "references": ["capability.tableGrants"],
    }
    factory.dispose()


def test_display_name_and_unreferenced_field_changes_remain_compatible(tmp_path):
    factory, project_id, automation, _coordinator = _setup(tmp_path)
    input_ref = _field_ref(automation)
    extra = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
        project_id,
        input_ref["tableId"],
        uid(),
        {
            "definition": {
                "key": "optional_note",
                "name": "无关可选字段",
                "type": "string",
                "required": False,
                "validation": {},
            },
            "expectedTableRevision": 2,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    _activate_task(factory, project_id, automation)
    store = SqlAlchemyProjectDataImpacts(factory)

    input_definition = _definition(factory, input_ref)
    label_report = store.preview_field_update(
        project_id, input_ref, {**input_definition, "name": "新显示名称"}
    )
    extra_definition = _definition(factory, extra["ref"])
    unrelated_report = store.preview_field_update(
        project_id,
        extra["ref"],
        {**extra_definition, "key": "optional_note_v2"},
    )

    assert _active_blockers(label_report) == []
    assert _active_blockers(unrelated_report) == []
    factory.dispose()


def test_require_rechecks_task_that_started_after_preview(tmp_path):
    factory, project_id, automation, _coordinator = _setup(tmp_path)
    ref = _field_ref(automation)
    change = {**_definition(factory, ref), "key": "started_later"}
    store = SqlAlchemyProjectDataImpacts(factory)
    report = store.preview_field_update(project_id, ref, change)
    assert _active_blockers(report) == []
    _activate_task(factory, project_id, automation)

    with factory.begin() as session, pytest.raises(ProjectError) as caught:
        store.require_field_update(
            session, project_id, ref, change, report["impactRevision"]
        )

    assert caught.value.code == "PRECONDITION_FAILED"
    assert caught.value.details is not None
    assert caught.value.details["blockers"][0]["code"] == (
        "ACTIVE_TASK_FIELD_DEPENDENCY"
    )
    with factory() as session:
        assert session.scalar(select(ProjectTaskRow)) is not None
        assert session.scalar(select(WorkflowRunRow)).status == "queued"
    factory.dispose()


def test_terminal_task_no_longer_blocks_its_frozen_field(tmp_path):
    factory, project_id, automation, _coordinator = _setup(tmp_path)
    task = _activate_task(factory, project_id, automation)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        run.status = "succeeded"
        run.status_revision += 1
        run.completed_at = datetime.now(UTC)
    ref = _field_ref(automation)

    report = SqlAlchemyProjectDataImpacts(factory).preview_field_update(
        project_id, ref, {**_definition(factory, ref), "key": "after_completion"}
    )

    assert _active_blockers(report) == []
    factory.dispose()
