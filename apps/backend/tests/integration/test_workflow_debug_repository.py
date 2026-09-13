import io
import json
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import (
    SqlAlchemyWorkflowRunRepository,
)
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifacts
from autoflow.infrastructure.filesystem.workflow_diagnostics import result_archive
from tests.fixtures.workflow_runs import workflow_runtime
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_workflow_run_repository import _record


def test_diagnostic_ordinals_do_not_replace_results_and_commands_recover(tmp_path):
    db = tmp_path / 'db'
    migrate_database(db)
    factory = create_session_factory(db)
    repo = SqlAlchemyWorkflowRunRepository(factory)
    record = repo.create(_record()); run_id = record.data['runId']
    for i in range(105):
        purpose = 'result' if i in (2, 103) else 'diagnostic'
        repo.append(run_id, {'type': 'debug_checkpoint', 'message': f'checkpoint {i}'}, {'state': 'paused', '_artifact': {'id': str(i), 'nodeId': 'node', 'purpose': purpose, 'relativePath': f'{i}.json'}})
    assert repo.get(run_id).data['artifactCount'] == 2
    assert repo.get(run_id).data['artifactOrdinal'] == 105
    assert [a['ordinal'] for a in repo.artifacts(run_id, 0, 100)] == [3,104]
    assert len(repo.artifacts(run_id, 0, 50, purpose='diagnostic')) == 50
    assert len(repo.artifacts(run_id, 0, 100, purpose='diagnostic', through_seq=10)) == 8
    assert repo.active_id() == run_id
    assert repo.command(run_id,'id','hash') is None
    assert repo.command(run_id,'id','hash')['state'] == 'accepted'
    with pytest.raises(WorkflowError): repo.command(run_id,'id','different')
    repo.append(run_id, {'type':'debug_response'}, {'_command': {'commandId':'id','state':'applied'}})
    repo.command(run_id,'uncertain','hash2')
    repo.recover_interrupted()
    assert repo.command(run_id,'id')['state'] == 'applied'
    assert repo.command(run_id,'uncertain')['state'] == 'interrupted'
    assert repo.active_id() is None
    pages = repo.filtered_events(run_id, 0, 3, 999, {'q':'checkpoint 10'})
    assert len(pages) == 3
    latest = repo.filtered_events(run_id, 0, 3, 999, {}, tail=True)
    assert latest[-1]['type'] == 'interrupted'
    factory.dispose()


def test_archive_contains_registered_names_and_full_values(tmp_path):
    files = WorkflowArtifacts(tmp_path, 'run')
    item = files.save_json('node', 'x'*70000)
    data = b''.join(result_archive([(files.root/item['name'],item)]))
    with ZipFile(io.BytesIO(data)) as archive:
        assert json.loads(archive.read(item['name'])) == 'x'*70000
        assert json.loads(archive.read('manifest.json'))[0]['id'] == item['id']


def test_debug_api_validates_mode_json_and_navigation_before_commands(tmp_path):
    app, profile, _worker = workflow_runtime(tmp_path)
    body = {'runId':str(uuid4()), **workflow_payload(), 'profileId':profile.id}
    with TestClient(app, headers={'x-autoflow-token':'test-token'}) as client:
        # This fixture uses its configured token; read it from the established test constant.
        from tests.contract.test_workflow_runs import HEADERS
        client.headers.update(HEADERS)
        assert client.post('/api/v1/workflows/runs',json={**body,'debug':{'start':'entry'}}).status_code == 422
        invalid = client.post('/api/v1/workflows/runs',json={**body,'mode':'debug','debug':{'start':'node','targetNodeId':'missing'}})
        assert invalid.status_code == 422
        assert client.get('/api/v1/workflows/runs').json()['items'] == []
        command = {'commandId':'valid','expectedRevision':0,'action':'page','pageId':'page','url':'javascript:alert(1)'}
        assert client.post(f"/api/v1/workflows/runs/{body['runId']}/debug/commands",json=command).status_code == 422


def test_migration_preserves_historical_artifact_cutoff(tmp_path):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    db = tmp_path / 'db'
    migrate_database(db)
    factory = create_session_factory(db)
    repo = SqlAlchemyWorkflowRunRepository(factory)
    run_id = repo.create(_record()).data['runId']
    repo.append(run_id, {'type': 'node_succeeded', 'artifactId': 'old'}, {'_artifact': {'id': 'old', 'nodeId': 'node', 'relativePath': 'kept.json'}})
    original_seq = repo.artifacts(run_id, 0, 10)[0]['eventSeq']
    config = Config(str(Path('src/autoflow/infrastructure/database/alembic.ini')))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{db}')
    command.downgrade(config, '0007_workflow_artifacts')
    command.upgrade(config, 'head')
    assert repo.artifacts(run_id, 0, 10, through_seq=original_seq - 1) == []
    recovered = repo.artifacts(run_id, 0, 10, through_seq=original_seq)[0]
    assert (recovered['id'], recovered['relativePath'], recovered['purpose'], recovered['eventSeq']) == ('old', 'kept.json', 'result', original_seq)
    with factory() as session:
        assert session.execute(text('SELECT COUNT(*) FROM workflow_debug_commands')).scalar() == 0
    factory.dispose()
