import json
import os
import subprocess
import sys

from autoflow.bootstrap.schema_export import export_schema


def test_schema_export_matches_the_formal_application(client):
    assert export_schema() == client.get('/openapi.json').json()


def test_schema_export_does_not_construct_runtime(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('schema export invoked runtime setup')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('autoflow.bootstrap.app.create_app', forbidden)
    monkeypatch.setattr('autoflow.bootstrap.app.migrate_database', forbidden)
    monkeypatch.setattr('autoflow.bootstrap.app.create_session_factory', forbidden)
    schema = export_schema()
    assert '/api/v1/profiles' in schema['paths']
    assert '/api/v1/model-providers' in schema['paths']
    assert '/api/workflows' in schema['paths']
    assert '/api/workflows/{workflow_id}/execute' in schema['paths']
    assert '/api/workflow-runs/{run_id}/logs' in schema['paths']
    assert '/api/events/stream' in schema['paths']
    assert list(tmp_path.iterdir()) == []


def test_schema_export_cli_outputs_only_json():
    result = subprocess.run(
        [sys.executable, '-m', 'autoflow.bootstrap.schema_export'],
        capture_output=True, text=True, check=True,
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )
    assert json.loads(result.stdout) == export_schema()
