"""Unified node error policy (remediation M2 R2-08/R2-09).

Only an explicit ``{"version": 2, ...}`` policy changes how a failed node is
handled. Settings saved by older editors (``errorPolicy.mode``, ``retryCount``,
``timeoutAction`` ...) are converted to a *candidate* the editor can show and the
user can enable; reading or opening a document never activates them.
The editor implements the same conversion (tests share one fixture file).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

OnError = Literal["stop", "continue", "retry", "goto"]
MAX_RETRIES = 10
MAX_DELAY_SECONDS = 3600
LEGACY_EXPONENTIAL_CAP = 60


@dataclass(frozen=True)
class ErrorPolicy:
    on_error: OnError
    max_retries: int
    backoff_kind: Literal["fixed", "exponential"]
    initial_seconds: float
    max_seconds: float
    retry_on: Literal["any", "timeout"]
    goto_node_id: str | None
    on_exhausted: Literal["stop", "continue"]


def _config(data: Mapping[str, Any]) -> dict[str, Any]:
    nested = data.get("config")
    return {**data, **nested} if isinstance(nested, Mapping) else dict(data)


def active_policy(data: Mapping[str, Any]) -> ErrorPolicy | None:
    """The policy that takes effect, or None (the node stops the flow as before)."""
    raw = _config(data).get("errorPolicy")
    if not isinstance(raw, Mapping) or raw.get("version") != 2:
        return None
    on_error = raw.get("onError")
    retries = raw.get("maxRetries", 0)
    raw_backoff = raw.get("backoff")
    backoff: Mapping[str, Any] = raw_backoff if isinstance(raw_backoff, Mapping) else {}
    kind = backoff.get("kind", "fixed")
    initial = backoff.get("initialSeconds", 0)
    ceiling = backoff.get("maxSeconds", initial)
    retry_on = raw.get("retryOn", "any")
    goto = raw.get("gotoNodeId")
    exhausted = raw.get("onExhausted", "stop")
    numbers_ok = all(
        isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= MAX_DELAY_SECONDS
        for value in (initial, ceiling)
    )
    if (
        on_error not in {"stop", "continue", "retry", "goto"}
        or type(retries) is not int or not 0 <= retries <= MAX_RETRIES
        or kind not in {"fixed", "exponential"} or not numbers_ok
        or retry_on not in {"any", "timeout"}
        or exhausted not in {"stop", "continue"}
        or (on_error == "goto" and (not isinstance(goto, str) or not goto))
        or (on_error == "retry" and retries < 1)
    ):
        return None
    return ErrorPolicy(
        on_error, retries, kind, float(initial), float(max(ceiling, initial)), retry_on,
        goto if on_error == "goto" else None, exhausted,
    )


def retry_delay(policy: ErrorPolicy, attempt: int) -> float:
    """Seconds to wait before retry number ``attempt`` (1-based)."""
    if policy.backoff_kind == "fixed":
        return float(policy.initial_seconds)
    return float(min(policy.max_seconds, policy.initial_seconds * (2 ** (attempt - 1))))


def candidate_policy(data: Mapping[str, Any]) -> dict[str, Any] | None:
    """Convert old, never-executed settings into a version-2 candidate; None when nothing to offer."""
    config = _config(data)
    old = config.get("errorPolicy")
    if isinstance(old, Mapping) and old.get("version") == 2:
        return None

    def build(on_error: str, retries: int = 0, kind: str = "fixed", initial: float = 0, ceiling: float | None = None,
              retry_on: str = "any", goto: str | None = None, exhausted: str = "stop") -> dict[str, Any]:
        return {
            "version": 2, "onError": on_error, "maxRetries": retries,
            "backoff": {"kind": kind, "initialSeconds": initial, "maxSeconds": initial if ceiling is None else ceiling, "jitter": False},
            "retryOn": retry_on, "gotoNodeId": goto, "onExhausted": exhausted,
        }

    if isinstance(old, Mapping) and old.get("mode") not in (None, "stop"):
        mode = old.get("mode")
        retries = _int(old.get("maxRetries"), 1)
        interval = _number(old.get("interval"))
        exhausted = "continue" if old.get("onExhausted") == "continue" else "stop"
        if mode == "continue":
            return build("continue")
        if mode == "retry-self":
            return build("retry", retries, initial=interval, exhausted=exhausted)
        if mode == "retry-from" and isinstance(old.get("targetId"), str) and old["targetId"]:
            return build("goto", retries, initial=interval, goto=old["targetId"], exhausted=exhausted)
    retries = _int(config.get("retryCount"), 0)
    if retries > 0:
        delay = _number(config.get("retryDelay"))
        exponential = config.get("retryBackoff") == "exponential"
        exhausted = "continue" if config.get("retryExhaustedAction") in ("skip", "continue") else "stop"
        return build(
            "retry", min(retries, MAX_RETRIES), "exponential" if exponential else "fixed", delay,
            LEGACY_EXPONENTIAL_CAP if exponential else delay, exhausted=exhausted,
        )
    if config.get("timeoutAction") == "skip":
        return build("continue", retry_on="timeout")
    return None


def _int(value: Any, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _number(value: Any) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return max(0, min(value, MAX_DELAY_SECONDS))
