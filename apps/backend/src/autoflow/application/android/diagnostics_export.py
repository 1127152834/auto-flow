import re
from collections.abc import Mapping
from typing import Any

_PRIVATE = {
    "path",
    "token",
    "password",
    "inputtext",
    "apk",
    "screenshot",
    "rawlogcat",
    "logcat",
    "accounts",
    "username",
    "systemuser",
    "workspacepath",
    "volumepath",
    "hostpath",
    "credential",
    "credentials",
    "secret",
    "authorization",
    "cookie",
}
_HOST_PATH = re.compile(r"(?:(?:/Users|/home|/root|/private/var|/var/folders|/tmp|/workspace|/Volumes)/[^\s'\"`]+|[A-Za-z]:\\Users\\[^\s'\"`]+)")


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _redact(item)
            for key, item in value.items()
            if str(key).casefold() not in _PRIVATE
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    if isinstance(value, str):
        return _HOST_PATH.sub("[REDACTED_PATH]", value)
    return value


def redact_diagnostics(value: dict[str, Any]) -> dict[str, Any]:
    return _redact(value)
