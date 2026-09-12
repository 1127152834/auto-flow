import json

import pytest
from fastapi.testclient import TestClient

from autoflow.domain.profiles.models import ProfileSpec
from autoflow.infrastructure.filesystem import profile_environment

ENDPOINT = "/api/v1/profiles/environment-options"


def test_catalog_matches_json_and_contains_valid_profile_values(client, profile_payload):
    response = client.get(ENDPOINT)
    assert response.status_code == 200
    catalog = response.json()
    assert catalog == json.loads(profile_environment.CATALOG_PATH.read_text())
    assert len(catalog["locales"]) > 10
    assert len(catalog["timezones"]) > 9
    for field, key in (("locale", "locales"), ("timezone", "timezones")):
        for option in catalog[key]:
            ProfileSpec.from_values({"name": "验证", "browser_version": "146.0.1.1", field: option["value"]})

    created = client.post("/api/v1/profiles", json={**profile_payload, "locale": "ja-JP", "timezone": "Asia/Tokyo"})
    assert created.status_code == 201
    saved = client.get(f"/api/v1/profiles/{created.json()['id']}").json()
    assert (saved["locale"], saved["timezone"]) == ("ja-JP", "Asia/Tokyo")
    updated = client.put(f"/api/v1/profiles/{saved['id']}", json={**profile_payload, "locale": "de-CH-1901", "timezone": "Europe/Zurich"})
    assert updated.status_code == 200
    saved = client.get(f"/api/v1/profiles/{saved['id']}").json()
    assert (saved["locale"], saved["timezone"]) == ("de-CH-1901", "Europe/Zurich")


def test_catalog_is_authenticated_and_uses_the_generated_contract(client):
    assert client.get(ENDPOINT, headers={"x-autoflow-token": "wrong"}).status_code == 401
    operation = client.get("/openapi.json").json()["paths"][ENDPOINT]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ProfileEnvironmentOptionsRead"
    }


def test_backend_file_is_the_live_source(client, tmp_path, monkeypatch):
    path = tmp_path / "environment.json"
    monkeypatch.setattr(profile_environment, "CATALOG_PATH", path)
    catalog = {
        "locales": [{"value": "en-NZ", "label": "英语（新西兰）"}],
        "timezones": [{"value": "Pacific/Auckland", "label": "奥克兰"}],
    }
    path.write_text(json.dumps(catalog))
    assert client.get(ENDPOINT).json() == catalog
    catalog["locales"][0]["label"] = "维护后的名称"
    path.write_text(json.dumps(catalog))
    assert client.get(ENDPOINT).json() == catalog


def test_missing_catalog_returns_an_error_instead_of_demo_data(client, tmp_path, monkeypatch):
    monkeypatch.setattr(profile_environment, "CATALOG_PATH", tmp_path / "missing.json")
    with TestClient(client.app, raise_server_exceptions=False, headers={"x-autoflow-token": "secret"}) as failing_client:
        response = failing_client.get(ENDPOINT)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"


@pytest.mark.parametrize("content", ["not json", '{"locales": [], "timezones": []}', '{"locales": [{"value": 1, "label": "invalid"}], "timezones": []}'])
def test_invalid_catalog_fails_without_fallback(tmp_path, monkeypatch, content):
    path = tmp_path / "environment.json"
    path.write_text(content)
    monkeypatch.setattr(profile_environment, "CATALOG_PATH", path)
    with pytest.raises(ValueError):
        profile_environment.read_profile_environment_options()
    path.unlink()
    with pytest.raises(FileNotFoundError):
        profile_environment.read_profile_environment_options()
