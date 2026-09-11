from urllib.parse import parse_qsl, urlsplit, urlunsplit

from .errors import ModelError
from .models import ProviderConnection

DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}
AUTH_QUERY_NAMES = {
    "key",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "authorization",
    "password",
}
OPTIONAL_API_KEY_PRESETS = {"ollama", "custom-openai-compatible"}


def normalize_base_url(connection: ProviderConnection) -> str:
    value = (
        connection.base_url or DEFAULT_URLS.get(connection.provider_kind, "")
    ).strip()
    if not value:
        raise ModelError(
            "MODEL_PROVIDER_BASE_URL_REQUIRED", "该供应商需要填写 Base URL", 422
        )
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ModelError(
            "MODEL_PROVIDER_BASE_URL_INVALID", "Base URL 格式无效", 422
        ) from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username
        or parsed.password
        or parsed.fragment
        or port is not None
        and not 1 <= port <= 65535
    ):
        raise ModelError("MODEL_PROVIDER_BASE_URL_INVALID", "Base URL 格式无效", 422)
    if any(
        name.casefold() in AUTH_QUERY_NAMES
        for name, _ in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise ModelError(
            "MODEL_PROVIDER_BASE_URL_INVALID", "Base URL 不得包含认证参数", 422
        )
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), parsed.query, "")
    )


def validate_connection(connection: ProviderConnection, secret: str) -> str:
    value = normalize_base_url(connection)
    if (
        connection.provider_kind in {"anthropic", "gemini"}
        or connection.preset_id not in OPTIONAL_API_KEY_PRESETS
    ) and not secret.strip():
        raise ModelError("MODEL_PROVIDER_API_KEY_REQUIRED", "该供应商需要 API Key", 422)
    return value
