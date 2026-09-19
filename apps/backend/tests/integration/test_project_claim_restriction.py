"""PM7-C1: a follow-up batch may only claim the records it was pinned to."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.projects.service import ProjectService
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_claims import (
    SqlAlchemyProjectInputGroups,
    _parse_record_ref,
)
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from tests.integration.test_project_run_data_start import _setup


def uid() -> str:
    return str(uuid4())


def _table_with_records(factory, project_id: str, name: str, *values: str):
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, uid(), {"name": name}
    )[0]
    field = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
        project_id,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "value",
                "name": "值",
                "type": "string",
                "required": True,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    records = [
        DataRecordService(SqlAlchemyProjectDataRecords(factory)).create(
            project_id,
            table["tableId"],
            uid(),
            {
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field["ref"]["fieldId"], "value": value}],
            },
        )[0]
        for value in values
    ]
    return table, field, records


def _input(project_id: str, table: dict, field: dict, alias: str, **overrides) -> dict:
    item = {
        "inputId": uid(),
        "alias": alias,
        "tableId": table["tableId"],
        "datasetGeneration": table["datasetGeneration"],
        "mode": "independent",
        "required": True,
        "fieldBindings": [
            {
                "inputFieldId": uid(),
                "inputFieldAlias": "值",
                "fieldRef": {
                    "projectId": project_id,
                    "tableId": table["tableId"],
                    "datasetGeneration": table["datasetGeneration"],
                    "fieldId": field["ref"]["fieldId"],
                },
            }
        ],
        "filter": {"type": "all", "items": []},
        "orderBy": [{"systemField": "recordKey", "direction": "asc"}],
    }
    item.update(overrides)
    return item


def _project(factory) -> str:
    return (
        ProjectService(SqlAlchemyProjects(factory))
        .create(uid(), {"name": "PM7"})[0]
        .project_id
    )


def _ref_of(project_id: str, table: dict, record: dict) -> RecordRef:
    key = record["ref"]["recordKey"]
    return RecordRef(
        project_id,
        table["tableId"],
        table["datasetGeneration"],
        RecordKey(key["type"], key["value"]),
    )


def test_without_restriction_selection_is_unchanged(tmp_path):
    path = tmp_path / "no-restriction.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = _project(factory)
    table, field, records = _table_with_records(factory, project_id, "人员", "甲", "乙")
    plan = {"inputs": [_input(project_id, table, field, "人员")]}

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(project_id, plan)

    assert result.status == "ready"
    selected = result.inputs[0].record_ref.record_key.value
    assert selected in {record["ref"]["recordKey"]["value"] for record in records}
    factory.dispose()


def test_restriction_narrows_to_the_pinned_record(tmp_path):
    path = tmp_path / "pinned.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = _project(factory)
    table, field, records = _table_with_records(factory, project_id, "人员", "甲", "乙")
    plan = {"inputs": [_input(project_id, table, field, "人员")]}
    pinned = _ref_of(project_id, table, records[1])

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, plan, candidate_restriction={plan["inputs"][0]["inputId"]: [pinned]}
        )

    assert result.status == "ready"
    assert [item.record_ref.record_key.value for item in result.inputs] == [
        records[1]["ref"]["recordKey"]["value"]
    ]
    factory.dispose()


def test_busy_pinned_record_does_not_fall_back_to_other_records(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    batch, _operation, _replayed = coordinator.start(
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
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id)
        == "ready"
    )
    with factory() as session:
        row = session.get(ProjectAutomationRow, automation.automation_id)
        assert row is not None
        inputs = row.input_plan["inputs"]
        leases = list(
            session.scalars(
                select(ProjectRecordLeaseRow).where(
                    ProjectRecordLeaseRow.project_id == project_id
                )
            )
        )
    assert len(leases) == len(inputs) == 2
    by_table = {
        lease.record_ref["tableId"]: _parse_record_ref(lease.record_ref)
        for lease in leases
    }
    restriction = {item["inputId"]: [by_table[item["tableId"]]] for item in inputs}

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id,
            {"inputs": inputs},
            candidate_restriction=restriction,
        )

    assert result.status == "temporarilyBusy"
    assert result.inputs == ()
    factory.dispose()


def test_pinned_record_that_no_longer_matches_is_no_match(tmp_path):
    path = tmp_path / "stale-match.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = _project(factory)
    table, field, records = _table_with_records(factory, project_id, "人员", "甲", "乙")
    input_id = uid()
    filtered = _input(
        project_id,
        table,
        field,
        "人员",
        inputId=input_id,
        filter={
            "type": "all",
            "items": [
                {
                    "type": "compare",
                    "fieldId": field["ref"]["fieldId"],
                    "operator": "eq",
                    "value": "丙",
                }
            ],
        },
    )
    plan = {"inputs": [filtered]}
    pinned = _ref_of(project_id, table, records[0])

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, plan, candidate_restriction={input_id: [pinned]}
        )

    assert result.status == "noMatch"
    assert result.inputs == ()
    factory.dispose()


def test_deleted_pinned_record_is_no_match_without_raising(tmp_path):
    path = tmp_path / "deleted.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = _project(factory)
    table, field, records = _table_with_records(factory, project_id, "人员", "甲", "乙")
    input_id = uid()
    plan = {"inputs": [_input(project_id, table, field, "人员", inputId=input_id)]}
    pinned = _ref_of(project_id, table, records[1])
    # Same persisted state the record-deletion service writes; that transition
    # itself is covered by tests/integration/test_project_data_deletions.py.
    with factory() as session:
        row = session.get(
            DataRecordRow,
            (
                table["datasetGeneration"],
                records[1]["ref"]["recordKey"]["type"],
                records[1]["ref"]["recordKey"]["value"],
            ),
        )
        assert row is not None
        row.deleted = True
        session.commit()

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, plan, candidate_restriction={input_id: [pinned]}
        )

    assert result.status == "noMatch"
    assert result.inputs == ()
    factory.dispose()


def test_empty_restriction_returns_nothing(tmp_path):
    path = tmp_path / "empty-restriction.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = _project(factory)
    table, field, _records = _table_with_records(factory, project_id, "人员", "甲", "乙")
    input_id = uid()
    plan = {"inputs": [_input(project_id, table, field, "人员", inputId=input_id)]}

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, plan, candidate_restriction={input_id: []}
        )

    assert result.status == "noMatch"
    assert result.inputs == ()
    factory.dispose()
