"""R1 reads current schema without granting record or mutation authority."""
from dataclasses import replace

import pytest
from sqlalchemy import func, select

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.domain.project_data import capabilities as commands
from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskRecordReadRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_capability_fencing import (  # noqa: F401
    _record_ref,
    _scope,
    _service,
    capability_context,
)
from tests.integration.test_project_run_data_start import uid


def schema_request(context):
    factory, project, task, table, field, _ = context
    service = _service(factory)
    grant = commands.TableCapabilityGrant(table['tableId'], table['datasetGeneration'], frozenset({'queryTableSchema'}), frozenset({field['ref']['fieldId']}))
    scope = replace(service.scope(project, task.task_id, task.run_id), table_grants=frozenset({grant}), create_record_targets=frozenset())
    request = commands.QueryProjectTableSchemaRequest(1, project, table['tableId'], table['datasetGeneration'], [field['ref']['fieldId']])
    return service, scope, request


def facts(factory):
    with factory() as session:
        return ([(r.id, r.table_revision) for r in session.scalars(select(DataTableRow))],
                [(r.key_value, r.content_revision, r.status_revision) for r in session.scalars(select(DataRecordRow))],
                [session.scalar(select(func.count()).select_from(model)) for model in (ProjectRecordLeaseRow, ProjectTaskRecordReadRow, ProjectOperationRow)])


def test_schema_query_is_explicit_current_and_read_only(capability_context):  # noqa: F811
    factory, _, _, table, field, _ = capability_context
    service, scope, request = schema_request(capability_context)
    before = facts(factory)
    result = service.query_table_schema(scope, request)
    assert result == service.query_table_schema(scope, request)
    assert result == {
        'projectId': scope.project_id, 'tableId': table['tableId'], 'datasetGeneration': table['datasetGeneration'],
        'tableRevision': 2,
        'fields': [{'fieldId': field['ref']['fieldId'], 'key': 'value', 'name': '值', 'type': 'string', 'required': True, 'writable': True, 'formula': False, 'sourceColumn': None}],
        'systemProperties': {'statusId': {'type': 'status', 'nullable': True, 'writable': False}},
    }
    assert facts(factory) == before
    # Current metadata may advance within the same permitted field identity.
    with factory.begin() as session:
        row = session.get(DataFieldRow, (field['ref']['fieldId'], table['datasetGeneration']))
        row.name = '当前名称'
        row.formula = True
        row.writable = False
        session.get(DataTableRow, table['tableId']).table_revision += 1
    latest = service.query_table_schema(scope, request)
    assert latest['tableRevision'] == 3 and latest['fields'][0]['name'] == '当前名称'
    assert latest['fields'][0]['formula'] and not latest['fields'][0]['writable']


@pytest.mark.parametrize('fault', ['empty', 'duplicate', 'grant', 'project', 'table', 'generation', 'field', 'missing-field', 'stale-binding', 'revoked', 'finished', 'inactive'])
def test_schema_query_rejects_invalid_or_ungranted_target_without_effects(capability_context, fault):  # noqa: F811
    factory, _, task, table, field, _ = capability_context
    service, scope, request = schema_request(capability_context)
    if fault == 'missing-field':
        with factory.begin() as session:
            session.delete(session.get(DataFieldRow, (field['ref']['fieldId'], table['datasetGeneration'])))
    if fault == 'finished':
        with factory.begin() as session: session.get(WorkflowRunRow, task.run_id).status = 'cancelled'
    if fault == 'inactive':
        with factory.begin() as session: session.get(ProjectRow, scope.project_id).lifecycle_state = 'archived'
    before = facts(factory)
    with pytest.raises(ProjectError):
        if fault == 'empty': request = replace(request, field_ids=[])
        elif fault == 'duplicate': request = replace(request, field_ids=list(request.field_ids) * 2)
        elif fault == 'grant': scope = replace(scope, table_grants=frozenset())
        elif fault == 'project': request = replace(request, project_id=uid())
        elif fault == 'table': request = replace(request, table_id=uid())
        elif fault == 'generation': request = replace(request, dataset_generation=uid())
        elif fault == 'field': request = replace(request, field_ids=[uid()])
        elif fault == 'stale-binding':
            request = replace(request, dataset_generation=uid())
            scope = replace(scope, table_grants=frozenset({replace(next(iter(scope.table_grants)), dataset_generation=request.dataset_generation)}))
        elif fault == 'revoked': request = replace(request, execution_generation=2)
        service.query_table_schema(scope, request)
    assert facts(factory) == before


def test_schema_query_returns_only_selected_source_metadata_and_no_write_grant(tmp_path):
    from autoflow.infrastructure.database.project_claims import _parse_record_ref
    from tests.integration.test_project_sheets_claim_paths import query_task
    from tests.integration.test_project_sheets_claims import shared_tables

    with shared_tables(tmp_path) as (first, _second):
        scope, service = query_task(first)
        field_id = first.field_id('title')
        scope = replace(scope, table_grants=frozenset({commands.TableCapabilityGrant(
            first.table, first.dataset_generation(), frozenset({'queryTableSchema'}), frozenset({field_id})
        )}), create_record_targets=frozenset())
        request = commands.QueryProjectTableSchemaRequest(1, first.project, first.table, first.dataset_generation(), [field_id])
        before = facts(first.client.app.state.session_factory)
        result = service.query_table_schema(scope, request)
        assert len(result['fields']) == 1
        assert result['fields'][0]['sourceColumn'] == {'columnId': 'B', 'direction': 'both'}
        assert result['fields'][0]['fieldId'] == field_id
        record = first.records()[0]
        with pytest.raises(ProjectError) as denied:
            service.update_record(scope, commands.UpdateProjectRecordCommand(uid(), 1, _parse_record_ref(record['ref']), {field_id: 'not permitted'}, 1))
        assert denied.value.code == 'CAPABILITY_SCOPE_DENIED'
        assert facts(first.client.app.state.session_factory) == before
        assert first.transport.changes() == 0


def test_system_status_is_read_only_while_business_status_field_and_status_write_coexist(capability_context):  # noqa: F811
    factory, project, task, table, field, record = capability_context
    service = _service(factory)
    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    business_field = catalog.create_field(
        project,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "status",
                "name": "业务状态",
                "type": "string",
                "required": False,
                "validation": {},
            },
            "expectedTableRevision": 2,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    business_status = catalog.create_status(
        project,
        table["tableId"],
        uid(),
        {
            "name": "已处理",
            "color": "#2f855a",
            "order": 1,
            "expectedTableRevision": 3,
        },
    )[0]["status"]

    schema_scope = replace(
        service.scope(project, task.task_id, task.run_id),
        table_grants=frozenset(
            {
                commands.TableCapabilityGrant(
                    table["tableId"],
                    table["datasetGeneration"],
                    frozenset({"queryTableSchema"}),
                    frozenset(
                        {field["ref"]["fieldId"], business_field["ref"]["fieldId"]}
                    ),
                )
            }
        ),
    )
    schema = service.query_table_schema(
        schema_scope,
        commands.QueryProjectTableSchemaRequest(
            1,
            project,
            table["tableId"],
            table["datasetGeneration"],
            [field["ref"]["fieldId"], business_field["ref"]["fieldId"]],
        ),
    )
    assert {item["key"] for item in schema["fields"]} == {"value", "status"}
    assert schema["systemProperties"] == {
        "statusId": {"type": "status", "nullable": True, "writable": False}
    }

    system_definition = {
        "key": "statusId",
        "name": "系统状态",
        "type": "string",
        "required": False,
        "validation": {},
    }
    capability_scope = _scope(project, task, table, field, _record_ref(project, record), 1)
    # Even a field-authorized caller cannot turn a status directory ID into a Field.
    structure_scope = replace(capability_scope, table_grants=frozenset({
        commands.TableCapabilityGrant(table["tableId"], table["datasetGeneration"],
            frozenset({"modifyField", "deleteField"}), frozenset({business_status["statusId"]}))
    }))
    before = facts(factory)
    statuses_before = catalog.statuses(project, table["tableId"])
    modify_op, delete_op = uid(), uid()
    with pytest.raises(ProjectError) as modified_system:
        service.modify_field(
            structure_scope,
            commands.ModifyProjectFieldCommand(
                modify_op,
                1,
                project,
                table["tableId"],
                table["datasetGeneration"],
                business_status["statusId"],
                system_definition,
                4,
                1,
                1,
            ),
        )
    assert modified_system.value.code == "FIELD_NOT_FOUND"
    with pytest.raises(ProjectError) as deleted_system:
        service.delete_field(
            structure_scope,
            commands.DeleteProjectFieldCommand(
                delete_op,
                1,
                project,
                table["tableId"],
                table["datasetGeneration"],
                business_status["statusId"],
                4,
                1,
            ),
        )
    assert deleted_system.value.code == "FIELD_NOT_FOUND"
    assert facts(factory) == before
    assert catalog.statuses(project, table["tableId"]) == statuses_before
    with factory() as session:
        assert session.get(ProjectOperationRow, modify_op) is None
        assert session.get(ProjectOperationRow, delete_op) is None
        assert session.get(DataTableRow, table["tableId"]).table_revision == 4

    ref = record["ref"]
    service.read_record(
        capability_scope,
        commands.ReadProjectRecordRequest(
            1,
            _record_ref(project, record),
            [field["ref"]["fieldId"]],
            "workflow",
        ),
    )
    changed, replayed = service.set_record_status(
        capability_scope,
        commands.SetRecordStatusCommand(
            uid(),
            1,
            RecordRef(
                project,
                ref["tableId"],
                ref["datasetGeneration"],
                RecordKey(ref["recordKey"]["type"], ref["recordKey"]["value"]),
            ),
            business_status["statusId"],
            record["statusRevision"],
        ),
    )
    assert not replayed and changed["statusId"] == business_status["statusId"]
    assert changed["statusRevision"] == record["statusRevision"] + 1
    assert changed["contentRevision"] == record["contentRevision"]
    assert changed["linkRevision"] == record["linkRevision"]
    assert DataRecordService(SqlAlchemyProjectDataRecords(factory)).get(
        project,
        table["tableId"],
        table["datasetGeneration"],
        encode_record_key(
            RecordKey(ref["recordKey"]["type"], ref["recordKey"]["value"])
        ),
        ref["recordKey"]["type"],
    )["statusId"] == business_status["statusId"]


@pytest.mark.parametrize("target", ["statusId", "status-directory-id"])
def test_sheets_binding_cannot_map_system_status(tmp_path, target):
    from copy import deepcopy

    from tests.fixtures.sheets import FakeSheetsTransport, new_key, open_sheets_table
    from tests.integration.test_project_sheets_sync import pull

    transport = FakeSheetsTransport({"数据": [["编号", "status"], ["A-1", "source-value"]]})
    with open_sheets_table(tmp_path, transport, [("code", "编号", "string"), ("status", "业务字段 status", "string")]) as sheets:
        pull(sheets)
        status = sheets.client.post(sheets.url("/statuses"), headers=new_key(), json={
            "name": "已处理", "color": "#2f855a", "order": 1,
            "expectedTableRevision": sheets.table_revision(),
        })
        assert status.status_code == 201, status.text
        status_id = status.json()["statusId"]
        factory = sheets.client.app.state.session_factory
        before = facts(factory)
        records = sheets.records()
        assert next(cell["value"] for cell in records[0]["values"] if cell["fieldId"] == sheets.field_id("status")) == "source-value"
        binding = sheets.client.get(sheets.url("/sheets/binding")).json()
        mapping = deepcopy(binding["mapping"])
        business_mapping = next(item for item in mapping if item["fieldId"] == sheets.field_id("status"))
        business_mapping["fieldId"] = "statusId" if target == "statusId" else status_id
        key = new_key()
        rejected = sheets.client.put(sheets.url("/sheets/binding"), headers=key, json={
            **{name: binding[name] for name in ("connectionId", "spreadsheetId", "sheetId", "identityStrategy")},
            "mapping": mapping, "expectedTableRevision": sheets.table_revision(), "impactRevision": 1,
        })
        assert rejected.status_code == 422, rejected.text
        if target == "status-directory-id":
            assert rejected.json()["error"]["code"] == "SHEETS_MAPPING_UNKNOWN_FIELD"
        assert facts(factory) == before
        assert sheets.records() == records
        assert sheets.client.get(sheets.url("/sheets/binding")).json() == binding
        assert sheets.client.get(f"/api/v1/projects/{sheets.project}/operations/by-idempotency-key/{key['Idempotency-Key']}").status_code == 404
        assert transport.changes() == 0
