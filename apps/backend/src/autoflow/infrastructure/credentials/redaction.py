"""Small, dependency-free redaction helpers for provider errors and logs."""

from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SENSITIVE_QUERY_MARKERS = ("apikey", "authorization", "password", "secret", "token")


def _is_sensitive_query_key(key: str) -> bool:
    normalized = key.lower().replace("-", "").replace("_", "").replace(".", "")
    return normalized in {"auth", "key"} or normalized.endswith("key") or any(
        marker in normalized for marker in _SENSITIVE_QUERY_MARKERS
    )


def redact_url(url: str) -> str:
    """Remove URL credentials and sensitive query values while keeping context."""

    try:
        parts = urlsplit(url)
    except ValueError:
        return "<redacted-url>"

    try:
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        return "<redacted-url>"
    if port is not None:
        host = f"{host}:{port}"
    netloc = host
    query = [
        (key, "<redacted>" if _is_sensitive_query_key(key) else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(query), ""))


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    """Replace known secret values before a message reaches logs or errors."""

    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return redacted
