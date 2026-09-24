import re
from collections.abc import Mapping
from datetime import UTC, datetime
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
_LOGCAT_HEADER = re.compile(rb"^\s*(\d{10}(?:\.\d{1,3})?)\s+\d+\s+\d+\s+([VDIWEF])\s+([A-Za-z0-9_.-]{1,64}):")


def summarize_logcat(raw: bytes, *, window_seconds: int = 300, max_bytes: int = 65536) -> list[dict[str, Any]]:
    """Keep time and severity only; app-controlled tags and messages never enter the export."""
    now = datetime.now(UTC).timestamp()
    entries = []
    for line in raw[-max_bytes:].splitlines()[-200:]:
        match = _LOGCAT_HEADER.match(line)
        if match is None:
            continue
        at = float(match[1])
        if now - window_seconds <= at <= now + 5:
            entries.append({"at": round(at, 3), "priority": match[2].decode()})
    return entries


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
        advanced = value["advancedLogs"]
        snapshot["advancedLogs"] = {key: advanced[key] for key in ("status", "code", "windowSeconds") if key in advanced}
        snapshot["advancedLogs"]["devices"] = [
            {"deviceId": item["deviceId"], **{key: item[key] for key in ("status", "code") if key in item}, "entries": [
                {key: entry[key] for key in ("at", "priority") if key in entry}
                for entry in item.get("entries", [])[:200]
            ]}
            for item in advanced.get("devices", [])[:5]
        ]
    return redact_diagnostics(snapshot)
