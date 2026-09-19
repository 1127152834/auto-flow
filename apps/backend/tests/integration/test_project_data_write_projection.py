from datetime import UTC, datetime, timedelta

from autoflow.application.project_runs.queries import _data_writes
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data_models import DataChangeRow
from autoflow.infrastructure.database.project_run_models import (
    ProjectTaskRecordQueryRow,
    ProjectTaskRecordReadRow,
)
from tests.integration.test_project_run_data_start import _setup, uid


def test_task_projection_uses_confirmed_operation_result_for_field_facts(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    batch = coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id)
        == "ready"
    )
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    snapshot = coordinator.get_snapshot(project_id, task.task_id)
    record = snapshot.inputs[0]
    input_ref = record["recordRef"]
    record_ref = {
        "projectId": input_ref["projectId"],
        "tableId": input_ref["tableId"],
        "datasetGeneration": input_ref["datasetGeneration"],
        "recordKey": {
            "type": input_ref["recordKey"]["type"],
            "value": input_ref["recordKey"]["value"],
        },
    }
    table_id = record_ref["tableId"]
    generation = record_ref["datasetGeneration"]
    base = datetime.now(UTC)

    added = {
        "ref": {
            "projectId": project_id,
            "tableId": table_id,
            "datasetGeneration": generation,
            "fieldId": uid(),
        },
        "key": "note",
        "name": "备注",
        "type": "string",
        "required": False,
        "validation": {},
        "fieldRevision": 1,
    }
    modified = {**added, "name": "任务备注", "required": True, "fieldRevision": 2}

    def operation(kind: str, result: dict, offset: int, *, status: str = "succeeded"):
        operation_id = uid()
        return ProjectOperationRow(
            id=operation_id,
            project_id=project_id,
            idempotency_key=operation_id,
            kind=kind,
            request_digest=str(offset) * 64,
            status=status,
            status_revision=1,
            resource={
                "taskId": task.task_id,
                "runId": task.run_id,
                "executionGeneration": 0,
            },
            result=result,
            error=None if status == "succeeded" else {"code": "REVISION_CONFLICT"},
            created_at=base + timedelta(seconds=offset),
            updated_at=base + timedelta(seconds=offset),
            completed_at=base + timedelta(seconds=offset),
        )

    add_operation = operation(
        "addField",
        {"action": "create", "created": True, "field": added, "tableRevision": 2},
        1,
    )
    modify_operation = operation(
        "modifyField",
        {"action": "update", "field": modified, "tableRevision": 3},
        2,
    )
    ensure_operation = operation(
        "ensureField",
        {"action": "ensure", "created": False, "field": modified, "tableRevision": 3},
        3,
    )
    rejected_operation = operation(
        "ensureField",
        {"action": "ensure", "created": False, "field": modified, "tableRevision": 3},
        4,
        status="failed",
    )

    with factory.begin() as session:
        session.add_all(
            [add_operation, modify_operation, ensure_operation, rejected_operation]
        )
        session.add_all(
            [
                DataChangeRow(
                    id=uid(),
                    project_id=project_id,
                    operation_id=add_operation.id,
                    sequence=1,
                    resource={"type": "field", "fieldRef": added["ref"]},
                    origin="workflow",
                    before=None,
                    after=added,
                    created_at=add_operation.created_at,
                ),
                DataChangeRow(
                    id=uid(),
                    project_id=project_id,
                    operation_id=modify_operation.id,
                    sequence=1,
                    resource={"type": "field", "fieldRef": modified["ref"]},
                    origin="workflow",
                    before=added,
                    after=modified,
                    created_at=modify_operation.created_at,
                ),
                ProjectTaskRecordReadRow(
                    id=uid(),
                    project_id=project_id,
                    task_id=task.task_id,
                    run_id=task.run_id,
                    execution_generation=0,
                    table_id=table_id,
                    dataset_generation=generation,
                    key_type=record_ref["recordKey"]["type"],
                    key_value=record_ref["recordKey"]["value"],
                    field_ids=[],
                    read_purpose="workflow",
                    content_revision=record["contentRevision"],
                    status_revision=record["statusRevision"],
                    link_revision=record["linkRevision"],
                    snapshot={"ref": record_ref, "values": []},
                    created_at=base,
                ),
            ]
        )
        session.add(
            ProjectTaskRecordQueryRow(
                id=uid(),
                project_id=project_id,
                task_id=task.task_id,
                run_id=task.run_id,
                execution_generation=0,
                table_id=table_id,
                dataset_generation=generation,
                request_digest="q" * 64,
                request_payload={
                    "readPurpose": "workflow",
                    "filter": {"type": "all", "items": []},
                    "orderBy": [],
                    "fieldIds": [],
                    "cursor": None,
                    "limit": 20,
                },
                result_count=0,
                created_at=base - timedelta(seconds=1),
            )
        )

    with factory() as session:
        writes = _data_writes(session, project_id, task.task_id, visits=[])

    assert [write["kind"] for write in writes] == [
        "query",
        "read",
        "fieldAdded",
        "fieldModified",
        "fieldEnsured",
    ]
    assert writes[0]["recordDisplay"] == "命中 0 条"
    assert writes[0]["detail"] == "读取用途：workflow"
    assert writes[2]["tableDisplay"] == "人员"
    assert writes[2]["recordDisplay"] == "备注"
    assert writes[2]["afterSummary"] == "string · 可选"
    assert writes[3]["recordDisplay"] == "任务备注"
    assert writes[3]["beforeSummary"] == "string · 可选"
    assert writes[3]["afterSummary"] == "string · 必填"
    assert writes[4]["detail"] == "字段已存在，无需变更"
    assert all(write["outcome"] == "succeeded" for write in writes)
    factory.dispose()
