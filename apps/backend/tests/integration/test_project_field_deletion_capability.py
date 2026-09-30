"""Explicit schema deletion uses the shared candidate and impact transaction."""
from dataclasses import replace

import pytest
from sqlalchemy import func, select

from autoflow.domain.project_data import capabilities as commands
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_capability_fencing import (  # noqa: F401
    _service,
    capability_context,
)
from tests.integration.test_project_run_data_start import uid


def deletion_context(context):
    factory, project, task, table, field, _record = context
    service = _service(factory)
    grant = {'tableId': table['tableId'], 'datasetGeneration': table['datasetGeneration'], 'operations': ['deleteField'], 'fieldIds': [field['ref']['fieldId']], 'readPurposes': []}
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.capability_bindings = [{**binding, 'tableGrants': [grant]} for binding in run.capability_bindings]
    scope = service.scope(project, task.task_id, task.run_id)
    request = commands.PreviewProjectFieldDeletionRequest(1, project, table['tableId'], table['datasetGeneration'], field['ref']['fieldId'])
    return service, scope, request


def deletion_command(request, impact, **changes):
    return commands.DeleteProjectFieldCommand(uid(), request.execution_generation, request.project_id, request.table_id, request.dataset_generation, request.field_id, changes.get('expected_table_revision', 2), impact['impactRevision'])


def test_delete_field_keeps_original_command_and_other_record_facts(capability_context):  # noqa: F811
    factory, _, _, _table, field, record = capability_context
    service, scope, request = deletion_context(capability_context)
    preview = service.preview_field_deletion(scope, request)
    assert preview['blockers'] == []
    assert preview['affectedRecords'] == 1
    command = deletion_command(request, preview)
    result, replayed = service.delete_field(scope, command)
    assert result['deleted'] and result['fieldRef'] == field['ref'] and result['tableRevision'] == 3
    assert not replayed
    assert service.delete_field(scope, command) == (result, True)
    with pytest.raises(ProjectError) as mismatch:
        service.delete_field(scope, replace(command, expected_table_revision=3))
    assert mismatch.value.code == 'OPERATION_PAYLOAD_MISMATCH'
    with factory() as session:
        assert session.get(DataFieldRow, (request.field_id, request.dataset_generation)) is None
        row = session.get(DataRecordRow, (request.dataset_generation, record['ref']['recordKey']['type'], record['ref']['recordKey']['value']))
        assert row.values_json == {} and row.content_revision == 2
        assert row.status_revision == record['statusRevision'] and row.link_revision == record['linkRevision']
        assert session.scalar(select(func.count()).select_from(ProjectOperationRow).where(ProjectOperationRow.idempotency_key == command.operation_id)) == 1
    with pytest.raises(ProjectError): service.preview_field_deletion(scope, request)


@pytest.mark.parametrize('dependency', ['identity', 'own-read', 'foreign-task', 'automation', 'stale-table', 'generation', 'cancelled'])
def test_delete_field_rechecks_dependencies_after_preview(capability_context, dependency):  # noqa: F811
    factory, project, task, table, field, record = capability_context
    service, scope, request = deletion_context(capability_context)
    preview = service.preview_field_deletion(scope, request)
    assert not preview['blockers']
    if dependency == 'foreign-task':
        from autoflow.infrastructure.database.project_automations import (
            SqlAlchemyProjectAutomations,
        )
        from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
        from tests.integration.test_project_capability_field_impacts import (
            _activate_task,
        )
        with factory() as session:
            automation_id = session.get(ProjectBatchRow, task.batch_id).automation_id
        automation = SqlAlchemyProjectAutomations(factory).get(project, automation_id)
        _activate_task(factory, project, automation, [{'tableId': table['tableId'], 'datasetGeneration': table['datasetGeneration'], 'operations': ['readRecord'], 'fieldIds': [request.field_id], 'readPurposes': ['workflow']}])
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        target = session.get(DataTableRow, table['tableId'])
        if dependency == 'identity': target.identity = {'mode': 'field', 'fieldId': request.field_id}
        elif dependency == 'own-read':
            # An extra frozen read declaration in the same Task must not be
            # exempted merely because its delete declaration is exempted.
            run.capability_bindings = [{**binding, 'tableGrants': [*binding['tableGrants'], {**binding['tableGrants'][0], 'operations': ['readRecord']}]} for binding in run.capability_bindings]
        elif dependency == 'automation':
            from autoflow.infrastructure.database.project_automation_models import (
                ProjectAutomationRow,
            )
            from tests.integration.test_project_run_data_start import _input
            automation = session.scalars(select(ProjectAutomationRow).where(ProjectAutomationRow.project_id == project)).first()
            automation.input_plan = {'inputs': [_input(project, table, field, '后续输入')]}
        elif dependency == 'stale-table': target.table_revision += 1
        elif dependency == 'generation': request = replace(request, dataset_generation=uid())
        elif dependency == 'cancelled': run.status = 'cancelled'
    with pytest.raises(ProjectError) as conflict: service.delete_field(scope, deletion_command(request, preview))
    codes = {'identity': 'IDENTITY_FIELD_PROTECTED', 'own-read': 'ACTIVE_TASK_FIELD_DEPENDENCY', 'foreign-task': 'ACTIVE_TASK_FIELD_DEPENDENCY', 'automation': 'AUTOMATION_FIELD_DEPENDENCY'}
    if dependency in codes:
        assert codes[dependency] in {blocker['code'] for blocker in conflict.value.details['blockers']}
    with factory() as session:
        assert session.get(DataFieldRow, (field['ref']['fieldId'], table['datasetGeneration'])) is not None
        row = session.get(DataRecordRow, (table['datasetGeneration'], record['ref']['recordKey']['type'], record['ref']['recordKey']['value']))
        assert row.values_json == {field['ref']['fieldId']: 'original'} and row.content_revision == 1


def test_deleted_field_identity_cannot_be_created_again(capability_context):  # noqa: F811
    factory, project, _task, table, _field, _ = capability_context
    service, scope, request = deletion_context(capability_context)
    preview = service.preview_field_deletion(scope, request)
    service.delete_field(scope, deletion_command(request, preview))
    grant = commands.TableCapabilityGrant(table['tableId'], table['datasetGeneration'], frozenset({'addField'}))
    scope = replace(scope, table_grants=frozenset({grant}))
    command = commands.AddProjectFieldCommand(uid(), 1, project, table['tableId'], table['datasetGeneration'], request.field_id,
        {'key': 'replacement', 'name': '替换', 'type': 'string', 'required': False, 'validation': {}}, False, None, 3)
    with pytest.raises(ProjectError) as retired: service.add_field(scope, command)
    assert retired.value.code == 'FIELD_ID_RETIRED'
    with factory() as session: assert session.get(DataFieldRow, (request.field_id, request.dataset_generation)) is None


def test_source_mapping_and_unsent_intent_block_field_deletion(tmp_path):
    from autoflow.domain.project_data.identity import RecordKey
    from autoflow.infrastructure.database.project_sync import enqueue_intent
    from tests.integration.test_project_sheets_claim_paths import query_task
    from tests.integration.test_project_sheets_claims import shared_tables

    with shared_tables(tmp_path) as (first, _second):
        scope, service = query_task(first)
        field_id = first.field_id('title')
        factory = first.client.app.state.session_factory
        grant = commands.TableCapabilityGrant(first.table, first.dataset_generation(), frozenset({'deleteField'}), frozenset({field_id}))
        scope = replace(scope, table_grants=frozenset({grant}))
        with factory.begin() as session:
            run = session.get(WorkflowRunRow, scope.run_id)
            run.capability_bindings = [{**binding, 'tableGrants': [{'tableId': first.table, 'datasetGeneration': first.dataset_generation(), 'operations': ['deleteField'], 'fieldIds': [field_id], 'readPurposes': []}]} for binding in run.capability_bindings]
            table = session.get(DataTableRow, first.table)
            record = first.records()[0]
            enqueue_intent(session, table, RecordKey(**record['ref']['recordKey']), record['contentRevision'], {field_id: 'pending'})
        request = commands.PreviewProjectFieldDeletionRequest(1, first.project, first.table, first.dataset_generation(), field_id)
        preview = service.preview_field_deletion(scope, request)
        assert {'SOURCE_FIELD_MAPPING', 'PENDING_SYNC_FIELD_DEPENDENCY'} <= {b['code'] for b in preview['blockers']}
        with pytest.raises(ProjectError): service.delete_field(scope, deletion_command(request, preview, expected_table_revision=first.table_revision()))
        assert first.transport.changes() == 0


@pytest.mark.parametrize('human_edit', [False, True])
def test_field_deletion_advances_only_a_current_owned_record_cursor(capability_context, human_edit):  # noqa: F811
    from autoflow.application.project_data.catalog import DataCatalogService
    from autoflow.infrastructure.database.project_claims import _parse_record_ref
    from autoflow.infrastructure.database.project_data_catalog import (
        SqlAlchemyProjectDataCatalog,
    )
    from autoflow.infrastructure.database.project_run_models import (
        ProjectTaskRecordCursorRow,
    )

    factory, project, _task, table, _field, record = capability_context
    service, scope, request = deletion_context(capability_context)
    keep = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(project, table['tableId'], uid(), {
        'definition': {'key': 'keep', 'name': '保留值', 'type': 'string', 'required': False, 'validation': {}},
        'sourceColumnPolicy': 'localOnly', 'expectedTableRevision': 2,
    })[0]['field']['ref']['fieldId']
    scope = replace(scope, table_grants=scope.table_grants | frozenset({commands.TableCapabilityGrant(
        table['tableId'], table['datasetGeneration'], frozenset({'queryRecords', 'updateRecord'}), frozenset({keep}), frozenset({'workflow'})
    )}))
    query = commands.QueryProjectRecordsRequest(1, project, table['tableId'], table['datasetGeneration'], [keep], 'workflow', None, [], None, 10)
    row = service.query_records(scope, query)['items'][0]
    ref = _parse_record_ref(record['ref'])
    service.update_record(scope, commands.UpdateProjectRecordCommand(uid(), 1, ref, {keep: 'task value'}, row['contentRevision']))
    if human_edit:
        with factory.begin() as session:
            current = session.get(DataRecordRow, (table['datasetGeneration'], record['ref']['recordKey']['type'], record['ref']['recordKey']['value']))
            current.values_json = {**current.values_json, keep: 'human value'}
            current.content_revision += 1
    preview = service.preview_field_deletion(scope, request)
    assert not preview['blockers']
    service.delete_field(scope, deletion_command(request, preview, expected_table_revision=3))
    with factory() as session:
        cursor = session.scalar(select(ProjectTaskRecordCursorRow).where(ProjectTaskRecordCursorRow.task_id == scope.task_id, ProjectTaskRecordCursorRow.record_ref == record['ref']))
        assert cursor.content_revision == (2 if human_edit else 3)
    current = service.query_records(scope, query)['items'][0]
    command = commands.UpdateProjectRecordCommand(uid(), 1, ref, {keep: 'next task value'}, current['contentRevision'])
    if human_edit:
        with pytest.raises(ProjectError): service.update_record(scope, command)
        assert current['values'][0]['value'] == 'human value'
    else:
        assert service.update_record(scope, command)[0]['values'][0]['value'] == 'next task value'


def test_delete_local_only_field_keeps_same_named_remote_column(tmp_path):
    from copy import deepcopy

    from tests.fixtures.sheets import (
        FakeSheetsTransport,
        new_field,
        new_key,
        open_sheets_table,
    )
    from tests.integration.test_project_sheets_claim_paths import query_task
    from tests.integration.test_project_sheets_columns import edit_note
    from tests.integration.test_project_sheets_sync import (
        COLUMNS,
        pull,
        sync_operations,
    )

    transport = FakeSheetsTransport({'数据':[['编号','标题','备注'],['A-1','original','source-owned']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        field = new_field(sheets.client, sheets.project, sheets.table, 'note', '备注', expectedTableRevision=sheets.table_revision())
        before = edit_note(sheets, field, sheets.records()[0], 'local-only')
        remote = deepcopy(transport.grid('数据'))
        scope, service = query_task(sheets)
        field_id = field['ref']['fieldId']
        grant = {'tableId':sheets.table, 'datasetGeneration':sheets.dataset_generation(), 'operations':['deleteField'], 'fieldIds':[field_id], 'readPurposes':[]}
        with sheets.client.app.state.session_factory.begin() as session:
            run = session.get(WorkflowRunRow, scope.run_id)
            run.capability_bindings = [{**binding, 'tableGrants':[grant]} for binding in run.capability_bindings]
        scope = replace(scope, table_grants=frozenset({commands.TableCapabilityGrant(sheets.table, sheets.dataset_generation(), frozenset({'deleteField'}), frozenset({field_id}))}))
        request = commands.PreviewProjectFieldDeletionRequest(1,sheets.project,sheets.table,sheets.dataset_generation(),field_id)
        impact = service.preview_field_deletion(scope, request)
        assert 'PENDING_SYNC_FIELD_DEPENDENCY' in {item['code'] for item in impact['blockers']}
        pending, = sync_operations(sheets, 'pending')
        abandoned = sheets.client.post(sheets.url('/sync-operations/'+pending['syncOperationId']+'/abandon'), headers=new_key(), json={'expectedStatusRevision':pending['statusRevision'], 'reason':'keep source column, remove only local field'})
        assert abandoned.status_code == 200, abandoned.text
        impact = service.preview_field_deletion(scope, request)
        assert impact['blockers'] == []
        result, replayed = service.delete_field(scope, deletion_command(request, impact, expected_table_revision=sheets.table_revision()))
        assert result['deleted'] and not replayed
        after = sheets.records()[0]
        assert all(cell['fieldId'] != field_id for cell in after['values'])
        assert after['statusRevision'] == before['statusRevision'] and after['linkRevision'] == before['linkRevision']
        assert transport.grid('数据') == remote and transport.changes() == 0
