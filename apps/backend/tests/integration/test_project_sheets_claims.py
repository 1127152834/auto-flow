"""Real HTTP bindings share physical identity without sharing local values."""

import json
from contextlib import contextmanager

import pytest
from sqlalchemy import select

from autoflow.infrastructure.database.project_claims import (
    SqlAlchemyProjectInputGroups,
    _lease_key,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.project_sync_models import SheetsBindingRow
from tests.integration.test_project_run_data_start import _input, uid
from tests.integration.test_project_sheets_sync import (
    COLUMNS,
    FakeSheetsTransport,
    new_key,
    open_sheets_table,
    pull,
)


@contextmanager
def shared_tables(tmp_path, *, same_project=False, identity_column="A"):
    from tests.fixtures.sheets import (
        SheetsTable,
        binding_impact,
        connect,
        new_field,
        new_project,
        new_table,
    )

    columns = [*COLUMNS, ("note", "备注", "string")]
    transport = FakeSheetsTransport(
        {"数据": [["编号", "标题", "备注"], ["A-1", "original", "old-note"]]}
    )
    with open_sheets_table(tmp_path, transport, columns) as first:
        client = first.client
        project = first.project if same_project else new_project(client, "Q")
        connection = connect(client, project, new_key())["result"]["connectionId"]
        table = new_table(client, project, "T2")["tableId"]
        fields = {
            key: new_field(
                client,
                project,
                table,
                key,
                name,
                type=kind,
                expectedTableRevision=index + 1,
            )
            for index, (key, name, kind) in enumerate(columns)
        }
        body = {
            "connectionId": connection,
            "spreadsheetId": transport.spreadsheet_id,
            "sheetId": 1000,
            "identityStrategy": {"kind": "column", "columnId": identity_column},
            "mapping": [
                {
                    "fieldId": fields[key]["ref"]["fieldId"],
                    "columnId": chr(65 + i),
                    "direction": "both",
                    "formula": False,
                }
                for i, (key, _, _) in enumerate(columns)
            ],
            "expectedTableRevision": 4,
        }
        accepted = client.put(
            f"/api/v1/projects/{project}/tables/{table}/sheets/binding",
            json=binding_impact(client, project, table, body),
            headers=new_key(),
        )
        assert accepted.status_code == 202, accepted.text
        second = SheetsTable(
            client,
            transport,
            project,
            table,
            connection,
            fields,
            accepted.json()["operation"]["result"],
        )
        pull(first)
        pull(second)
        yield first, second


def plan_for(bound):
    return {
        "inputs": [
            _input(
                bound.project,
                {
                    "tableId": bound.table,
                    "datasetGeneration": bound.dataset_generation(),
                },
                bound.fields["title"],
                "input",
            )
        ]
    }


def test_shared_sheet_lease_keys(tmp_path):
    with (
        shared_tables(tmp_path) as (first, second),
        first.client.app.state.session_factory() as session,
    ):
        selections = [
            SqlAlchemyProjectInputGroups(session).select_required(
                bound.project, plan_for(bound)
            )
            for bound in (first, second)
        ]
        assert [s.status for s in selections] == ["ready", "ready"]
        assert selections[0].lease_keys == selections[1].lease_keys
        key = json.loads(_lease_key(selections[0].lease_keys[0]))
        assert set(key) == {
            "source",
            "spreadsheetId",
            "sheetId",
            "identityNamespace",
            "recordKey",
        }
        assert key["source"] == "sheets"
        assert selections[0].inputs[0].record_ref != selections[1].inputs[0].record_ref
        assert selections[0].inputs[0].value["sourceIdentity"]["bindingEpoch"] == 1


def start_bound(bound):
    from autoflow.application.project_automations.service import (
        ProjectAutomationService,
    )
    from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
    from autoflow.application.workflows.runtime import WorkflowRuntimeService
    from autoflow.application.workflows.service import WorkflowService
    from autoflow.infrastructure.database.project_automations import (
        SqlAlchemyProjectAutomations,
    )
    from autoflow.infrastructure.database.projects import SqlAlchemyProjects
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
    from tests.fixtures.workflows import workflow_payload

    factory = bound.client.app.state.session_factory
    workflows = SqlAlchemyWorkflowRepository(factory)
    workflow = WorkflowService(workflows).create(workflow_payload(uid()), uid())
    automation = ProjectAutomationService(
        SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)
    ).create(
        bound.project,
        uid(),
        {
            "name": "共享领取",
            "description": "",
            "workflowId": workflow.workflow_id,
            "inputPlan": plan_for(bound),
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
    coordinator = ProjectRunCoordinator(
        factory,
        WorkflowRuntimeService(factory, workflows),
        resolve_resources=lambda *_: {"browser": "none", "modelProviderId": None},
        available_capabilities=["browser.cloakbrowser", "project.data"],
    )
    batch, _, _ = coordinator.start(
        bound.project,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": 1,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )
    return batch


def test_shared_claim_busy_rolls_back_and_release_allows_other_local_snapshot(tmp_path):
    from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
    from tests.integration.test_project_sheets_sync import edit_title

    with shared_tables(tmp_path) as (first, second):
        edit_title(second, second.records()[0], "Q 的本地值")
        batches = [start_bound(bound) for bound in (first, second)]
        factory = first.client.app.state.session_factory
        assert (
            ProjectBatchScheduler.claim_data_task(
                factory, first.project, batches[0].batch_id
            )
            == "ready"
        )
        assert (
            ProjectBatchScheduler.claim_data_task(
                factory, second.project, batches[1].batch_id
            )
            == "temporarilyBusy"
        )
        with factory.begin() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow)).all()
            assert len(leases) == 1
            assert len(session.scalars(select(ProjectTaskRow)).all()) == 1
            assert len(session.scalars(select(ProjectTaskInputSnapshotRow)).all()) == 1
            leases[
                0
            ].state = "released"  # Simulate the already-confirmed owner termination, not worker cleanup.
            from autoflow.infrastructure.database.workflow_runtime_models import (
                WorkflowRunRow,
            )

            session.get(WorkflowRunRow, leases[0].run_id).status = "succeeded"
        assert (
            ProjectBatchScheduler.claim_data_task(
                factory, second.project, batches[1].batch_id
            )
            == "ready"
        )
        with factory() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow)).all()
            assert len(leases) == 2 and leases[0].lease_key == leases[1].lease_key
            snapshot = session.scalar(
                select(ProjectTaskInputSnapshotRow)
                .join(
                    ProjectTaskRow,
                    ProjectTaskRow.id == ProjectTaskInputSnapshotRow.task_id,
                )
                .where(ProjectTaskRow.project_id == second.project)
            )
            assert any(
                value["value"] == "Q 的本地值" for value in snapshot.inputs[0]["values"]
            )
        assert first.records()[0]["contentRevision"] == 1
        assert second.records()[0]["contentRevision"] == 2


@pytest.mark.parametrize(
    "change", ["epoch", "identity", "missing", "duplicate", "header"]
)
def test_source_identity_changes_reject_prepared_claim(tmp_path, change):
    with shared_tables(tmp_path) as (first, _second):
        factory = first.client.app.state.session_factory
        plan = plan_for(first)
        with factory() as session:
            prepared = SqlAlchemyProjectInputGroups(session).select_required(
                first.project, plan
            )
            assert prepared.status == "ready"
        if change in {"epoch", "identity"}:
            with factory.begin() as session:
                binding = session.get(SheetsBindingRow, first.table)
                if change == "epoch":
                    binding.binding_epoch += 1
                else:
                    binding.identity_strategy = {"kind": "column", "columnId": "B"}
        else:
            grid = first.transport.grid("数据")
            if change == "missing":
                del grid[1:]
            elif change == "duplicate":
                grid.append(list(grid[1]))
            else:
                grid[0][0] = "different identity column"
            response = first.client.post(
                first.url("/sync/pull"),
                json={"expectedTableRevision": first.table_revision()},
                headers=new_key(),
            )
            assert response.status_code in {202, 409}
        with factory() as session:
            current = SqlAlchemyProjectInputGroups(session).revalidate_selected(
                first.project, plan, prepared
            )
            assert current.status != "ready"
            assert not session.scalars(select(ProjectRecordLeaseRow)).all()


def test_peer_observation_of_invalid_identity_blocks_old_local_proof(tmp_path):
    with shared_tables(tmp_path) as (first, second):
        first.transport.grid("数据").append(["A-1", "duplicate", "note"])
        response = second.client.post(
            second.url("/sync/pull"),
            json={"expectedTableRevision": second.table_revision()},
            headers=new_key(),
        )
        assert response.status_code == 202
        with first.client.app.state.session_factory() as session:
            selected = SqlAlchemyProjectInputGroups(session).select_required(
                first.project, plan_for(first)
            )
            assert selected.status == "configurationError"

@pytest.mark.parametrize("state", ["held", "reconciling"])
def test_legacy_active_local_sheet_lease_blocks_shared_claim(tmp_path, state):
    from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
    from autoflow.domain.project_runs.input_selection import LeaseKey
    with shared_tables(tmp_path) as (first, second):
        batch = start_bound(first)
        factory = first.client.app.state.session_factory
        assert ProjectBatchScheduler.claim_data_task(factory, first.project, batch.batch_id) == "ready"
        with factory.begin() as session:
            lease = session.scalar(select(ProjectRecordLeaseRow))
            from autoflow.infrastructure.database.project_claims import (
                _parse_record_ref,
            )
            ref = _parse_record_ref(lease.record_ref)
            lease.lease_key = _lease_key(LeaseKey("local", ref.project_id, ref.table_id, ref.dataset_generation, ref.record_key))
            lease.state = state
        with factory() as session:
            selection = SqlAlchemyProjectInputGroups(session).select_required(second.project, plan_for(second))
            assert selection.status == "temporarilyBusy"


def test_rejected_value_push_keeps_identity_claimable_and_peer_pull_independent(tmp_path):
    from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.integration.test_project_sheets_sync import edit_title, push, sync_operations

    with shared_tables(tmp_path) as (first, second):
        local = edit_title(first, first.records()[0], 'local survives rejection')
        first.transport.fail_writes.append(SheetsApiError(400, 'badRequest', 'rejected value'))
        assert push(first).status_code == 202
        failed, = sync_operations(first, 'failed')
        writes = first.transport.changes()
        pull(first)
        pull(second)
        assert first.records()[0] == local
        assert second.records()[0]['contentRevision'] == 1
        assert first.transport.grid('数据')[1][1] == 'original'
        assert sync_operations(first, 'failed') == [failed]
        batches = [start_bound(bound) for bound in (first, second)]
        factory = first.client.app.state.session_factory
        assert ProjectBatchScheduler.claim_data_task(factory, first.project, batches[0].batch_id) == 'ready'
        assert ProjectBatchScheduler.claim_data_task(factory, second.project, batches[1].batch_id) == 'temporarilyBusy'
        with factory() as session:
            task, = session.scalars(select(ProjectTaskRow)).all()
            assert task.project_id == first.project
            snapshot, = session.scalars(select(ProjectTaskInputSnapshotRow)).all()
            assert snapshot.inputs[0]['recordRef'] == local['ref']
            assert snapshot.inputs[0]['contentRevision'] == local['contentRevision']
            assert any(cell['value'] == 'local survives rejection' for cell in snapshot.inputs[0]['values'])
            lease, = session.scalars(select(ProjectRecordLeaseRow)).all()
            assert lease.state == 'held'
        assert first.transport.changes() == writes


@pytest.mark.parametrize('change', ['duplicate', 'blank', 'missing', 'header'])
def test_push_identity_observation_invalidates_stale_peer_claims(tmp_path, change):
    from tests.integration.test_project_sheets_sync import edit_title, push

    with shared_tables(tmp_path) as (first, second):
        local = edit_title(first, first.records()[0], 'keep local')
        grid = first.transport.grid('数据')
        if change == 'duplicate': grid.append(list(grid[1]))
        elif change == 'blank': grid.append(['', 'unidentified business row', 'note'])
        elif change == 'missing': del grid[1:]
        else: grid[0][0] = 'foreign identity'
        writes = first.transport.changes()
        assert push(first).status_code in {202, 409}
        with first.client.app.state.session_factory() as session:
            for bound in (first, second):
                selected = SqlAlchemyProjectInputGroups(session).select_required(bound.project, plan_for(bound))
                assert selected.status != 'ready', (change, bound.table, selected)
        assert first.records()[0] == local and first.transport.changes() == writes
