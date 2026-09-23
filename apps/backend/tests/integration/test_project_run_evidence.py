"""PM7-A1: frozen inputs vs live values, write attribution, node visit chain."""

from datetime import UTC, datetime, timedelta

from autoflow.adapters.http.project_run_schemas import TaskDetail
from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_runs.evidence import ProjectRunEvidence
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.domain.project_data.capabilities import SetRecordStatusCommand
from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)
from sqlalchemy import func, select

from tests.integration.test_project_run_data_start import _setup, uid


def _claim(tmp_path):
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_status_input_ids=lambda current: (
            current.input_plan["inputs"][1]["inputId"],
        ),
    )
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
    # the worker bumps the generation and leaves queued before invoking a node
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.execution_generation = 1
        run.status = "running"
    return factory, project_id, coordinator, task


def _retry_chain(factory, run_id: str, *, node_id: str, visit_id: str, start: datetime):
    """Three sequential attempts of one node visit, as the worker records them."""
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, run_id)
        sequence = (
            session.scalar(
                select(func.count())
                .select_from(WorkflowRunEventRow)
                .where(WorkflowRunEventRow.run_id == run_id)
            )
            or 0
        )
        for attempt in range(1, 4):
            opened = start + timedelta(seconds=attempt * 2)
            closed = opened + timedelta(seconds=1)
            for status, occurred_at in (("started", opened), ("succeeded", closed)):
                sequence += 1
                session.add(
                    WorkflowRunEventRow(
                        run_id=run_id,
                        sequence=sequence,
                        event_id=uid(),
                        execution_generation=run.execution_generation,
                        kind="nodeAttempt",
                        node_id=node_id,
                        node_visit_id=visit_id,
                        attempt=attempt,
                        occurred_at=occurred_at,
                        payload={"status": status},
                    )
                )
        run.last_sequence = sequence


def test_current_inputs_show_live_values_next_to_the_frozen_snapshot(tmp_path):
    factory, project_id, coordinator, task = _claim(tmp_path)
    snapshot = coordinator.get_snapshot(project_id, task.task_id)
    email = snapshot.inputs[1]

    # the human edits the same record after the task froze its input
    DataRecordService(SqlAlchemyProjectDataRecords(factory)).update(
        project_id,
        email["recordRef"]["tableId"],
        encode_record_key(
            RecordKey(
                email["recordRef"]["recordKey"]["type"],
                email["recordRef"]["recordKey"]["value"],
            )
        ),
        uid(),
        {
            "datasetGeneration": email["recordRef"]["datasetGeneration"],
            "recordKeyType": email["recordRef"]["recordKey"]["type"],
            "values": [
                {"fieldId": email["values"][0]["fieldId"], "value": "edited@example.test"}
            ],
            "expectedContentRevision": 1,
        },
    )

    detail = ProjectRunQueries(factory).task_detail(project_id, task.task_id)
    TaskDetail.model_validate(detail)
    assert [item["inputId"] for item in detail["currentInputs"]] == [
        item["inputId"] for item in snapshot.inputs
    ]
    assert all(item["exists"] for item in detail["currentInputs"])
    current = detail["currentInputs"][1]
    assert current["values"][0]["fieldName"] == "值"
    assert current["values"][0]["value"] == "edited@example.test"
    assert current["changedFieldIds"] == [email["values"][0]["fieldId"]]
    assert current["contentRevision"] == 2
    # the frozen snapshot stays untouched evidence
    assert detail["inputSnapshot"]["inputs"][1]["values"][0]["value"] == (
        email["values"][0]["value"]
    )
    factory.dispose()


def test_current_inputs_report_a_missing_record_instead_of_faking_a_value(tmp_path):
    factory, project_id, coordinator, task = _claim(tmp_path)
    snapshot = coordinator.get_snapshot(project_id, task.task_id)
    email = snapshot.inputs[1]
    with factory.begin() as session:
        row = session.scalar(
            select(DataRecordRow).where(
                DataRecordRow.table_id == email["recordRef"]["tableId"],
                DataRecordRow.key_value == email["recordRef"]["recordKey"]["value"],
            )
        )
        row.deleted = True

    detail = ProjectRunQueries(factory).task_detail(project_id, task.task_id)
    TaskDetail.model_validate(detail)
    missing = detail["currentInputs"][1]
    assert missing["exists"] is False
    assert missing["values"] == []
    assert missing["contentRevision"] is None
    assert detail["inputSnapshot"]["inputs"][1]["values"][0]["value"] == (
        email["values"][0]["value"]
    )
    factory.dispose()


def test_data_writes_show_the_node_that_ran_them_and_ignore_other_tasks(tmp_path):
    factory, project_id, coordinator, task = _claim(tmp_path)
    snapshot = coordinator.get_snapshot(project_id, task.task_id)
    email = snapshot.inputs[1]
    status = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_status(
        project_id,
        email["recordRef"]["tableId"],
        uid(),
        {
            "name": "已使用",
            "color": "#8f4b2b",
            "order": 1,
            "expectedTableRevision": 2,
        },
    )[0]["status"]

    service = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))
    namespace = service.scope(project_id, task.task_id, task.run_id)
    service.set_record_status(
        namespace,
        SetRecordStatusCommand(
            uid(),
            1,
            RecordRef(
                project_id,
                email["recordRef"]["tableId"],
                email["recordRef"]["datasetGeneration"],
                RecordKey(
                    email["recordRef"]["recordKey"]["type"],
                    email["recordRef"]["recordKey"]["value"],
                ),
            ),
            status["statusId"],
            email["statusRevision"],
        ),
    )
    with factory() as session:
        write_at = session.scalar(
            select(ProjectOperationRow.created_at).where(
                ProjectOperationRow.kind == "setRecordStatus",
                ProjectOperationRow.resource["taskId"].as_string() == task.task_id,
            )
        )
    # the third attempt's window is the one that contains the committed write
    _retry_chain(
        factory,
        task.run_id,
        node_id="status-node",
        visit_id=uid(),
        start=write_at.replace(tzinfo=UTC) - timedelta(seconds=6),
    )

    # a different task's operation must never be attributed to this task
    with factory.begin() as session:
        session.add(
            ProjectOperationRow(
                id=uid(),
                project_id=project_id,
                idempotency_key=uid(),
                kind="setRecordStatus",
                request_digest="f" * 64,
                status="succeeded",
                status_revision=2,
                resource={"projectId": project_id, "taskId": uid()},
                result={"statusId": None},
                error=None,
                created_at=write_at,
                updated_at=write_at,
                completed_at=write_at,
            )
        )

    detail = ProjectRunQueries(factory).task_detail(project_id, task.task_id)
    TaskDetail.model_validate(detail)
    assert [item["kind"] for item in detail["dataWrites"]] == ["statusChange"]
    assert detail["dataWrites"][0]["nodeId"] == "status-node"
    assert detail["dataWrites"][0]["nodeName"] == "未命名节点"
    factory.dispose()


def test_node_attempts_keep_retries_of_one_visit_as_separate_rows(tmp_path):
    factory, project_id, _coordinator, task = _claim(tmp_path)
    started = datetime.now(UTC) - timedelta(seconds=30)
    _retry_chain(
        factory,
        task.run_id,
        node_id="status-node",
        visit_id=uid(),
        start=started,
    )
    with factory.begin() as session:
        events = session.scalars(
            select(WorkflowRunEventRow)
            .where(WorkflowRunEventRow.run_id == task.run_id, WorkflowRunEventRow.kind == "nodeAttempt")
            .order_by(WorkflowRunEventRow.sequence)
        ).all()
        events[0].payload = {"status": "started", "executionContext": {"scopes": [], "loops": []}}
        events[1].payload = {"status": "succeeded", "executionContext": {
            "scopes": [], "loops": [{"nodeId": "loop", "iteration": 2}],
        }}
    attempts, total = ProjectRunEvidence(factory).node_attempts(
        project_id, task.task_id, page=1, page_size=50
    )
    assert total == 3
    assert [item["attempt"] for item in attempts] == [1, 2, 3]
    assert {item["nodeId"] for item in attempts} == {"status-node"}
    assert all(item["status"] == "succeeded" for item in attempts)
    assert attempts[0]["executionContext"]["loops"][0]["iteration"] == 2
    assert attempts[0]["completedAt"] < attempts[1]["completedAt"]
    factory.dispose()
