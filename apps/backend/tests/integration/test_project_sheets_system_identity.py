"""System UUID initialization crosses real HTTP, SQLite and controlled Google transport."""
from uuid import UUID

from tests.contract.test_project_sheets import base, inspection_body, prepared
from tests.fixtures.sheets import binding_impact, new_key


def test_system_identity_initializes_once_and_recovers_original_command(tmp_path):
    client, transport, project, connection, table, identity, title = prepared(tmp_path)
    with client:
        body = {**inspection_body(connection, identity, title), "identityStrategy": {"kind": "system", "columnId": "C"}, "expectedTableRevision": 3}
        body = binding_impact(client, project, table['tableId'], body)
        key = new_key()
        url = base(client, project, table) + '/sheets/system-identity'
        response = client.post(url, json=body, headers=key)
        assert response.status_code == 202, response.text
        operation = response.json()['operation']
        assert operation['status'] == 'succeeded', operation
        assert operation['kind'] == 'initializeSheetsIdentity'
        remote = transport.grid('数据')
        assert remote[0] == ['编号', '标题', '_autoflow_id']
        assert str(UUID(remote[1][2])) == remote[1][2]
        writes = transport.changes()
        assert writes == 1
        replay = client.post(url, json=body, headers=key)
        assert replay.status_code == 202 and replay.json() == response.json()
        assert transport.changes() == writes
        binding = client.get(base(client, project, table) + '/sheets/binding').json()
        assert binding['identityStrategy'] == {'kind': 'system', 'columnId': 'C'}

        pulled = client.post(base(client, project, table) + '/sync/pull', json={'expectedTableRevision': 4}, headers=new_key())
        assert pulled.status_code == 202, pulled.text
        assert pulled.json()['operation']['status'] == 'succeeded'
        records = client.get(base(client, project, table) + '/records', params={'datasetGeneration': client.get(base(client, project, table)).json()['datasetGeneration']}).json()['items']
        assert records and records[0]['ref']['recordKey'] == {'type': 'uuid', 'value': remote[1][2]}


def initialize(client, project, connection, table, identity, title):
    body = {**inspection_body(connection, identity, title), 'identityStrategy': {'kind': 'system', 'columnId': 'C'}, 'expectedTableRevision': 3}
    body = binding_impact(client, project, table['tableId'], body)
    response = client.post(base(client, project, table) + '/sheets/system-identity', json=body, headers=new_key())
    assert response.status_code == 202, response.text
    return response.json()['operation']


def test_lost_identity_response_recovers_one_original_plan_and_blocks_new_sends(tmp_path, monkeypatch):
    from autoflow.providers.data.google_sheets import SheetsApiError
    client, transport, project, connection, table, identity, title = prepared(tmp_path)
    original = transport.send
    def lost(method, url, **kwargs):
        result = original(method, url, **kwargs)
        if url.endswith(':batchUpdate'):
            raise SheetsApiError(0, 'responseLost', 'lost')
        return result
    monkeypatch.setattr(transport, 'send', lost)
    with client:
        operation = initialize(client, project, connection, table, identity, title)
        assert operation['status'] == 'reconciling'
        listed = client.get(base(client, project, table) + '/sheets/system-identity').json()
        assert listed['items'][0]['syncOperationId'] == operation['operationId']
        url = base(client, project, table) + '/sheets/system-identity/' + operation['operationId']
        uuid = transport.grid('数据')[1][2]
        assert client.get(base(client, project, table) + '/sheets/binding').json() is None
        # A new key cannot turn uncertainty into permission to initialize again.
        blocked = client.post(f'/api/v1/projects/{project}/mutation-impact', json={
            'action': 'changeSheetsBinding', 'target': {'type':'table', 'projectId':project, 'tableId':table['tableId']},
            'change': {**inspection_body(connection, identity, title), 'identityStrategy': {'kind':'system','columnId':'C'}},
        })
        assert blocked.status_code == 409, blocked.text
        assert client.post(url + '/retry').status_code == 409
        recovered = client.post(url + '/verify')
        assert recovered.status_code == 202, recovered.text
        assert recovered.json()['operation']['status'] == 'succeeded'
        assert transport.grid('数据')[1][2] == uuid and transport.changes() == 1
        assert client.post(url + '/verify').json() == recovered.json()
        assert transport.changes() == 1


def test_proven_unsent_identity_retries_frozen_uuids_only(tmp_path):
    from autoflow.infrastructure.database.project_sync_models import SyncOperationRow
    from autoflow.providers.data.google_sheets import SheetsApiError
    client, transport, project, connection, table, identity, title = prepared(tmp_path)
    transport.fail_writes = [SheetsApiError(-1, 'notSent', 'not sent')]
    with client:
        operation = initialize(client, project, connection, table, identity, title)
        assert operation['status'] == 'failed'
        factory = client.app.state.session_factory
        with factory() as session:
            plan = session.get(SyncOperationRow, operation['operationId']).request['initialization']
        url = base(client, project, table) + '/sheets/system-identity/' + operation['operationId']
        assert client.post(url + '/verify').json()['operation']['status'] == 'failed'
        retried = client.post(url + '/retry')
        assert retried.status_code == 202, retried.text
        assert retried.json()['operation']['status'] == 'succeeded'
        assert transport.grid('数据')[1][2] == plan['values'][1]
        assert len(transport.grid('数据')[0]) == 3
        assert client.post(url + '/retry').status_code == 409
        assert transport.changes() == 2  # one transport-confirmed unsent attempt, one actual mutation


import pytest


@pytest.mark.parametrize('mutation', ['partial', 'renamed', 'moved', 'rowChanged', 'ownerMissing'])
def test_identity_unknown_mismatch_never_publishes_or_resends(tmp_path, monkeypatch, mutation):
    from autoflow.providers.data.google_sheets import SheetsApiError
    client, transport, project, connection, table, identity, title = prepared(tmp_path)
    original = transport.send
    def lost(method, url, **kwargs):
        result = original(method, url, **kwargs)
        if url.endswith(':batchUpdate'):
            raise SheetsApiError(0, 'responseLost', 'lost')
        return result
    monkeypatch.setattr(transport, 'send', lost)
    with client:
        operation = initialize(client, project, connection, table, identity, title)
        grid = transport.grid('数据')
        if mutation == 'partial': grid[1][2] = ''
        elif mutation == 'renamed': grid[0][2] = 'other'
        elif mutation == 'moved':
            for row in grid: row[1], row[2] = row[2], row[1]
        elif mutation == 'rowChanged': grid[1][1] = 'human edit'
        else: transport.developer_metadata.clear()
        url = base(client, project, table) + '/sheets/system-identity/' + operation['operationId']
        verified = client.post(url + '/verify')
        assert verified.status_code == 202, verified.text
        assert verified.json()['operation']['error']['code'] == 'SHEETS_IDENTITY_EVIDENCE_MISMATCH'
        assert client.get(base(client, project, table) + '/sheets/binding').json() is None
        assert transport.changes() == 1


def test_system_uuid_and_text_binding_share_one_physical_lease_and_push_by_uuid(tmp_path):
    from autoflow.infrastructure.database.project_claims import (
        _parse_record_ref,
        resolve_record_lease,
    )
    from tests.fixtures.sheets import (
        SheetsTable,
        connect,
        new_field,
        new_project,
        new_table,
    )
    from tests.integration.test_project_sheets_sync import edit_title, pull, push
    client, transport, project, connection, table, identity, title = prepared(tmp_path)
    with client:
        operation = initialize(client, project, connection, table, identity, title)
        first = SheetsTable(client, transport, project, table['tableId'], connection['connectionId'], {'code':identity, 'title':title}, operation['result'])
        other_project = new_project(client, 'other')
        other_connection = connect(client, other_project, new_key())['result']
        other_table = new_table(client, other_project)
        other_id = new_field(client, other_project, other_table['tableId'], 'id', '身份', expectedTableRevision=1)
        other_title = new_field(client, other_project, other_table['tableId'], 'title', '标题', expectedTableRevision=2)
        body = {**inspection_body(other_connection, other_id, other_title), 'identityStrategy': {'kind':'column','columnId':'C'}, 'expectedTableRevision':3}
        body['mapping'][0]['columnId'] = 'C'
        result = client.put(base(client, other_project, other_table) + '/sheets/binding', json=binding_impact(client, other_project, other_table['tableId'], body), headers=new_key())
        assert result.status_code == 202, result.text
        second = SheetsTable(client, transport, other_project, other_table['tableId'], other_connection['connectionId'], {'code':other_id,'title':other_title}, result.json()['operation']['result'])
        pull(first); pull(second)
        a, b = first.records()[0], second.records()[0]
        assert a['ref']['recordKey']['type'] == 'uuid' and b['ref']['recordKey']['type'] == 'text'
        with client.app.state.session_factory() as session:
            assert resolve_record_lease(session, _parse_record_ref(a['ref']))[0] == resolve_record_lease(session, _parse_record_ref(b['ref']))[0]
        edit_title(first, a, 'local UUID edit')
        result = push(first)
        assert result.status_code == 202, result.text
        assert transport.grid('数据')[1][1] == 'local UUID edit'
        assert transport.grid('数据')[1][2] == a['ref']['recordKey']['value']


def test_unknown_identity_recovers_with_fresh_local_confirmation_after_table_edit(tmp_path, monkeypatch):
    from autoflow.providers.data.google_sheets import SheetsApiError
    client, transport, project, connection, table, identity, title = prepared(tmp_path)
    original = transport.send
    def lost(method, url, **kwargs):
        result = original(method, url, **kwargs)
        if url.endswith(':batchUpdate'): raise SheetsApiError(0, 'responseLost', 'lost')
        return result
    monkeypatch.setattr(transport, 'send', lost)
    with client:
        operation = initialize(client, project, connection, table, identity, title)
        changed = client.patch(base(client, project, table), json={'expectedTableRevision':3, 'name':'renamed'}, headers=new_key())
        assert changed.status_code == 200, changed.text
        url = base(client, project, table) + '/sheets/system-identity/' + operation['operationId']
        assert client.post(url + '/verify').status_code == 412
        preview = client.post(url + '/preview')
        assert preview.status_code == 200, preview.text
        recovered = client.post(url + '/verify', json={'expectedTableRevision':4, 'impactRevision':preview.json()['impactRevision']})
        assert recovered.status_code == 202, recovered.text
        assert recovered.json()['operation']['status'] == 'succeeded'
        assert transport.changes() == 1


def test_unresolved_structural_send_fences_peer_values_claims_and_binding(tmp_path, monkeypatch):
    from autoflow.domain.projects.models import ProjectError
    from autoflow.infrastructure.database.project_claims import (
        _parse_record_ref,
        resolve_record_lease,
    )
    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.fixtures.sheets import (
        FakeSheetsTransport,
        new_field,
        new_table,
        open_sheets_table,
    )
    from tests.integration.test_project_sheets_sync import (
        COLUMNS,
        edit_title,
        pull,
        push,
    )
    transport = FakeSheetsTransport({'数据': [['编号', '标题'], ['A-1', 'original']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as first:
        client, project = first.client, first.project
        pull(first)
        record = first.records()[0]
        edit_title(first, record, 'pending before structure')
        table = new_table(client, project, 'initializing')
        identity = new_field(client, project, table['tableId'], 'id', '编号', expectedTableRevision=1)
        title = new_field(client, project, table['tableId'], 'title', '标题', expectedTableRevision=2)
        original = transport.send
        def lost(method, url, **kwargs):
            result = original(method, url, **kwargs)
            if url.endswith(':batchUpdate'): raise SheetsApiError(0, 'responseLost', 'lost')
            return result
        monkeypatch.setattr(transport, 'send', lost)
        operation = initialize(client, project, {'connectionId':first.connection}, table, identity, title)
        assert operation['status'] == 'reconciling'
        assert push(first).status_code == 409
        with client.app.state.session_factory() as session, pytest.raises(ProjectError, match='来源仍有'):
            resolve_record_lease(session, _parse_record_ref(record['ref']))
        unbind = client.post(f'/api/v1/projects/{project}/mutation-impact', json={
            'action':'removeSheetsBinding','target':{'type':'table','projectId':project,'tableId':first.table},'change':{'mode':'remove'},
        })
        assert unbind.status_code == 409
        assert transport.changes() == 1 and transport.grid('数据')[1][1] == 'original'
        verified = client.post(base(client, project, table) + '/sheets/system-identity/' + operation['operationId'] + '/verify')
        assert verified.status_code == 202 and verified.json()['operation']['status'] == 'succeeded', verified.text
        assert push(first).status_code == 202
        assert transport.grid('数据')[1][1] == 'pending before structure'


def test_value_send_unknown_blocks_system_initialization_before_any_column_write(tmp_path):
    from autoflow.providers.data.google_sheets import SheetsApiError
    from tests.fixtures.sheets import (
        FakeSheetsTransport,
        new_field,
        new_table,
        open_sheets_table,
    )
    from tests.integration.test_project_sheets_sync import (
        COLUMNS,
        edit_title,
        pull,
        push,
    )
    transport = FakeSheetsTransport({'数据': [['编号', '标题'], ['A-1', 'original']]})
    with open_sheets_table(tmp_path, transport, COLUMNS) as first:
        client, project = first.client, first.project
        pull(first); edit_title(first, first.records()[0], 'pending')
        transport.fail_writes = [SheetsApiError(0, 'responseLost', 'lost')]
        assert push(first).status_code == 202
        table = new_table(client, project, 'initializing')
        identity = new_field(client, project, table['tableId'], 'id', '编号', expectedTableRevision=1)
        title = new_field(client, project, table['tableId'], 'title', '标题', expectedTableRevision=2)
        body = {**inspection_body({'connectionId':first.connection}, identity, title), 'identityStrategy':{'kind':'system','columnId':'C'}, 'expectedTableRevision':3}
        response = client.post(base(client, project, table) + '/sheets/system-identity', json=binding_impact(client, project, table['tableId'], body), headers=new_key())
        assert response.status_code == 409, response.text
        assert response.json()['error']['code'] == 'SHEETS_SOURCE_SEND_IN_PROGRESS'
        assert transport.changes() == 1 and transport.grid('数据')[0] == ['编号','标题']


def test_explicit_rebind_reuses_owned_system_column_without_rewriting_uuids(tmp_path):
    client, transport, project, connection, table, identity, title = prepared(tmp_path)
    with client:
        initialized = initialize(client, project, connection, table, identity, title)
        uuid = transport.grid('数据')[1][2]
        # Rebinding is a new explicit local generation, using proven source ownership.
        body = {**inspection_body(connection, identity, title), 'identityStrategy':{'kind':'system','columnId':'C'},
                'expectedTableRevision':4, 'expectedBindingEpoch':initialized['result']['bindingEpoch']}
        response = client.put(base(client, project, table) + '/sheets/binding', json=binding_impact(client, project, table['tableId'], body), headers=new_key())
        assert response.status_code == 202 and response.json()['operation']['status'] == 'succeeded', response.text
        pulled = client.post(base(client, project, table) + '/sync/pull', json={'expectedTableRevision':5}, headers=new_key())
        assert pulled.status_code == 202 and pulled.json()['operation']['status'] == 'succeeded', pulled.text
        assert transport.changes() == 1 and transport.grid('数据')[1][2] == uuid
        # A forged same-name column never becomes owned just because it has UUID-shaped values.
        transport.developer_metadata.clear()
        body.update(expectedTableRevision=5, expectedBindingEpoch=2)
        refused = client.put(base(client, project, table) + '/sheets/binding', json=binding_impact(client, project, table['tableId'], body), headers=new_key())
        assert refused.status_code == 409 and refused.json()['error']['code'] == 'SHEETS_IDENTITY_UNVERIFIED'
        assert transport.changes() == 1
