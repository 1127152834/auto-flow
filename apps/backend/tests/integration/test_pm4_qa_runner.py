from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.service import WorkflowService
from autoflow.bootstrap.config import Settings
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_project_run_data_start import _setup, uid
from tests.qa.pm4_fake_executor import CREATE_ACCOUNT, PauseBarrier
from tests.qa.pm4_sidecar import (
    _F_FORCE_STOP_GRACE,
    _apply_f_preview_override,
    _b_capability_manifest,
    _create_targets,
    _f_capability_manifest,
    _f_create_targets,
    _f_force_stop_projection,
    _f_status_inputs,
    _status_inputs,
    create_qa_app,
)
from tests.qa.pm4_v1_runner import PM4V1FakeRunner


def test_f_force_stop_projection_keeps_a_real_grace_before_the_fake_gate() -> None:
    accepted = datetime(2026, 9, 16, tzinfo=UTC)
    assert _f_force_stop_projection(
        "stopping", accepted, now=accepted + timedelta(seconds=1)
    ) == (False, accepted + timedelta(seconds=2))
    assert _f_force_stop_projection(
        "stopping", accepted, now=accepted + timedelta(seconds=2)
    ) == (True, accepted + timedelta(seconds=2))
    assert _f_force_stop_projection("completed", accepted, now=accepted)[0] is False


def test_f_sidecar_aligns_the_real_force_stop_grace_with_its_projection(tmp_path) -> None:
    """Both gates must share one grace or the UI enables what the core refuses."""
    app = create_qa_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="pm4-f-force-stop-grace",
            instance_token="secret",
        ),
        mode="f",
    )
    assert app.state.workflow_dispatcher._force_stop_grace == _F_FORCE_STOP_GRACE


@pytest.mark.parametrize(
    ("outcome", "detail"),
    [
        ("temporarilyBusy", "符合条件的记录暂时被其他任务占用"),
        ("configurationError", "数据输入配置或表结构已失效"),
    ],
)
def test_f_preview_override_preserves_real_input_facts_and_changes_only_last_candidate(
    outcome: str, detail: str
) -> None:
    original = {
        "runnable": True,
        "selectionStatus": "ready",
        "evaluatedCandidateBindings": 2,
        "inputs": [
            {
                "inputId": "person",
                "alias": "人员输入",
                "tableDisplay": "人员",
                "recordDisplay": "uuid · person-1",
                "values": [{"fieldName": "姓名", "value": "张三"}],
                "outcome": "ready",
                "required": True,
                "detail": None,
                "scannedCount": None,
            },
            {
                "inputId": "email",
                "alias": "邮箱输入",
                "tableDisplay": "邮箱",
                "recordDisplay": "uuid · email-1",
                "values": [{"fieldName": "邮箱地址", "value": "a@example.test"}],
                "outcome": "ready",
                "required": True,
                "detail": None,
                "scannedCount": None,
            },
        ],
    }

    projected = _apply_f_preview_override(original, outcome)

    assert original["runnable"] is True
    assert original["inputs"][1]["outcome"] == "ready"
    assert projected["runnable"] is False
    assert projected["selectionStatus"] == outcome
    assert projected["inputs"][0] == original["inputs"][0]
    assert projected["inputs"][1] == {
        **original["inputs"][1],
        "recordDisplay": None,
        "values": [],
        "outcome": outcome,
        "detail": detail,
    }


def test_f_preview_override_rejects_unknown_or_empty_candidates() -> None:
    with pytest.raises(ValueError, match="unsupported PM4-F preview outcome"):
        _apply_f_preview_override({"inputs": [{}]}, "ready")
    with pytest.raises(ValueError, match="at least one configured input"):
        _apply_f_preview_override({"inputs": []}, "temporarilyBusy")


def test_f_preview_control_is_authenticated_qa_only_and_not_in_openapi(tmp_path) -> None:
    app = create_qa_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="pm4-f-preview-control",
            instance_token="secret",
        ),
        mode="f",
    )
    path = "/api/v1/qa/pm4/input-preview"
    with TestClient(app) as client:
        assert client.post(path, json={"automationId": "writer"}).status_code == 401
        response = client.post(
            path,
            json={"automationId": "writer", "outcome": "temporarilyBusy"},
            headers={"x-autoflow-token": "secret"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "automationId": "writer",
            "outcome": "temporarilyBusy",
        }
        schema = client.get(
            "/openapi.json", headers={"x-autoflow-token": "secret"}
        ).json()
        assert path not in schema["paths"]


def _target_data(factory, project_id: str, automation) -> tuple[dict, dict]:
    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    email_table_id = automation.input_plan["inputs"][1]["tableId"]
    status = catalog.create_status(
        project_id,
        email_table_id,
        uid(),
        {
            "name": "已使用",
            "color": "#8f4b2b",
            "order": 1,
            "expectedTableRevision": 2,
        },
    )[0]["status"]
    account = DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, uid(), {"name": "账号"}
    )[0]
    for revision, (key, name) in enumerate(
        (("person", "人员"), ("email", "邮箱"), ("result", "网页结果")), start=1
    ):
        catalog.create_field(
            project_id,
            account["tableId"],
            uid(),
            {
                "definition": {
                    "key": key,
                    "name": name,
                    "type": "string",
                    "required": True,
                    "validation": {},
                },
                "expectedTableRevision": revision,
                "sourceColumnPolicy": "localOnly",
            },
        )
    return status, account


def _grant_account_target(coordinator, account: dict) -> None:
    coordinator._resolve_create_record_targets = lambda _session, _automation: (
        (account["tableId"], account["datasetGeneration"]),
    )
    coordinator._resolve_status_input_ids = lambda automation: (
        automation.input_plan["inputs"][1]["inputId"],
    )


def _grant_b_capabilities(coordinator, account: dict) -> None:
    _grant_account_target(coordinator, account)

    def manifest(session, _automation):
        field_ids = list(
            session.scalars(
                select(DataFieldRow.id).where(
                    DataFieldRow.project_id == account["projectId"],
                    DataFieldRow.table_id == account["tableId"],
                    DataFieldRow.dataset_generation == account["datasetGeneration"],
                )
            )
        )
        return {
            "tableGrants": [
                {
                    "tableId": account["tableId"],
                    "datasetGeneration": account["datasetGeneration"],
                    "operations": [
                        "readRecord",
                        "queryRecords",
                        "updateRecord",
                        "deleteRecord",
                        "addField",
                        "ensureField",
                        "modifyField",
                    ],
                    "fieldIds": field_ids,
                    "readPurposes": ["workflow"],
                }
            ]
        }

    coordinator._resolve_data_capability_manifest = manifest


def _create_account_reader(factory, project_id: str, account: dict):
    with factory() as session:
        field = session.scalar(
            select(DataFieldRow)
            .where(
                DataFieldRow.project_id == project_id,
                DataFieldRow.table_id == account["tableId"],
                DataFieldRow.dataset_generation == account["datasetGeneration"],
                DataFieldRow.key == "result",
            )
        )
        assert field is not None
        field_id = field.id
    document = workflow_payload()
    document["id"] = uid()
    workflow = WorkflowService(SqlAlchemyWorkflowRepository(factory)).create(document, uid())
    return ProjectAutomationService(
        SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)
    ).create(
        project_id,
        uid(),
        {
            "name": "账号结果复核",
            "description": "读取上一自动化创建的账号",
            "workflowId": workflow.workflow_id,
            "inputPlan": {
                "inputs": [
                    {
                        "inputId": uid(),
                        "alias": "账号输入",
                        "tableId": account["tableId"],
                        "datasetGeneration": account["datasetGeneration"],
                        "mode": "independent",
                        "required": True,
                        "fieldBindings": [
                            {
                                "inputFieldId": uid(),
                                "inputFieldAlias": "网页结果",
                                "fieldRef": {
                                    "projectId": project_id,
                                    "tableId": account["tableId"],
                                    "datasetGeneration": account[
                                        "datasetGeneration"
                                    ],
                                    "fieldId": field_id,
                                },
                            }
                        ],
                        "filter": {"type": "all", "items": []},
                        "orderBy": [
                            {"systemField": "recordKey", "direction": "asc"}
                        ],
                    }
                ]
            },
            "parameterSchema": [],
            "environmentPolicy": {"source": "newFromProfile"},
            "runPolicy": {
                "maxTasks": 1,
                "concurrency": 1,
                "maxLiveInstances": 1,
                "continueAfterFailure": False,
                "automaticExecutionTimeoutSeconds": 60,
                "manualDeadlineSeconds": 300,
            },
        },
    )[0]


@pytest.mark.asyncio
async def test_runner_completes_real_writes_terminal_facts_and_lease_release(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    status, account = _target_data(factory, project_id, automation)
    _grant_account_target(coordinator, account)
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

    outcome = await PM4V1FakeRunner(factory).tick()

    assert outcome is not None and outcome.finalized
    assert outcome.result.status == "succeeded"
    assert outcome.result.to_dict()["executor"] == "fake"
    assert outcome.result.to_dict()["browser"] == "notExecuted"
    assert outcome.result.to_dict()["studio"] == "notExecuted"
    with factory() as session:
        run = session.get(WorkflowRunRow, outcome.result.run_id)
        stored_batch = session.get(ProjectBatchRow, batch.batch_id)
        leases = session.scalars(
            select(ProjectRecordLeaseRow).where(
                ProjectRecordLeaseRow.task_id == outcome.result.task_id
            )
        ).all()
        account_count = session.scalar(
            select(func.count())
            .select_from(DataRecordRow)
            .where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == account["tableId"],
                DataRecordRow.deleted.is_(False),
            )
        )
        email = session.scalar(
            select(DataRecordRow).where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == automation.input_plan["inputs"][1]["tableId"],
                DataRecordRow.deleted.is_(False),
            )
        )
        outputs = session.scalars(
            select(WorkflowRunEventRow)
            .where(
                WorkflowRunEventRow.run_id == outcome.result.run_id,
                WorkflowRunEventRow.kind == "output",
            )
            .order_by(WorkflowRunEventRow.sequence)
        ).all()
    assert run is not None and run.status == "succeeded"
    assert stored_batch is not None and stored_batch.status == "completed"
    assert leases and all(lease.state == "released" for lease in leases)
    assert account_count == 1
    assert email is not None and email.status_id == status["statusId"]
    assert outputs[0].payload["value"] == {
        "executor": "fake",
        "browser": "notExecuted",
        "studio": "notExecuted",
    }
    assert outputs[1].payload["value"] == {
        "邮箱状态": "已使用",
        "账号记录": "已新增 1 条",
    }
    assert await PM4V1FakeRunner(factory).tick() is None
    factory.dispose()


@pytest.mark.asyncio
async def test_final_runner_reads_account_created_by_first_automation_without_writing(
    tmp_path,
):
    factory, project_id, writer, coordinator = _setup(tmp_path)
    _status, account = _target_data(factory, project_id, writer)
    coordinator._resolve_create_record_targets = _f_create_targets
    coordinator._resolve_status_input_ids = _f_status_inputs
    coordinator._resolve_data_capability_manifest = _f_capability_manifest
    writer_batch = coordinator.start(
        project_id,
        writer.automation_id,
        uid(),
        {
            "expectedAutomationRevision": writer.management_revision,
            "parameters": {},
            "maxTasks": None,
            "concurrency": 1,
        },
    )
    runner = PM4V1FakeRunner(factory, max_auto_tasks=1)
    first = await runner.tick()
    assert first is not None and first.finalized

    reader = _create_account_reader(factory, project_id, account)
    batch = coordinator.start(
        project_id,
        reader.automation_id,
        uid(),
        {
            "expectedAutomationRevision": reader.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    second = await runner.tick()

    assert second is not None and second.finalized
    assert second.result.status == "succeeded"
    assert second.result.outputs["accountRead"]["values"]
    tasks = coordinator.list_tasks(project_id, batch.batch_id)
    assert len(tasks) == 1
    detail = ProjectRunQueries(factory).task_detail(project_id, tasks[0].task_id)
    assert [item["alias"] for item in detail["inputSnapshot"]["inputs"]] == [
        "账号输入"
    ]
    assert [item["kind"] for item in detail["dataWrites"]] == ["read"]
    with factory() as session:
        account_count = session.scalar(
            select(func.count())
            .select_from(DataRecordRow)
            .where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == account["tableId"],
                DataRecordRow.deleted.is_(False),
            )
        )
        event_kinds = list(
            session.scalars(
                select(WorkflowRunEventRow.kind)
                .where(WorkflowRunEventRow.run_id == tasks[0].run_id)
                .order_by(WorkflowRunEventRow.sequence)
            )
        )
    assert account_count == 1
    assert "log" in event_kinds
    assert len(coordinator.list_tasks(project_id, writer_batch[0].batch_id)) == 1
    factory.dispose()


@pytest.mark.asyncio
async def test_b_runner_projects_every_explicit_management_data_operation(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    status, account = _target_data(factory, project_id, automation)
    _grant_b_capabilities(coordinator, account)
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

    outcome = await PM4V1FakeRunner(factory, mode="b").tick()

    assert outcome is not None and outcome.finalized
    assert outcome.result.status == "succeeded"
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    detail = ProjectRunQueries(factory).task_detail(project_id, task.task_id)
    kinds = {item["kind"] for item in detail["dataWrites"]}
    assert kinds >= {
        "query",
        "read",
        "statusChange",
        "recordCreated",
        "recordUpdated",
        "recordDeleted",
        "fieldAdded",
        "fieldEnsured",
        "fieldModified",
    }
    with factory() as session:
        active_accounts = list(
            session.scalars(
                select(DataRecordRow).where(
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.table_id == account["tableId"],
                    DataRecordRow.deleted.is_(False),
                )
            )
        )
        email = session.scalar(
            select(DataRecordRow).where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == automation.input_plan["inputs"][1]["tableId"],
                DataRecordRow.deleted.is_(False),
            )
        )
        added_field = session.scalar(
            select(DataFieldRow).where(
                DataFieldRow.project_id == project_id,
                DataFieldRow.table_id == account["tableId"],
                DataFieldRow.key == "qa_note",
            )
        )
    assert len(active_accounts) == 1
    assert email is not None and email.status_id == status["statusId"]
    assert added_field is not None and added_field.name == "执行备注"
    factory.dispose()


@pytest.mark.asyncio
async def test_failed_second_step_reports_only_the_write_that_committed(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    _status, account = _target_data(factory, project_id, automation)
    _grant_account_target(coordinator, account)
    coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )

    outcome = await PM4V1FakeRunner(factory, fail_step=CREATE_ACCOUNT).tick()

    assert outcome is not None and outcome.finalized
    assert outcome.result.status == "failed"
    with factory() as session:
        account_count = session.scalar(
            select(func.count())
            .select_from(DataRecordRow)
            .where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == account["tableId"],
                DataRecordRow.deleted.is_(False),
            )
        )
        outputs = session.scalars(
            select(WorkflowRunEventRow)
            .where(
                WorkflowRunEventRow.run_id == outcome.result.run_id,
                WorkflowRunEventRow.kind == "output",
            )
            .order_by(WorkflowRunEventRow.sequence)
        ).all()
    assert account_count == 0
    assert outputs[1].payload["value"] == {"邮箱状态": "已使用"}
    factory.dispose()


@pytest.mark.asyncio
async def test_runner_recovers_lost_create_ack_without_duplicate_account(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    _status, account = _target_data(factory, project_id, automation)
    _grant_account_target(coordinator, account)
    coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )

    outcome = await PM4V1FakeRunner(
        factory, acknowledgement_loss_steps={CREATE_ACCOUNT}
    ).tick()

    assert outcome is not None and outcome.finalized
    kinds = [event.kind for event in outcome.result.events]
    assert "ackLost" in kinds and "operationRecovered" in kinds
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DataRecordRow)
                .where(
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.table_id == account["tableId"],
                    DataRecordRow.deleted.is_(False),
                )
            )
            == 1
        )
    factory.dispose()


@pytest.mark.asyncio
async def test_new_runner_recovers_running_task_after_writes_without_replaying_facts(
    tmp_path,
):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    _status, account = _target_data(factory, project_id, automation)
    _grant_account_target(coordinator, account)
    coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )

    abandoned = await PM4V1FakeRunner(
        factory, simulate_crash_before_finalize=True
    ).tick()
    recovered = await PM4V1FakeRunner(factory).tick()

    assert abandoned is not None and not abandoned.finalized
    assert recovered is not None and recovered.finalized
    assert recovered.result.status == "succeeded"
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DataRecordRow)
                .where(
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.table_id == account["tableId"],
                    DataRecordRow.deleted.is_(False),
                )
            )
            == 1
        )
    factory.dispose()


@pytest.mark.asyncio
async def test_old_generation_cannot_write_or_finalize_and_keeps_leases_held(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    _status, account = _target_data(factory, project_id, automation)
    _grant_account_target(coordinator, account)
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
    barrier = PauseBarrier(before_step="set_status:email")
    pending = asyncio.create_task(
        PM4V1FakeRunner(factory, pause_barrier=barrier).tick()
    )
    await barrier.wait_until_reached()
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        run.execution_generation += 1
        run.status_revision += 1
    barrier.release()

    outcome = await pending

    assert outcome is not None and not outcome.finalized
    assert outcome.result.status == "failed"
    assert outcome.result.error is not None
    assert outcome.result.error["code"] == "ProjectError"
    with factory() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        leases = session.scalars(
            select(ProjectRecordLeaseRow).where(
                ProjectRecordLeaseRow.task_id == task.task_id
            )
        ).all()
        assert run is not None and run.execution_generation == 2
        assert leases and all(lease.state == "held" for lease in leases)
    factory.dispose()


@pytest.mark.asyncio
async def test_stop_wins_before_first_step_and_runner_does_not_write(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    _status, account = _target_data(factory, project_id, automation)
    _grant_account_target(coordinator, account)
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
    barrier = PauseBarrier(before_step="set_status:email")
    pending = asyncio.create_task(
        PM4V1FakeRunner(factory, pause_barrier=barrier).tick()
    )
    await barrier.wait_until_reached()
    current = coordinator.get_batch(project_id, batch.batch_id)
    scheduler = ProjectBatchScheduler(
        factory,
        None,
        QuiesceGate(),  # type: ignore[arg-type]
    )
    stop_operation = await scheduler.stop(
        project_id,
        batch.batch_id,
        uid(),
        {
            "expectedStatusRevision": current.status_revision,
            "reason": "QA 验证停止收尾",
        },
    )
    barrier.release()

    outcome = await pending
    await PM4V1FakeRunner(factory).tick()

    assert outcome is not None and not outcome.finalized
    assert outcome.result.status == "failed"
    with factory() as session:
        account_count = session.scalar(
            select(func.count())
            .select_from(DataRecordRow)
            .where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == account["tableId"],
                DataRecordRow.deleted.is_(False),
            )
        )
        leases = session.scalars(
            select(ProjectRecordLeaseRow).where(
                ProjectRecordLeaseRow.task_id == task.task_id
            )
        ).all()
        email = session.scalar(
            select(DataRecordRow).where(
                DataRecordRow.project_id == project_id,
                DataRecordRow.table_id == automation.input_plan["inputs"][1]["tableId"],
                DataRecordRow.deleted.is_(False),
            )
        )
        run = session.get(WorkflowRunRow, task.run_id)
        stored_batch = session.get(ProjectBatchRow, batch.batch_id)
        stored_operation = session.get(ProjectOperationRow, stop_operation.operation_id)
    assert account_count == 0
    assert email is not None and email.status_id is None
    assert run is not None and run.status == "cancelled"
    assert stored_batch is not None and stored_batch.status == "stopped"
    assert stored_operation is not None and stored_operation.status == "succeeded"
    assert leases and all(lease.state == "released" for lease in leases)

    force_operation = await scheduler.stop(
        project_id,
        batch.batch_id,
        uid(),
        {"expectedStatusRevision": 1, "reason": "核验已停止事实"},
        force=True,
    )
    assert force_operation.status == "succeeded"
    assert force_operation.result is not None
    assert force_operation.result["batch"]["status"] == "stopped"
    factory.dispose()


@pytest.mark.asyncio
async def test_active_force_stop_revokes_generation_and_releases_leases(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    _status, account = _target_data(factory, project_id, automation)
    _grant_account_target(coordinator, account)
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
    with factory() as session:
        initial_run = session.get(WorkflowRunRow, task.run_id)
        assert initial_run is not None
        initial_generation = initial_run.execution_generation

    class ForceCore:
        def query_run(self, run_id):
            with factory() as session:
                run = session.get(WorkflowRunRow, run_id)
                assert run is not None
                return SimpleNamespace(status=run.status)

        def validate_force_stop(self, _run_id, _revision, _generation):
            return None

    scheduler = ProjectBatchScheduler(factory, ForceCore(), QuiesceGate())  # type: ignore[arg-type]
    normal = await scheduler.stop(
        project_id,
        batch.batch_id,
        uid(),
        {"expectedStatusRevision": batch.status_revision, "reason": "先请求普通停止"},
    )
    stopping = coordinator.get_batch(project_id, batch.batch_id)
    forced = await scheduler.stop(
        project_id,
        batch.batch_id,
        uid(),
        {
            "expectedStatusRevision": stopping.status_revision,
            "reason": "立即强制停止隔离执行",
        },
        force=True,
    )

    assert normal.status == "running"
    assert forced.status == "running"
    assert await PM4V1FakeRunner(factory).tick() is None
    with factory() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        stopped = session.get(ProjectBatchRow, batch.batch_id)
        leases = session.scalars(
            select(ProjectRecordLeaseRow).where(
                ProjectRecordLeaseRow.task_id == task.task_id
            )
        ).all()
        force_operation = session.scalar(
            select(ProjectOperationRow).where(
                ProjectOperationRow.idempotency_key == forced.idempotency_key
            )
        )
    assert run is not None and run.status == "interrupted"
    assert run.execution_generation == initial_generation + 1
    assert stopped is not None and stopped.status == "stopped"
    assert leases and all(lease.state == "released" for lease in leases)
    assert force_operation is not None and force_operation.status == "succeeded"
    factory.dispose()


@pytest.mark.asyncio
async def test_f_runner_fences_suspended_run_so_real_force_stop_gate_accepts(tmp_path):
    """F-mode normal stop must mirror the production fence, not leave the run running.

    The QA sidecar disables the production scheduler, so the QA runner owns the
    normal-stop fence. Without it the real dispatcher gate still sees a
    ``running`` run and rejects force stop with FORCE_STOP_GRACE_ACTIVE.
    """
    from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher

    factory, project_id, automation, coordinator = _setup(tmp_path)
    _status, account = _target_data(factory, project_id, automation)
    _grant_account_target(coordinator, account)
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
    now = datetime.now(UTC)
    with factory() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        run.status = "running"
        run.status_revision += 1
        run.execution_generation += 1
        run.started_at = run.updated_at = now
        session.commit()

    runner = PM4V1FakeRunner(factory, settle_normal_stops=False)
    core = WorkflowRunDispatcher(
        factory,
        SimpleNamespace(busy=lambda: False),  # type: ignore[arg-type]
        SimpleNamespace(),
        QuiesceGate(),
        lambda _run: None,
        force_stop_grace=timedelta(seconds=0),
    )
    scheduler = ProjectBatchScheduler(factory, core, QuiesceGate())
    await scheduler.stop(
        project_id,
        batch.batch_id,
        uid(),
        {"expectedStatusRevision": batch.status_revision, "reason": "普通停止"},
    )
    stopping = coordinator.get_batch(project_id, batch.batch_id)
    assert stopping.status == "stopping"
    # The suspended runner loop cannot tick, so the sidecar fences on wake instead.
    runner.fence_stopping_runs()

    with factory() as session:
        fenced = session.get(WorkflowRunRow, task.run_id)
        assert fenced is not None and fenced.status == "stopping"
        assert fenced.completed_at is None
        fenced_generation = fenced.execution_generation

    forced = await scheduler.stop(
        project_id,
        batch.batch_id,
        uid(),
        {"expectedStatusRevision": stopping.status_revision, "reason": "强制停止"},
        force=True,
    )
    assert forced.status == "running"
    # An accepted force stop revokes worker authority before the worker is released.
    runner.fence_stopping_runs()
    with factory() as session:
        revoked = session.get(WorkflowRunRow, task.run_id)
        assert revoked is not None and revoked.status == "reconciling"
        assert revoked.execution_generation == fenced_generation + 1
    await runner.tick()
    with factory() as session:
        interrupted = session.get(WorkflowRunRow, task.run_id)
        final = session.get(ProjectBatchRow, batch.batch_id)
        operation = session.scalar(
            select(ProjectOperationRow).where(
                ProjectOperationRow.idempotency_key == forced.idempotency_key
            )
        )
        assert interrupted is not None and interrupted.status == "interrupted"
        assert final is not None and final.status == "stopped"
        assert operation is not None and operation.status == "succeeded"
    factory.dispose()


def test_missing_qa_write_grant_rejects_start_without_durable_run_facts(tmp_path):
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_create_record_targets=_create_targets,
        resolve_status_input_ids=_status_inputs,
    )
    with factory() as session:
        operation_count = session.scalar(
            select(func.count()).select_from(ProjectOperationRow)
        )

    with pytest.raises(ProjectError) as caught:
        coordinator.start(
            project_id,
            automation.automation_id,
            uid(),
            {
                "expectedAutomationRevision": automation.management_revision,
                "parameters": {},
                "maxTasks": 1,
                "concurrency": 1,
            },
        )

    assert caught.value.code == "QA_FIXTURE_INCOMPLETE"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectBatchRow)) == 0
        assert session.scalar(select(func.count()).select_from(ProjectTaskRow)) == 0
        assert session.scalar(select(func.count()).select_from(WorkflowRunRow)) == 0
        assert (
            session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 0
        )
        assert (
            session.scalar(select(func.count()).select_from(ProjectOperationRow))
            == operation_count
        )
    factory.dispose()


def test_b_sidecar_manifest_grants_only_account_operations_and_fields(tmp_path):
    factory, project_id, automation, _coordinator = _setup(tmp_path)
    _status, account = _target_data(factory, project_id, automation)

    with factory() as session:
        manifest = _b_capability_manifest(session, automation)
        field_ids = list(
            session.scalars(
                select(DataFieldRow.id)
                .where(DataFieldRow.table_id == account["tableId"])
                .order_by(DataFieldRow.position, DataFieldRow.id)
            )
        )

    assert manifest == {
        "tableGrants": [
            {
                "tableId": account["tableId"],
                "datasetGeneration": account["datasetGeneration"],
                "operations": [
                    "readRecord",
                    "queryRecords",
                    "updateRecord",
                    "deleteRecord",
                    "addField",
                    "ensureField",
                    "modifyField",
                ],
                "fieldIds": field_ids,
                "readPurposes": ["workflow"],
            }
        ]
    }
    factory.dispose()


def test_missing_qa_status_grant_rejects_start_without_durable_run_facts(tmp_path):
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_create_record_targets=_create_targets,
        resolve_status_input_ids=_status_inputs,
    )
    _status, _account = _target_data(factory, project_id, automation)
    with factory.begin() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        assert row is not None
        row.input_plan = {
            "inputs": [
                {**item, "alias": f"输入 {index + 1}"}
                for index, item in enumerate(row.input_plan["inputs"])
            ]
        }
    with factory() as session:
        operation_count = session.scalar(
            select(func.count()).select_from(ProjectOperationRow)
        )

    with pytest.raises(ProjectError) as caught:
        coordinator.start(
            project_id,
            automation.automation_id,
            uid(),
            {
                "expectedAutomationRevision": automation.management_revision,
                "parameters": {},
                "maxTasks": 1,
                "concurrency": 1,
            },
        )

    assert caught.value.code == "QA_FIXTURE_INCOMPLETE"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectBatchRow)) == 0
        assert session.scalar(select(func.count()).select_from(ProjectTaskRow)) == 0
        assert session.scalar(select(func.count()).select_from(WorkflowRunRow)) == 0
        assert (
            session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 0
        )
        assert (
            session.scalar(select(func.count()).select_from(ProjectOperationRow))
            == operation_count
        )
    factory.dispose()


def test_missing_qa_status_target_rejects_start_without_durable_run_facts(tmp_path):
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_create_record_targets=_create_targets,
        resolve_status_input_ids=_status_inputs,
    )
    DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, uid(), {"name": "账号"}
    )
    with factory() as session:
        operation_count = session.scalar(
            select(func.count()).select_from(ProjectOperationRow)
        )

    with pytest.raises(ProjectError) as caught:
        coordinator.start(
            project_id,
            automation.automation_id,
            uid(),
            {
                "expectedAutomationRevision": automation.management_revision,
                "parameters": {},
                "maxTasks": 1,
                "concurrency": 1,
            },
        )

    assert caught.value.code == "QA_FIXTURE_INCOMPLETE"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectBatchRow)) == 0
        assert session.scalar(select(func.count()).select_from(ProjectTaskRow)) == 0
        assert session.scalar(select(func.count()).select_from(WorkflowRunRow)) == 0
        assert (
            session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 0
        )
        assert (
            session.scalar(select(func.count()).select_from(ProjectOperationRow))
            == operation_count
        )
    factory.dispose()
