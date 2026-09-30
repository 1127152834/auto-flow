"""Real-row golden scenario support; never equate attempts with successful rows."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from tests.benchmarks.report import Unit


def _ref_key(ref: dict) -> str:
    # Keep the complete frozen RecordRef including key type and generation.
    return json.dumps(
        {
            key: ref[key]
            for key in ("projectId", "tableId", "datasetGeneration", "recordKey")
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _detail_ref(detail: dict) -> dict:
    inputs = detail["inputSnapshot"]["inputs"]
    if len(inputs) != 1:
        raise ValueError("M0 golden workloads require exactly one input record")
    return inputs[0]["recordRef"]


def assert_complete_coverage(expected_refs: list[dict], details: list[dict]) -> None:
    expected = Counter(_ref_key(ref) for ref in expected_refs)
    actual = Counter(_ref_key(_detail_ref(detail)) for detail in details)
    assert expected and all(count == 1 for count in expected.values()), (
        "Expected unique nonempty inputs"
    )
    assert actual == expected, (
        f"Incomplete or repeated row coverage: expected {expected}, got {actual}"
    )


@dataclass
class GoldenRun:
    details: list[dict[str, Any]]
    elapsed_seconds: float
    expected_refs: list[dict]
    verified_success_refs: list[dict] = field(default_factory=list)
    loop_lag_p99_ms: float = 0.0

    def metrics(self) -> dict[str, tuple[float | None, Unit]]:
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds <= 0:
            raise ValueError("A positive elapsed duration is required")
        if any(
            detail["task"]["status"] not in {"succeeded", "failed", "interrupted"}
            for detail in self.details
        ):
            raise ValueError("Unfinished or cancelled runs are not valid baselines")
        refs = {_ref_key(_detail_ref(detail)) for detail in self.details}
        verified = {_ref_key(ref) for ref in self.verified_success_refs}
        successes = {
            _ref_key(_detail_ref(detail))
            for detail in self.details
            if detail["task"]["status"] == "succeeded"
        } & verified
        failures = [
            detail for detail in self.details if detail["task"]["status"] != "succeeded"
        ]
        generic = {"工作流节点执行失败", "工作流节点执行超时", "工作流执行失败"}
        explained = 0
        for detail in failures:
            error = (
                detail.get("run", {}).get("error") or detail["task"].get("error") or {}
            )
            message = error.get("message", "").strip()
            explained += bool(message and message not in generic)
        return {
            "tasks_attempted": (len(self.details), "count"),
            "distinct_rows_processed": (len(refs), "count"),
            "rows_succeeded": (len(successes), "count"),
            "tasks_failed": (len(failures), "count"),
            "throughput_rows_per_min": (
                len(successes) * 60 / self.elapsed_seconds,
                "rows_per_min",
            ),
            "attempts_per_min": (
                len(self.details) * 60 / self.elapsed_seconds,
                "tasks_per_min",
            ),
            "failure_reason_ratio": (
                explained / len(failures) if failures else None,
                "ratio",
            ),
            "loop_lag_p99_ms": (self.loop_lag_p99_ms, "ms"),
        }
