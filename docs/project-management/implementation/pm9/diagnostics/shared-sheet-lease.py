"""Known failing acceptance probe; not a passing regression or CI test.

Run from apps/backend with PYTHONPATH=.:src uv run pytest
../../docs/project-management/implementation/pm9/diagnostics/shared-sheet-lease.py -q
"""

from tests.integration.test_project_sheets_sync import COLUMNS, FakeSheetsTransport, open_sheets_table, new_key, pull
def test_diagnostic_shared_sheet_lease_keys(tmp_path):
    from tests.fixtures.sheets import (
        SheetsTable,
        binding_impact,
        connect,
        new_field,
        new_project,
        new_table,
    )
    columns = [*COLUMNS, ('note', '备注', 'string')]
    transport = FakeSheetsTransport({'数据': [['编号', '标题', '备注'], ['A-1', 'original', 'old-note']]})
    with open_sheets_table(tmp_path, transport, columns) as first:
        client = first.client
        project = new_project(client, 'Q')
        connection = connect(client, project, new_key())['result']['connectionId']
        table = new_table(client, project)['tableId']
        fields = {key: new_field(client, project, table, key, name, type=kind, expectedTableRevision=index + 1)
                  for index, (key, name, kind) in enumerate(columns)}
        body = {
            'connectionId': connection, 'spreadsheetId': transport.spreadsheet_id, 'sheetId': 1000,
            'identityStrategy': {'kind': 'column', 'columnId': 'A'},
            'mapping': [{'fieldId': fields[key]['ref']['fieldId'], 'columnId': chr(65 + i), 'direction': 'both', 'formula': False}
                        for i, (key, _, _) in enumerate(columns)],
            'expectedTableRevision': 4,
        }
        accepted = client.put(f'/api/v1/projects/{project}/tables/{table}/sheets/binding',
                              json=binding_impact(client, project, table, body), headers=new_key())
        assert accepted.status_code == 202, accepted.text
        second = SheetsTable(client, transport, project, table, connection, fields, accepted.json()['operation']['result'])
        pull(first)
        pull(second)
        from tests.integration.test_project_run_data_start import _input
        from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups, _lease_key
        keys = []
        with client.app.state.session_factory() as session:
            for bound in (first, second):
                table_ref = {"tableId": bound.table, "datasetGeneration": bound.dataset_generation()}
                plan = {"inputs": [_input(bound.project, table_ref, bound.fields["title"], "input")]}
                selection = SqlAlchemyProjectInputGroups(session).select_required(bound.project, plan)
                assert selection.status == "ready"
                key, = selection.lease_keys
                keys.append(_lease_key(key))
        assert keys[0] == keys[1], "same physical Spreadsheet/Sheet/identity must share one Workspace lease"
