import re
from collections.abc import Iterable

_STRUCTURED_SECRET = re.compile(
    r"(?i)(authorization\s*:\s*bearer\s+|[?&](?:api_key|key|token)=|"
    r"[\"'](?:api_key|password|token)[\"']\s*:\s*[\"'])[^\s&,;\"']+"
)
_URL_PASSWORD = re.compile(r"(?i)(://[^:/\s]+:)[^@/\s]+(@)")


def redact_sensitive_text(message: str, secrets: Iterable[str | bytes] = ()) -> str:
    """Remove known credentials and common credential syntax from error text."""

    redacted = message
    for secret in secrets:
        value = secret.decode("utf-8", errors="ignore") if isinstance(secret, bytes) else secret
        if value:
            redacted = redacted.replace(value, "[REDACTED]")
    redacted = _STRUCTURED_SECRET.sub(r"\1[REDACTED]", redacted)
    return _URL_PASSWORD.sub(r"\1[REDACTED]\2", redacted)
