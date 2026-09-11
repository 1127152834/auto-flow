from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.credentials.redaction import redact_text, redact_url


def test_redact_url_removes_basic_auth_and_sensitive_query_values():
    value = redact_url(
        "https://pt_live:super-secret@proxypanel.io/api/v1/proxies?api_key=pt_live&limit=10"
    )

    assert value == "https://proxypanel.io/api/v1/proxies?api_key=%3Credacted%3E&limit=10"
    assert "super-secret" not in value
    assert "pt_live" not in value


def test_redact_text_replaces_provider_secrets():
    assert redact_text("request failed token=pt_live", ["pt_live"]) == (
        "request failed token=<redacted>"
    )


def test_redact_url_does_not_raise_for_malformed_port():
    assert redact_url("https://proxypanel.io:bad/proxies") == "<redacted-url>"


def test_redact_url_handles_common_compound_secret_names():
    value = redact_url(
        "https://proxypanel.io/proxies?access_token=one&license-key=two&city=Miami"
    )

    assert "one" not in value
    assert "two" not in value
    assert "city=Miami" in value


def test_sidecar_api_requires_instance_token(tmp_path):
    client = TestClient(
        create_app(Settings(data_dir=str(tmp_path), instance_id="test", instance_token="secret"))
    )

    assert client.get("/api/v1/security-check").status_code == 401
    assert client.get(
        "/api/v1/security-check", headers={"x-autoflow-token": "secret"}
    ).status_code == 404
