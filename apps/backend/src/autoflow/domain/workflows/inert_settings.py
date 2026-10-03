"""Settings the Studio saves but the runtime does not execute yet (remediation M1, R1-02 / spec §5.1).

Mirrors apps/desktop/src/renderer/domains/workflows/lib/inertSettings.ts. Since M2 R2-12 these old
keys are only migration candidates for the version-2 node error policy; the hint points there.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

INERT_SETTING_KEYS = (
    "errorPolicy", "retryCount", "retryDelay", "retryBackoff",
    "retryExhaustedAction", "timeoutAction", "onTimeout",
)
LOOP_TYPES = frozenset({"loop", "foreach", "foreach_dict", "infinite_loop"})
LABELS = {
    "errorPolicy": "出错时", "retryCount": "重试次数", "retryDelay": "重试间隔",
    "retryBackoff": "退避策略", "retryExhaustedAction": "重试耗尽后",
    "timeoutAction": "运行超时后", "onTimeout": "循环超时后",
}


def inert_keys(data: Mapping[str, Any], module_type: str) -> list[str]:
    nested = data.get("config")
    config = {**data, **nested} if isinstance(nested, Mapping) else dict(data)
    keys: list[str] = []
    policy = config.get("errorPolicy")
    if isinstance(policy, Mapping) and policy.get("mode") not in (None, "stop"):
        keys.append("errorPolicy")
    try:
        retry_count = float(config.get("retryCount") or 0)
    except (TypeError, ValueError):
        retry_count = 0
    if retry_count > 0:
        keys.append("retryCount")
        keys.extend(
            key for key in ("retryDelay", "retryBackoff", "retryExhaustedAction")
            if config.get(key) not in (None, "")
        )
    if config.get("timeoutAction") in ("retry", "skip"):
        keys.append("timeoutAction")
    if module_type in LOOP_TYPES and config.get("onTimeout") in ("retry", "skip"):
        keys.append("onTimeout")
    return keys


def describe_inert_keys(label: str, keys: list[str]) -> str:
    return f"「{label}」的以下旧设置不会自动生效，可在「出错时」查看转换建议并启用：{'、'.join(LABELS[key] for key in keys)}"
