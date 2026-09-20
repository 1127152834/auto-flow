import re
from collections.abc import Iterable
from typing import Any

_STRUCTURED_SECRET = re.compile(
    r"(?i)(authorization\s*:\s*bearer\s+|[?&](?:api_key|key|token)=|"
    r"[\"'](?:api_key|password|token)[\"']\s*:\s*[\"'])[^\s&,;\"']+"
)
_URL_PASSWORD = re.compile(r"(?i)(://[^:/\s]+:)[^@/\s]+(@)")
_SECRET_KEYS = frozenset(
    {
        "accesstoken",
        "apikey",
        "appsecret",
        "authorization",
        "bearertoken",
        "license",
        "licensekey",
        "password",
        "proxypassword",
        "refreshtoken",
        "secret",
        "token",
    }
)


def redact_sensitive_text(message: str, secrets: Iterable[str | bytes] = ()) -> str:
    """Remove known credentials and common credential syntax from error text."""

    redacted = message
    for secret in secrets:
        value = secret.decode("utf-8", errors="ignore") if isinstance(secret, bytes) else secret
        if value:
            redacted = redacted.replace(value, "[REDACTED]")
    redacted = _STRUCTURED_SECRET.sub(r"\1[REDACTED]", redacted)
    return _URL_PASSWORD.sub(r"\1[REDACTED]\2", redacted)


def redact_sensitive_value(value: Any) -> Any:
    """Redact credential-shaped values while preserving JSON structure."""

    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if _is_secret_key(str(key))
                else redact_sensitive_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_value(item) for item in value)
    return redact_sensitive_text(value) if isinstance(value, str) else value


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized in _SECRET_KEYS or normalized.endswith(
        ("apikey", "password", "secret", "licensekey", "token")
    )
