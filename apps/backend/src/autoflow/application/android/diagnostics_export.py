from typing import Any

_PRIVATE = {"path", "token", "password", "inputText", "apk", "screenshot", "rawLogcat", "logcat", "accounts", "username", "systemUser"}


def redact_diagnostics(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key not in _PRIVATE}
