"""Input matching rules for a draft input plan (remediation M5 5B-A4, B4)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

HIDDEN = "已隐藏"
SAMPLE_ROWS = 3


def unprocessed_count(
    matched: Iterable[tuple[str, str]], succeeded: set[tuple[str, str]], occupied: set[tuple[str, str]]
) -> int:
    """Matched rows (record key type, value) that have no succeeded processing record and are not held by a task."""
    return sum(1 for key in matched if key not in succeeded and key not in occupied)


def sample_row(
    bindings: Iterable[Mapping[str, Any]], values: Mapping[str, Any], *, sensitive_fields: set[str]
) -> dict[str, Any]:
    """One sample row: only the bound fields, keyed by the input's own field name; sensitive ones hidden."""
    row: dict[str, Any] = {}
    for binding in bindings:
        value = values.get(binding["fieldRef"]["fieldId"])
        row[binding["inputFieldAlias"]] = HIDDEN if value is not None and binding.get("signatureField") in sensitive_fields else value
    return row
