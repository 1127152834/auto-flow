"""R1 reads current schema without granting record or mutation authority."""
from dataclasses import replace

import pytest
from sqlalchemy import func, select

from autoflow.domain.project_data import capabilities as commands
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskRecordReadRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_capability_fencing import (  # noqa: F401
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
