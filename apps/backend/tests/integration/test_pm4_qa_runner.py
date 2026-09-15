from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
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
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)
from tests.integration.test_project_run_data_start import _setup, uid
from tests.qa.pm4_fake_executor import CREATE_ACCOUNT, PauseBarrier
from tests.qa.pm4_sidecar import _b_capability_manifest, _create_targets, _status_inputs
from tests.qa.pm4_v1_runner import PM4V1FakeRunner


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
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    barrier = PauseBarrier(before_step="set_status:email")
    pending = asyncio.create_task(PM4V1FakeRunner(factory, pause_barrier=barrier).tick())
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
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    barrier = PauseBarrier(before_step="set_status:email")
    pending = asyncio.create_task(PM4V1FakeRunner(factory, pause_barrier=barrier).tick())
    await barrier.wait_until_reached()
    current = coordinator.get_batch(project_id, batch.batch_id)
    scheduler = ProjectBatchScheduler(
        factory, None, QuiesceGate()  # type: ignore[arg-type]
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
        stored_operation = session.get(
            ProjectOperationRow, stop_operation.operation_id
        )
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
        assert session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 0
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
        assert session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 0
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
        assert session.scalar(select(func.count()).select_from(ProjectRecordLeaseRow)) == 0
        assert (
            session.scalar(select(func.count()).select_from(ProjectOperationRow))
            == operation_count
        )
    factory.dispose()
