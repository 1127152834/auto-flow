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


def diagnostic_snapshot(value: dict[str, Any]) -> dict[str, Any]:
    """Export only reviewed status fields, never arbitrary metadata or messages."""
    from autoflow.application.android.diagnostics import CHECK_NAMES

    environment = value.get("environment", {})
    snapshot = {
        key: value[key]
        for key in ("deviceIds", "includeAdvancedLogs", "workflow") if key in value
    }
    snapshot["environment"] = {
        key: environment[key]
        for key in ("checkedAt", "runtimeId", "status", "code") if key in environment
    }
    snapshot["environment"]["checks"] = {
        name: {key: check[key] for key in ("status", "code") if key in check}
        for name, check in environment.get("checks", {}).items() if name in CHECK_NAMES
    }
    snapshot["devices"] = [
        {key: item[key] for key in ("deviceId", "revision", "runtimeState", "observedAt", "stale") if key in item}
        for item in value.get("devices", [])
    ]
    snapshot["operations"] = [
        {key: item[key] for key in ("operationId", "targetId", "action", "state", "stageCode", "attempt", "retryOf",
                                    "createdAt", "startedAt", "finishedAt", "resultCode") if key in item}
        for item in value.get("operations", [])
    ]
    if "advancedLogs" in value:
        snapshot["advancedLogs"] = {
            key: value["advancedLogs"][key] for key in ("status", "code") if key in value["advancedLogs"]
        }
    return redact_diagnostics(snapshot)
