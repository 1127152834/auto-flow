"""Shared claims must fence dynamic writes and binding changes too."""

import pytest
from sqlalchemy import select

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.domain.project_data.capabilities import (
    QueryProjectRecordsRequest,
    TableCapabilityGrant,
    TaskCapabilityScope,
    UpdateProjectRecordCommand,
)
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_claims import _parse_record_ref
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.fixtures.sheets import new_key
from tests.integration.test_project_capability_field_impacts import _activate_task
from tests.integration.test_project_run_data_start import uid
from tests.integration.test_project_sheets_claims import shared_tables, start_bound


def query_task(bound, extra_bounds=(), *, create=False):
    batch = start_bound(bound)
    factory = bound.client.app.state.session_factory
    grants = [{"tableId": current.table, "datasetGeneration": current.dataset_generation(),
               "operations": ["queryRecords", "updateRecord", *(["createRecord"] if create else [])], "fieldIds": [current.field_id("title"), *([current.field_id("code")] if create else [])],
               "readPurposes": ["workflow"]} for current in (bound, *extra_bounds)]
    automation = SqlAlchemyProjectAutomations(factory).get(bound.project, batch.automation_id)
    task = _activate_task(factory, bound.project, automation, grants)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.status = "running"
        run.execution_generation = 1
        run.status_revision += 1
    scope = TaskCapabilityScope(bound.project, task.id, task.run_id, 1,
        frozenset(), frozenset(), table_grants=frozenset(TableCapabilityGrant(
            grant["tableId"], grant["datasetGeneration"], frozenset(grant["operations"]),
            frozenset(grant["fieldIds"]), frozenset(grant["readPurposes"]),
        ) for grant in grants))
    return scope, ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))


def test_dynamic_query_write_cannot_bypass_other_project_source_lease(tmp_path):
    with shared_tables(tmp_path) as (first, second):
        batch = start_bound(first)
        factory = first.client.app.state.session_factory
        assert ProjectBatchScheduler.claim_data_task(factory, first.project, batch.batch_id) == "ready"
        scope, service = query_task(second)
        page = service.query_records(scope, QueryProjectRecordsRequest(
            1, second.project, second.table, second.dataset_generation(),
            [second.field_id("title")], "workflow", None, [], None, 10,
        ))
        row = page["items"][0]
        command = UpdateProjectRecordCommand(uid(), 1, _parse_record_ref(row["ref"]),
                                            {second.field_id("title"): "must not commit"}, 1)
        with pytest.raises(ProjectError) as busy:
            service.update_record(scope, command)
        assert busy.value.code == "LEASE_BUSY"
        assert second.records()[0]["contentRevision"] == 1
        with factory() as session:
            assert len(session.scalars(select(ProjectRecordLeaseRow)).all()) == 1


@pytest.mark.parametrize("action", ["removeSheetsBinding", "changeSheetsBinding"])
def test_shared_active_lease_blocks_source_mutation_without_foreign_details(tmp_path, action):
    with shared_tables(tmp_path) as (first, second):
        batch = start_bound(first)
        factory = first.client.app.state.session_factory
        assert ProjectBatchScheduler.claim_data_task(factory, first.project, batch.batch_id) == "ready"
        change = {"mode": "remove"} if action == "removeSheetsBinding" else {
            key: second.binding[key] for key in ("connectionId", "spreadsheetId", "sheetId", "identityStrategy", "mapping")
        }
        response = second.client.post(f"/api/v1/projects/{second.project}/mutation-impact", json={
            "action": action, "target": {"type": "table", "projectId": second.project, "tableId": second.table}, "change": change,
        })
        assert response.status_code == 200, response.text
        blockers = response.json()["blockers"]
        assert any(item["code"] == "SHEETS_SOURCE_IN_USE" for item in blockers)
        assert first.project not in str(blockers) and first.table not in str(blockers)
        if action == "removeSheetsBinding":
            removed = second.client.request("DELETE", second.url("/sheets/binding"), json={
                "expectedTableRevision": second.table_revision(), "impactRevision": response.json()["impactRevision"],
            }, headers=new_key())
            assert removed.status_code == 412, removed.text


def test_same_task_shared_row_keeps_separate_local_write_cursors(tmp_path):
    from autoflow.infrastructure.database.project_run_models import (
        ProjectTaskRecordCursorRow,
    )
    with shared_tables(tmp_path, same_project=True) as (first, second):
        scope, service = query_task(first, (second,))
        for bound, value in ((first, "P1"), (second, "Q1"), (first, "P2"), (second, "Q2")):
            page = service.query_records(scope, QueryProjectRecordsRequest(1, bound.project, bound.table,
                bound.dataset_generation(), [bound.field_id("title")], "workflow", None, [], None, 10))
            row = page["items"][0]
            changed, replayed = service.update_record(scope, UpdateProjectRecordCommand(uid(), 1,
                _parse_record_ref(row["ref"]), {bound.field_id("title"): value}, row["contentRevision"]))
            assert not replayed and changed["contentRevision"] == row["contentRevision"] + 1
        factory = first.client.app.state.session_factory
        with factory() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.task_id == scope.task_id)).all()
            cursors = session.scalars(select(ProjectTaskRecordCursorRow).where(ProjectTaskRecordCursorRow.task_id == scope.task_id)).all()
            assert len(leases) == 1
            assert len(cursors) == 2
            assert {cursor.lease_id for cursor in cursors} == {leases[0].id}
            assert {cursor.record_ref["tableId"] for cursor in cursors} == {first.table, second.table}
            assert [cursor.content_revision for cursor in cursors] == [3, 3]
        assert first.records()[0]["values"] != second.records()[0]["values"]
        # A downgrade cannot collapse two local versions back into one cursor.
        from pathlib import Path

        from alembic import command as alembic_command
        from alembic.config import Config

        from autoflow.infrastructure.database import session as session_module
        config = Config(str(Path(session_module.__file__).with_name("alembic.ini")))
        config.set_main_option("sqlalchemy.url", str(factory.kw["bind"].url))
        with pytest.raises(RuntimeError, match="Shared lease cursors exist"):
            alembic_command.downgrade(config, "pm09_shared_sheet_identity")
        with factory() as session:
            assert len(session.scalars(select(ProjectTaskRecordCursorRow).where(ProjectTaskRecordCursorRow.task_id == scope.task_id)).all()) == 2



def test_project_archive_waits_for_shared_source_owner(tmp_path):
    from autoflow.infrastructure.database.project_lifecycle import (
        SqlAlchemyProjectLifecycle,
    )
    with shared_tables(tmp_path) as (first, second):
        batch = start_bound(first)
        factory = first.client.app.state.session_factory
        assert ProjectBatchScheduler.claim_data_task(factory, first.project, batch.batch_id) == "ready"
        report = SqlAlchemyProjectLifecycle(factory).impact(second.project, "archive")
        assert any(item["code"] == "SHEETS_SOURCE_IN_USE" for item in report["blockers"])
        assert first.project not in str(report["blockers"])


def test_outbound_failure_does_not_revoke_valid_source_identity(tmp_path):
    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.integration.test_project_sheets_sync import edit_title, push
    with shared_tables(tmp_path) as (first, _second):
        edit_title(first, first.records()[0], "local change")
        first.transport.fail_writes.append(SheetsApiError(403, "denied", "denied"))
        assert push(first).status_code == 202
        batch = start_bound(first)
        factory = first.client.app.state.session_factory
        assert ProjectBatchScheduler.claim_data_task(factory, first.project, batch.batch_id) == "ready"


def test_created_record_uses_public_lease_and_original_command_replays(tmp_path):
    import json

    from autoflow.domain.project_data.capabilities import CreateProjectRecordCommand
    from autoflow.infrastructure.database.models import ProjectOperationRow
    with shared_tables(tmp_path) as (first, second):
        first_scope, first_service = query_task(first, create=True)
        second_scope, second_service = query_task(second, create=True)
        def command(bound):
            return CreateProjectRecordCommand(uid(), 1, bound.project, bound.table, bound.dataset_generation(),
                {bound.field_id("code"): "NEW-1", bound.field_id("title"): "created locally"})
        accepted = command(first)
        created, replayed = first_service.create_record(first_scope, accepted)
        assert not replayed and created["ref"]["recordKey"]["value"] == "NEW-1"
        again, replayed = first_service.create_record(first_scope, accepted)
        assert replayed and again == created
        rejected = command(second)
        with pytest.raises(ProjectError) as busy:
            second_service.create_record(second_scope, rejected)
        assert busy.value.code == "LEASE_BUSY"
        assert len(second.records()) == 1
        with first.client.app.state.session_factory() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow)).all()
            assert len(leases) == 1 and json.loads(leases[0].lease_key)["source"] == "sheets"
            assert session.get(ProjectOperationRow, rejected.operation_id) is None
        assert first.transport.changes() == 0  # Local creation does not pretend remote row append exists.


def test_new_source_scan_does_not_require_every_binding_to_pull_again(tmp_path):
    from autoflow.infrastructure.database.project_claims import (
        SqlAlchemyProjectInputGroups,
    )
    from tests.integration.test_project_sheets_claims import plan_for
    from tests.integration.test_project_sheets_sync import pull
    with shared_tables(tmp_path) as (first, second):
        first.transport.grid("数据").append(["B-2", "new remote row", "note"])
        pull(first)
        factory = first.client.app.state.session_factory
        with factory() as session:
            assert SqlAlchemyProjectInputGroups(session).select_required(second.project, plan_for(second)).status == "ready"
        # A newer scan can nevertheless prove the old local A-1 is now absent.
        first.transport.grid("数据").pop(1)
        pull(first)
        with factory() as session:
            assert SqlAlchemyProjectInputGroups(session).select_required(second.project, plan_for(second)).status == "configurationError"


def test_unbinding_a_peer_cannot_erase_its_bad_source_observation(tmp_path):
    from autoflow.infrastructure.database.project_claims import (
        SqlAlchemyProjectInputGroups,
    )
    from tests.fixtures.sheets import unbind_impact
    from tests.integration.test_project_sheets_claims import plan_for
    with shared_tables(tmp_path) as (first, second):
        first.transport.grid("数据").append(["A-1", "duplicate", "note"])
        second.client.post(second.url("/sync/pull"), json={"expectedTableRevision": second.table_revision()}, headers=new_key())
        response = second.client.request("DELETE", second.url("/sheets/binding"), json={
            "expectedTableRevision": second.table_revision(),
            "impactRevision": unbind_impact(second.client, second.project, second.table),
        }, headers=new_key())
        assert response.status_code == 202, response.text
        with first.client.app.state.session_factory() as session:
            assert SqlAlchemyProjectInputGroups(session).select_required(first.project, plan_for(first)).status == "configurationError"


def test_different_identity_columns_allow_binding_and_local_reads_but_not_claims(tmp_path):
    from autoflow.infrastructure.database.project_claims import (
        SqlAlchemyProjectInputGroups,
    )
    from tests.integration.test_project_sheets_claims import plan_for
    with shared_tables(tmp_path, identity_column="B") as (first, second):
        assert len(first.records()) == len(second.records()) == 1
        assert first.records()[0]["ref"]["recordKey"] != second.records()[0]["ref"]["recordKey"]
        with first.client.app.state.session_factory() as session:
            for bound in (first, second):
                result = SqlAlchemyProjectInputGroups(session).select_required(bound.project, plan_for(bound))
                assert result.status == "configurationError"
                assert "身份列" in str(result.issue_details)
            assert not session.scalars(select(ProjectRecordLeaseRow)).all()
