"""Batch progress rules (remediation M5 5B-A4, B7).

``error_code`` is the stable grouping key for failures; the UI keeps a code-to-wording map, so a code
is never renamed. Messages are only ever shown masked, never grouped by.
"""

from __future__ import annotations

import re
from typing import Any

from autoflow.infrastructure.credentials.redaction import redact_sensitive_text

ERROR_CODES: tuple[str, ...] = (
    "input_invalid", "business_failed", "page_error", "environment_error",
    "outcome_unknown", "cancelled", "unknown",
)
_BY_OUTCOME = {
    "business": "business_failed", "page": "page_error", "infrastructure": "environment_error",
    "unknown": "outcome_unknown", "cancelled": "cancelled",
}
MESSAGE_LIMIT = 200
_UUID = re.compile(r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PLAIN_SECRET = re.compile(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|密码|口令)(\s*[=:：]\s*)[^\s,;&]+")


def error_code(last_outcome: str | None, last_error: dict[str, Any] | None) -> str:
    """Map a processing record's last outcome (and error code) to one value of ``ERROR_CODES``."""
    if isinstance((last_error or {}).get("code"), str) and last_error["code"] == "INPUT_VALUE_INVALID":  # type: ignore[index]
        return "input_invalid"
    return _BY_OUTCOME.get(last_outcome or "", "unknown")


def mask_message(message: str) -> str:
    """Credentials, internal ids and e-mail addresses removed, then shortened."""
    text = _PLAIN_SECRET.sub(r"[已隐藏]", redact_sensitive_text(message))
    text = _EMAIL.sub("[已隐藏]", _UUID.sub("…", text))
    return text if len(text) <= MESSAGE_LIMIT else text[: MESSAGE_LIMIT - 1] + "…"


def per_minute(count: int, minutes: float) -> float:
    return count / minutes if minutes > 0 else 0.0


def eta_seconds(*, remaining: int | None, recent_per_minute: float, average_per_minute: float) -> int | None:
    """Time left at the recent pace, else at the average pace; unknown when nothing is left or no pace exists."""
    rate = recent_per_minute or average_per_minute
    if remaining is None or remaining <= 0 or rate <= 0:
        return None
    return round(remaining / rate * 60)
