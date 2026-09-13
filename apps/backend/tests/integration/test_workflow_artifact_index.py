import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import (
    SqlAlchemyWorkflowRunRepository,
)
from tests.integration.test_workflow_run_repository import _record


def test_old_artifacts_migrate_without_moving_files_and_roundtrip_downgrade(tmp_path):
    database = tmp_path / 'db.sqlite3'
    config = Config(str(Path('src/autoflow/infrastructure/database/alembic.ini')))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database}')
    command.upgrade(config, '0006_workflow_runs')
    factory = create_session_factory(database)
    original = _record()
    artifact = {'id': 'old', 'nodeId': 'extract', 'relativePath': 'artifacts/old.json'}
    original.data['artifacts'] = [artifact]
    SqlAlchemyWorkflowRunRepository(factory).create(original)
    migrate_database(database)
    repository = SqlAlchemyWorkflowRunRepository(factory)
    identifier = original.data['runId']
    assert repository.artifact(identifier, 'old') == artifact
    assert repository.get(identifier).data['artifacts'] == []
    assert repository.get(identifier).data['artifactCount'] == 1
    command.downgrade(config, '0006_workflow_runs')
    with factory() as session:
        stored = json.loads(session.execute(text('SELECT payload FROM workflow_runs')).scalar())
        assert stored['artifacts'] == [artifact]
    migrate_database(database)
    assert repository.artifact(identifier, 'old') == artifact
    factory.dispose()


def test_repeated_artifacts_are_indexed_transactionally_with_events(tmp_path):
    database = tmp_path / 'db.sqlite3'
    migrate_database(database)
    factory = create_session_factory(database)
    repository = SqlAlchemyWorkflowRunRepository(factory)
    record = repository.create(_record())
    identifier = record.data['runId']
    for i in range(123):
        artifact = {'id': str(i), 'nodeId': 'repeat', 'executionId': f'execution-{i}', 'relativePath': f'artifacts/{i}.json'}
        repository.append(identifier, {'type': 'node_succeeded', 'artifactId': str(i)}, {'_artifact': artifact})
    stored = repository.get(identifier).data
    assert stored['artifactCount'] == 123 and not stored.get('artifacts')
    pages = [repository.artifacts(identifier, after, 50) for after in (0, 50, 100)]
    assert [len(page) for page in pages] == [50, 50, 23]
    assert [a['ordinal'] for page in pages for a in page] == list(range(1, 124))
    assert repository.artifacts(identifier, 0, 50, execution_id='execution-70')[0]['id'] == '70'
    assert repository.artifacts(identifier, 0, 50, node_id='other') == []
    assert len(repository.events(identifier, 0, 200)) == 124
    factory.dispose()
