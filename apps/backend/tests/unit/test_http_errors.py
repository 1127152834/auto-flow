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
    assert response.json()["error"]["message"] == "Model provider request failed"
    assert response.json()["error"]["details"] == {
        "status": 502,
        "fields": {"apiKey": "Invalid value"},
    }
    assert "sk-test-secret" not in response.text
