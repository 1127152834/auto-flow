"""Explicit source column creation preserves local data and original command ownership."""
from tests.fixtures.sheets import (
    FakeSheetsTransport,
    new_field,
    new_key,
    open_sheets_table,
)
from tests.integration.test_project_sheets_sync import COLUMNS, edit_title, pull, push


def column_body(sheets, field):
    return {"fieldId":field['ref']['fieldId'], 'columnName':'备注', 'datasetGeneration':sheets.dataset_generation(),
            'connectionId':sheets.connection, 'spreadsheetId':sheets.binding['spreadsheetId'], 'sheetId':sheets.binding['sheetId'],
            'expectedBindingEpoch':sheets.binding['bindingEpoch'], 'expectedTableRevision':sheets.table_revision()}


def test_explicit_column_keeps_generation_and_old_patch_then_pushes_new_field(tmp_path):
    transport = FakeSheetsTransport({'数据':[['编号','标题'],['A-1','original']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        old = sheets.records()[0]
        field = new_field(sheets.client, sheets.project, sheets.table, 'note', '备注', expectedTableRevision=sheets.table_revision())
        body = column_body(sheets, field)
        preview = sheets.client.post(sheets.url('/sheets/columns/preview'), json=body)
        assert preview.status_code == 200, preview.text
        key = new_key()
        body['impactRevision'] = preview.json()['impactRevision']
        created = sheets.client.post(sheets.url('/sheets/columns'), headers=key, json=body)
        assert created.status_code == 202, created.text
        assert created.json()['operation']['status'] == 'succeeded'
        mapping = created.json()['operation']['result']['mapping']
        assert mapping[-1]['fieldId'] == field['ref']['fieldId'] and mapping[-1]['columnId'] == 'AA'
        assert sheets.records()[0] == old and sheets.dataset_generation() == old['ref']['datasetGeneration']
        edit_title(sheets, old, 'old patch accepted')
        assert push(sheets).status_code == 202
        assert transport.grid('数据')[1][1] == 'old patch accepted'
        assert transport.grid('数据')[0][26] == '备注'
        writes = transport.changes()
        assert sheets.client.post(sheets.url('/sheets/columns'), headers=key, json=body).json() == created.json()
        assert transport.changes() == writes


def start_column(sheets, field):
    body = column_body(sheets, field)
    preview = sheets.client.post(sheets.url('/sheets/columns/preview'), json=body)
    assert preview.status_code == 200, preview.text
    body['impactRevision'] = preview.json()['impactRevision']
    response = sheets.client.post(sheets.url('/sheets/columns'), headers=new_key(), json=body)
    assert response.status_code == 202, response.text
    return response.json()['operation']


def edit_note(sheets, field, record, value):
    from autoflow.domain.project_data.identity import RecordKey, encode_record_key
    ref = record['ref']
    encoded = encode_record_key(RecordKey(**ref['recordKey']))
    response = sheets.client.patch(sheets.url('/records/'+encoded), headers=new_key(), json={
        'datasetGeneration':ref['datasetGeneration'], 'recordKeyType':ref['recordKey']['type'],
        'expectedContentRevision':record['contentRevision'], 'values':[{'fieldId':field['ref']['fieldId'],'value':value}],
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_lost_column_response_blocks_values_and_recovers_original_mapping(tmp_path, monkeypatch):
    from sqlalchemy import select

    from autoflow.infrastructure.database.project_sync_models import SyncOperationRow
    from autoflow.providers.data.google_sheets import SheetsApiError
    transport = FakeSheetsTransport({'数据':[['编号','标题'],['A-1','original']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        field = new_field(sheets.client, sheets.project, sheets.table, 'note', '备注', expectedTableRevision=sheets.table_revision())
        local = edit_note(sheets, field, sheets.records()[0], 'local before source exists')
        original = transport.send
        def lost(method, url, **kwargs):
            result = original(method, url, **kwargs)
            if url.endswith(':batchUpdate'): raise SheetsApiError(0, 'lost', 'lost')
            return result
        monkeypatch.setattr(transport, 'send', lost)
        operation = start_column(sheets, field)
        assert operation['status'] == 'reconciling'
        operation_url = sheets.url('/sheets/columns/' + operation['operationId'])
        assert sheets.client.get(sheets.url('/sheets/columns')).json()['items'][0]['syncOperationId'] == operation['operationId']
        assert sheets.client.get(sheets.url('/sheets/binding')).json()['mapping'] == sheets.binding['mapping']
        assert push(sheets).status_code == 409
        assert sheets.records()[0] == local
        assert len(transport.grid('数据')[1]) == 2
        status = sheets.client.get(sheets.url('/sheets/columns')).json()['items'][0]
        assert sheets.client.post(operation_url+'/cancel', json={'expectedStatusRevision':status['statusRevision']}).status_code == 409
        recovered = sheets.client.post(operation_url+'/verify')
        assert recovered.status_code == 202 and recovered.json()['operation']['status'] == 'succeeded', recovered.text
        assert sheets.client.post(operation_url+'/verify').json() == recovered.json()
        assert transport.changes() == 1
        with sheets.client.app.state.session_factory() as session:
            pending = session.scalars(select(SyncOperationRow).where(SyncOperationRow.kind=='push',SyncOperationRow.operation_id.is_(None))).all()
            assert any(operation['operationId'] in item.request['columnDependencies'] for item in pending)
        assert push(sheets).status_code == 202
        assert transport.grid('数据')[1][26] == 'local before source exists'
        assert sheets.records()[0] == local
        # An owned header moved or renamed externally cannot redirect a later value write.
        transport.grid('数据')[0][26] = 'foreign'
        edit_note(sheets, field, sheets.records()[0], 'must stay local')
        assert push(sheets).status_code == 409
        assert transport.changes() == 2


def test_unsent_column_can_be_cancelled_without_deleting_local_field_or_value(tmp_path):
    from autoflow.providers.data.google_sheets import SheetsApiError
    transport = FakeSheetsTransport({'数据':[['编号','标题'],['A-1','original']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        field = new_field(sheets.client, sheets.project, sheets.table, 'note', '备注', expectedTableRevision=sheets.table_revision())
        local = edit_note(sheets, field, sheets.records()[0], 'keep me')
        transport.fail_writes = [SheetsApiError(-1, 'notSent', 'not sent')]
        operation = start_column(sheets, field)
        assert operation['status'] == 'failed'
        item = sheets.client.get(sheets.url('/sheets/columns')).json()['items'][0]
        url = sheets.url('/sheets/columns/'+operation['operationId'])
        canceled = sheets.client.post(url+'/cancel', json={'expectedStatusRevision':item['statusRevision']})
        assert canceled.status_code == 200 and canceled.json()['error']['code'] == 'SYNC_ABANDONED', canceled.text
        assert sheets.records()[0] == local
        assert transport.grid('数据')[0] == ['编号','标题']
        preview = sheets.client.post(url+'/preview').json()
        assert sheets.client.post(url+'/retry', json={'expectedTableRevision':sheets.table_revision(),'impactRevision':preview['impactRevision']}).status_code == 409
        assert transport.changes() == 1


def test_existing_task_patch_survives_column_extension_without_new_field_grant(tmp_path):
    import pytest

    from autoflow.domain.project_data.capabilities import (
        QueryProjectRecordsRequest,
        UpdateProjectRecordCommand,
    )
    from autoflow.domain.projects.models import ProjectError
    from autoflow.infrastructure.database.project_claims import _parse_record_ref
    from tests.integration.test_project_run_data_start import uid
    from tests.integration.test_project_sheets_claim_paths import query_task
    transport = FakeSheetsTransport({'数据':[['编号','标题'],['A-1','original']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        scope, service = query_task(sheets)
        record = service.query_records(scope, QueryProjectRecordsRequest(1,sheets.project,sheets.table,sheets.dataset_generation(),[sheets.field_id('title')],'workflow',None,[],None,10))['items'][0]
        field = new_field(sheets.client, sheets.project, sheets.table, 'note', '备注', expectedTableRevision=sheets.table_revision())
        assert start_column(sheets, field)['status'] == 'succeeded'
        command = UpdateProjectRecordCommand(uid(), 1, _parse_record_ref(record['ref']), {sheets.field_id('title'):'frozen Task patch'}, record['contentRevision'])
        service.update_record(scope, command)
        assert next(item['value'] for item in sheets.records()[0]['values'] if item['fieldId'] == sheets.field_id('title')) == 'frozen Task patch'
        with pytest.raises(ProjectError):
            service.update_record(scope, UpdateProjectRecordCommand(uid(),1,_parse_record_ref(record['ref']),{field['ref']['fieldId']:'not granted'},2))


def test_foreign_same_name_column_is_not_adopted(tmp_path):
    transport = FakeSheetsTransport({'数据':[['编号','标题','备注'],['A-1','original','human']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        field = new_field(sheets.client,sheets.project,sheets.table,'note','备注',expectedTableRevision=sheets.table_revision())
        body = column_body(sheets,field)
        preview = sheets.client.post(sheets.url('/sheets/columns/preview'),json=body)
        body['impactRevision'] = preview.json()['impactRevision']
        refused = sheets.client.post(sheets.url('/sheets/columns'),headers=new_key(),json=body)
        assert refused.status_code == 409 and refused.json()['error']['code'] == 'SHEETS_COLUMN_OWNERSHIP', refused.text
        assert transport.changes() == 0 and transport.grid('数据')[1][2] == 'human'


def test_unsent_column_retry_uses_same_owner_and_confirms_only_once(tmp_path):
    from autoflow.providers.data.google_sheets import SheetsApiError
    transport = FakeSheetsTransport({'数据':[['编号','标题'],['A-1','original']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        field = new_field(sheets.client,sheets.project,sheets.table,'note','备注',expectedTableRevision=sheets.table_revision())
        transport.fail_writes = [SheetsApiError(-1,'notSent','not sent')]
        operation = start_column(sheets,field)
        url = sheets.url('/sheets/columns/'+operation['operationId'])
        preview = sheets.client.post(url+'/preview').json()
        response = sheets.client.post(url+'/retry',json={'expectedTableRevision':sheets.table_revision(),'impactRevision':preview['impactRevision']})
        assert response.status_code == 202 and response.json()['operation']['status'] == 'succeeded',response.text
        assert transport.developer_metadata[0]['metadataValue'] == operation['operationId']
        assert len(transport.grid('数据')[0]) == 27 and transport.changes() == 2
        assert sheets.client.post(url+'/retry',json={'expectedTableRevision':sheets.table_revision(),'impactRevision':preview['impactRevision']}).status_code == 409
        assert transport.changes() == 2


import pytest


@pytest.mark.parametrize('change',['moved','renamed','missingOwner','nonempty'])
def test_unknown_column_mismatch_never_maps_or_creates_again(tmp_path,monkeypatch,change):
    from autoflow.providers.data.google_sheets import SheetsApiError
    transport = FakeSheetsTransport({'数据':[['编号','标题'],['A-1','original']]})
    with open_sheets_table(tmp_path,transport,COLUMNS) as sheets:
        field = new_field(sheets.client,sheets.project,sheets.table,'note','备注',expectedTableRevision=sheets.table_revision())
        original = transport.send
        def lost(method,url,**kwargs):
            result=original(method,url,**kwargs)
            if url.endswith(':batchUpdate'): raise SheetsApiError(0,'lost','lost')
            return result
        monkeypatch.setattr(transport,'send',lost)
        operation=start_column(sheets,field)
        grid=transport.grid('数据')
        if change=='moved': transport.developer_metadata[0]['location']['dimensionRange']['startIndex']=25
        elif change=='renamed':grid[0][26]='foreign'
        elif change=='missingOwner':transport.developer_metadata.clear()
        else:grid[1] += ['']*24+['human value']
        response=sheets.client.post(sheets.url('/sheets/columns/'+operation['operationId']+'/verify'))
        assert response.status_code==202 and response.json()['operation']['status']=='reconciling',response.text
        assert response.json()['operation']['error']['code']=='SHEETS_COLUMN_EVIDENCE_MISMATCH'
        assert sheets.client.get(sheets.url('/sheets/binding')).json()['mapping']==sheets.binding['mapping']
        assert transport.changes()==1


def test_column_preview_cannot_send_after_binding_removed(tmp_path):
    transport=FakeSheetsTransport({'数据':[['编号','标题'],['A-1','original']]})
    with open_sheets_table(tmp_path,transport,COLUMNS) as sheets:
        field=new_field(sheets.client,sheets.project,sheets.table,'note','备注',expectedTableRevision=sheets.table_revision())
        body=column_body(sheets,field)
        preview=sheets.client.post(sheets.url('/sheets/columns/preview'),json=body).json()
        unbind=sheets.client.post(f'/api/v1/projects/{sheets.project}/mutation-impact',json={'action':'removeSheetsBinding','target':{'type':'table','projectId':sheets.project,'tableId':sheets.table},'change':{'mode':'remove'}}).json()
        removed=sheets.client.request('DELETE',sheets.url('/sheets/binding'),headers=new_key(),json={'expectedTableRevision':sheets.table_revision(),'impactRevision':unbind['impactRevision']})
        assert removed.status_code==202,removed.text
        response=sheets.client.post(sheets.url('/sheets/columns'),headers=new_key(),json={**body,'impactRevision':preview['impactRevision']})
        assert response.status_code in {404,412},response.text
        assert transport.changes()==0


@pytest.mark.parametrize('changed', ['name', 'owner'])
def test_value_reconcile_refuses_changed_owned_column(tmp_path, monkeypatch, changed):
    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.integration.test_project_sheets_sync import sync_operations

    transport = FakeSheetsTransport({'数据':[['编号','标题'],['A-1','original']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as sheets:
        pull(sheets)
        field = new_field(sheets.client, sheets.project, sheets.table, 'note', '备注', expectedTableRevision=sheets.table_revision())
        assert start_column(sheets, field)['status'] == 'succeeded'
        local = edit_note(sheets, field, sheets.records()[0], 'sent once')
        original = transport.send
        def lost(method, url, **kwargs):
            response = original(method, url, **kwargs)
            if url.endswith('/values:batchUpdate'): raise SheetsApiError(0, 'lost', 'response lost')
            return response
        monkeypatch.setattr(transport, 'send', lost)
        assert push(sheets).status_code == 202
        unknown, = sync_operations(sheets, 'unknown')
        writes = transport.changes()
        if changed == 'name': transport.grid('数据')[0][26] = 'foreign'
        else: transport.developer_metadata.clear()
        response = sheets.client.post(sheets.url('/sync-operations/'+unknown['syncOperationId']+'/reconcile'), headers=new_key(), json={'expectedStatusRevision':unknown['statusRevision']})
        assert response.status_code == 409 and response.json()['error']['code'] == 'SHEETS_COLUMN_EVIDENCE_MISMATCH', response.text
        assert sync_operations(sheets, 'unknown') == [unknown]
        assert sheets.records()[0] == local and transport.changes() == writes
