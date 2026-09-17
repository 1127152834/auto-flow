from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from autoflow.application.project_data.tables import DataTableService
from autoflow.domain.project_data.capabilities import (
    AddProjectFieldCommand,
    DeleteProjectRecordCommand,
    PreviewProjectFieldChangeRequest,
    TableCapabilityGrant,
    TaskCapabilityScope,
)
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataFieldRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from tests.integration.test_project_capability_query_snapshot import (
    _context,
    _query,
)
from tests.integration.test_project_run_data_start import uid


def _scope_with_grants(base_scope, grants):
    return TaskCapabilityScope(
        base_scope.project_id,
        base_scope.task_id,
        base_scope.run_id,
        base_scope.execution_generation,
        frozenset(),
        frozenset(),
        table_grants=frozenset(grants),
    )


def _grant(table, operations, field_ids=()):
    return TableCapabilityGrant(
        table["tableId"],
        table["datasetGeneration"],
        frozenset(operations),
        frozenset(field_ids),
        frozenset({"workflow"}),
    )


def _required_definition(key="required"):
    return {
        "key": key,
        "name": "必填字段",
        "type": "string",
        "required": True,
        "validation": {},
    }


def test_created_field_evidence_cannot_authorize_same_field_id_in_another_table(
    tmp_path,
):
    (
        factory,
        project_id,
        _automation,
        _grant_payload,
        first_table,
        _first_field,
        _created,
        _task,
        base_scope,
        service,
    ) = _context(tmp_path)
    try:
        second_table = DataTableService(SqlAlchemyProjectData(factory)).create(
            project_id, uid(), {"name": "第二张表"}
        )[0]
        shared_field_id = uid()
        scope = _scope_with_grants(
            base_scope,
            {
                _grant(first_table, {"addField"}),
                _grant(second_table, {"modifyField"}),
            },
        )
        service.add_field(
            scope,
            AddProjectFieldCommand(
                uid(),
                1,
                project_id,
                first_table["tableId"],
                first_table["datasetGeneration"],
                shared_field_id,
                {
                    "key": "created_here",
                    "name": "本表创建",
                    "type": "string",
                    "required": False,
                    "validation": {},
                },
                False,
                None,
                2,
            ),
        )
        with factory.begin() as session:
            second_row = session.get(DataTableRow, second_table["tableId"])
            assert second_row is not None
            session.add(
                DataFieldRow(
                    id=shared_field_id,
                    project_id=project_id,
                    table_id=second_table["tableId"],
                    dataset_generation=second_table["datasetGeneration"],
                    key="foreign",
                    name="另一张表",
                    type="string",
                    required=False,
                    writable=True,
                    formula=False,
                    validation={},
                    field_revision=1,
                    position=0,
                )
            )
            second_row.table_revision = 2

        with pytest.raises(ProjectError) as denied:
            service.preview_field_change(
                scope,
                PreviewProjectFieldChangeRequest(
                    1,
                    project_id,
                    second_table["tableId"],
                    second_table["datasetGeneration"],
                    shared_field_id,
                    {
                        "key": "foreign",
                        "name": "不得借用另一表证据",
                        "type": "string",
                        "required": False,
                        "validation": {},
                    },
                ),
            )

        assert denied.value.code == "CAPABILITY_SCOPE_DENIED"
    finally:
        factory.dispose()


def test_workflow_delete_rejects_inbound_reference_without_partial_facts(tmp_path):
    (
        factory,
        project_id,
        _automation,
        _grant_payload,
        table,
        field,
        created,
        task,
        base_scope,
        service,
    ) = _context(tmp_path)
    try:
        scope = _scope_with_grants(
            base_scope,
            {
                _grant(
                    table,
                    {"queryRecords", "deleteRecord"},
                    {field["ref"]["fieldId"]},
                )
            },
        )
        selected = service.query_records(
            scope, _query(project_id, table, field, limit=1)
        )["items"][0]
        source = next(
            item
            for item in created
            if item["ref"]["recordKey"] != selected["ref"]["recordKey"]
        )
        with factory.begin() as session:
            source_row = session.get(
                DataRecordRow,
                (
                    table["datasetGeneration"],
                    source["ref"]["recordKey"]["type"],
                    source["ref"]["recordKey"]["value"],
                ),
            )
            assert source_row is not None
            source_row.record_slots = [{"slotId": uid(), "target": selected["ref"]}]
        target_ref = selected["ref"]
        command = DeleteProjectRecordCommand(
            uid(),
            1,
            RecordRef(
                project_id,
                target_ref["tableId"],
                target_ref["datasetGeneration"],
                RecordKey(
                    target_ref["recordKey"]["type"],
                    target_ref["recordKey"]["value"],
                ),
            ),
            selected["contentRevision"],
            selected["statusRevision"],
            selected["linkRevision"],
        )

        with pytest.raises(ProjectError) as blocked:
            service.delete_record(scope, command)

        assert blocked.value.code == "RECORD_REFERENCED"
        with factory() as session:
            target = session.get(
                DataRecordRow,
                (
                    table["datasetGeneration"],
                    target_ref["recordKey"]["type"],
                    target_ref["recordKey"]["value"],
                ),
            )
            assert target is not None and target.deleted is False
            assert session.get(ProjectOperationRow, command.operation_id) is None
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(DataChangeRow)
                    .where(DataChangeRow.operation_id == command.operation_id)
                )
                == 0
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ProjectRecordLeaseRow)
                    .where(
                        ProjectRecordLeaseRow.task_id == task.id,
                        ProjectRecordLeaseRow.record_ref["tableId"].as_string()
                        == table["tableId"],
                        ProjectRecordLeaseRow.record_ref["recordKey"][
                            "value"
                        ].as_string()
                        == target_ref["recordKey"]["value"],
                    )
                )
                == 0
            )
    finally:
        factory.dispose()


@pytest.mark.parametrize("budget", ["recordCount", "snapshotBytes"])
def test_required_field_default_rejects_backfill_over_budget_without_partial_facts(
    tmp_path, budget
):
    (
        factory,
        project_id,
        _automation,
        _grant_payload,
        table,
        field,
        _created,
        _task,
        base_scope,
        service,
    ) = _context(tmp_path)
    operation_id, new_field_id = uid(), uid()
    try:
        if budget == "recordCount":
            now = datetime.now(UTC)
            with factory.begin() as session:
                session.add_all(
                    DataRecordRow(
                        project_id=project_id,
                        table_id=table["tableId"],
                        dataset_generation=table["datasetGeneration"],
                        key_type="text",
                        key_value=f"backfill-{index:04d}",
                        values_json={field["ref"]["fieldId"]: "value"},
                        record_slots=[],
                        status_id=None,
                        current_environment_id=None,
                        content_revision=1,
                        status_revision=1,
                        link_revision=1,
                        deleted=False,
                        created_at=now,
                        updated_at=now,
                    )
                    for index in range(997)
                )
        else:
            with factory.begin() as session:
                row = session.scalar(
                    select(DataRecordRow).where(
                        DataRecordRow.dataset_generation == table["datasetGeneration"]
                    )
                )
                assert row is not None
                row.values_json = {
                    field["ref"]["fieldId"]: "界" * (4 * 1024 * 1024 // 3 + 1)
                }
        scope = _scope_with_grants(base_scope, {_grant(table, {"addField"})})
        command = AddProjectFieldCommand(
            operation_id,
            1,
            project_id,
            table["tableId"],
            table["datasetGeneration"],
            new_field_id,
            _required_definition(f"required_{budget}"),
            True,
            "default",
            2,
        )

        with pytest.raises(ProjectError) as limited:
            service.add_field(scope, command)

        assert limited.value.code == "SCHEMA_BACKFILL_LIMIT"
        with factory() as session:
            table_row = session.get(DataTableRow, table["tableId"])
            assert table_row is not None and table_row.table_revision == 2
            assert (
                session.get(DataFieldRow, (new_field_id, table["datasetGeneration"]))
                is None
            )
            assert session.get(ProjectOperationRow, operation_id) is None
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(DataChangeRow)
                    .where(DataChangeRow.operation_id == operation_id)
                )
                == 0
            )
            assert all(
                new_field_id not in values
                for values in session.scalars(
                    select(DataRecordRow.values_json).where(
                        DataRecordRow.dataset_generation == table["datasetGeneration"]
                    )
                )
            )
    finally:
        factory.dispose()
