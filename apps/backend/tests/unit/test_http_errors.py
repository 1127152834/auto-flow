from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import error_response, install_error_handlers
from autoflow.adapters.http.model_schemas import ModelProviderCreateInput
from autoflow.domain.models.errors import ModelError


def test_validation_error_does_not_echo_secret_input_or_pydantic_context() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/provider")
    def create_provider(_body: ModelProviderCreateInput) -> None:
        return None

    response = TestClient(app).post(
        "/provider", json={"name": "Local", "apiKey": {"secret": "do-not-echo"}}
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["details"]["fields"].keys() == {"apiKey"}
    assert payload["error"]["requestId"]
    assert "do-not-echo" not in response.text
    assert "ctx" not in response.text


def test_required_api_key_uses_specific_safe_error_code() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/provider")
    def create_provider(_body: ModelProviderCreateInput) -> None:
        return None

    response = TestClient(app).post(
        "/provider", json={"name": "OpenAI", "presetId": "openai", "apiKey": ""}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MODEL_PROVIDER_API_KEY_REQUIRED"
    assert response.json()["error"]["details"] == {
        "fields": {"apiKey": "API key is required"}
    }


def test_error_response_is_available_for_middleware() -> None:
    response = error_response(401, "SIDECAR_UNAUTHORIZED", "Unauthorized")

    assert response.status_code == 401
    assert b'"details":{}' in response.body
    assert b'"requestId":"' in response.body


def test_model_error_handler_only_returns_safe_structured_details() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/failure")
    def fail() -> None:
        raise ModelError(
            "MODEL_PROVIDER_REQUEST_FAILED",
            "upstream rejected sk-test-secret",
            409,
            {
                "status": 502,
                "authorization": "Bearer sk-test-secret",
                "fields": {"apiKey": "sk-test-secret is invalid"},
            },
        )

    response = TestClient(app, raise_server_exceptions=False).get("/failure")

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "供应商请求失败"
    assert response.json()["error"]["details"] == {
        "status": 502,
        "fields": {"apiKey": "Invalid value"},
    }
    assert "sk-test-secret" not in response.text


def test_model_provider_status_messages_are_clear_and_never_echo_upstream_text() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/failure/{status}")
    def fail(status: int) -> None:
        code = {
            401: "MODEL_PROVIDER_AUTH_FAILED",
            402: "MODEL_PROVIDER_REQUEST_FAILED",
            404: "MODEL_PROVIDER_ENDPOINT_NOT_FOUND",
            429: "MODEL_PROVIDER_RATE_LIMITED",
        }[status]
        raise ModelError(
            code,
            "upstream leaked sk-test-secret",
            409,
            {"status": status, "body": "remote sk-test-secret"},
        )

    client = TestClient(app, raise_server_exceptions=False)
    expected = {
        401: "供应商认证失败，请检查 API Key",
        402: "供应商余额或额度不足，请充值或调整额度后重试",
        404: "供应商接口不存在，请检查服务地址或模型标识",
        429: "供应商触发限流或额度限制，请稍后重试",
    }
    for status, message in expected.items():
        response = client.get(f"/failure/{status}")
        assert response.json()["error"] == {
            "code": {
                401: "MODEL_PROVIDER_AUTH_FAILED",
                402: "MODEL_PROVIDER_REQUEST_FAILED",
                404: "MODEL_PROVIDER_ENDPOINT_NOT_FOUND",
                429: "MODEL_PROVIDER_RATE_LIMITED",
            }[status],
            "message": message,
            "details": {"status": status},
            "requestId": response.json()["error"]["requestId"],
        }
        assert "sk-test-secret" not in response.text


def test_non_contention_database_failure_remains_an_internal_error() -> None:
    import sqlite3

    from sqlalchemy.exc import OperationalError

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/failure")
    def fail() -> None:
        raise OperationalError("secret query", {}, sqlite3.OperationalError("disk I/O error"))

    response = TestClient(app, raise_server_exceptions=False).get("/failure")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret query" not in response.text
    assert "disk I/O" not in response.text
