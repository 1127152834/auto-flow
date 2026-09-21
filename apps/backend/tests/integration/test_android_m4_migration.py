import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from autoflow.infrastructure.database import session as database_session


@pytest.mark.parametrize('revision', ['0006_workflow_runs', '0007_android_devices', '0007_workflow_artifacts', '0008_merge_android_m4'])
def test_existing_migration_histories_keep_devices_runs_and_artifacts(tmp_path, revision):
    database = tmp_path / 'existing.sqlite3'
    config = Config(str(Path(database_session.__file__).with_name('alembic.ini')))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database}')
    command.upgrade(config, revision)
    artifact = {'id': 'image-one', 'nodeId': 'screen', 'relativePath': 'original.png'}
    with sqlite3.connect(database) as connection:
        indexed = revision in {'0007_workflow_artifacts', '0008_merge_android_m4'}
        connection.execute('INSERT INTO workflow_runs(id,workflow_id,request_hash,started_at,payload) VALUES(?,?,?,?,?)', ('run', 'flow', 'original-hash', '2026-09-13', json.dumps({'artifacts': [] if indexed else [artifact], 'artifactCount': 1})))
        if indexed:
            connection.execute('INSERT INTO workflow_run_artifacts(run_id,id,ordinal,node_id,payload) VALUES(?,?,?,?,?)', ('run', 'image-one', 1, 'screen', json.dumps(artifact)))
        if revision in {'0007_android_devices', '0008_merge_android_m4'}:
            connection.execute('INSERT INTO android_devices(id,payload) VALUES(?,?)', ('device', json.dumps({'name': 'Keep device', 'volumeId': 'keep-data'})))
    database_session.migrate_database(database)
    database_session.migrate_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT version_num FROM alembic_version').fetchall() == [('am01_management_operations',)]
        assert connection.execute('SELECT request_hash FROM workflow_runs').fetchone() == ('original-hash',)
        assert json.loads(connection.execute('SELECT payload FROM workflow_run_artifacts').fetchone()[0]) == artifact
        if revision in {'0007_android_devices', '0008_merge_android_m4'}:
            assert json.loads(connection.execute('SELECT payload FROM android_devices').fetchone()[0])['volumeId'] == 'keep-data'
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
