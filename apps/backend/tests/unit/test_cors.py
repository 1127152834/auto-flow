import pytest
from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings


@pytest.mark.parametrize('origin', ['http://localhost:5173', 'null'])
def test_renderer_preflight_and_token_protection(tmp_path, origin):
    client = TestClient(create_app(Settings(
        data_dir=str(tmp_path), instance_id='test', instance_token='secret', renderer_origin=origin,
    )))
    response = client.options('/api/v1/example', headers={
        'Origin': origin, 'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'x-autoflow-token',
    })
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin
    assert client.get('/api/v1/example', headers={'Origin': origin}).status_code == 401
    rejected = client.options('/health', headers={
        'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'x-autoflow-token',
    })
    assert rejected.status_code == 400
    assert 'access-control-allow-origin' not in rejected.headers
