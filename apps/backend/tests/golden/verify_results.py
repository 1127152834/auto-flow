"""Independent check of golden result files after a run (M0 AC0-07).

The pytest assertions prove behaviour while the run is alive. This verifier
re-reads the files that the run left behind, so that the uploaded evidence can
be audited without trusting the run's own exit status. It never rewrites data.

Usage: python -m tests.golden.verify_results <results-dir> --rows N [--commit SHA]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# scenario report prefix -> number of rows that are expected to fail by design
EXPECTED_FAILURES = {"g2-scrape": 2, "g3-click": 1}
EXPECTED_SCENARIO_VERSION = {"g2-scrape": "g2-scrape-v1", "g3-click": "g3-click-v1"}


def _load(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        errors.append(f"{path.name}: unreadable ({error})")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path.name}: expected a JSON object")
        return None
    return data


def _ref_key(ref: Any) -> str:
    return json.dumps(ref, sort_keys=True, ensure_ascii=False)


def _detail_ref(detail: dict[str, Any]) -> Any:
    return detail["inputSnapshot"]["inputs"][0]["recordRef"]


def verify_scenario(
    report_path: Path, prefix: str, rows: int, commit: str | None
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    summary: dict[str, Any] = {"report": report_path.name}
    report = _load(report_path, errors)
    manifest = _load(report_path.with_suffix(".manifest.json"), errors)
    evidence = _load(report_path.with_suffix(".rows.json"), errors)
    if report is None or manifest is None or evidence is None:
        return errors, summary

    source_before = manifest.get("sourceBefore") or {}
    source_after = manifest.get("sourceAfter") or {}
    if manifest.get("comparable") is not True:
        errors.append(f"{prefix}: manifest.comparable is not true")
    if source_before.get("dirty") is not False:
        errors.append(f"{prefix}: source was dirty or unknown before the run")
    if source_before != source_after:
        errors.append(f"{prefix}: source changed during the run")
    if commit and source_before.get("commit") != commit:
        errors.append(
            f"{prefix}: commit {source_before.get('commit')} is not the requested {commit}"
        )
    if report.get("commit") != source_before.get("commit"):
        errors.append(f"{prefix}: report commit differs from the manifest")
    if manifest.get("scenarioVersion") != EXPECTED_SCENARIO_VERSION[prefix]:
        errors.append(f"{prefix}: unexpected scenarioVersion")
    if manifest.get("evidence") != [report_path.with_suffix(".rows.json").name]:
        errors.append(f"{prefix}: manifest does not reference its rows evidence")
    if manifest.get("reports") != [report_path.name]:
        errors.append(f"{prefix}: manifest does not reference its report")
    kernel = str(manifest.get("browserKernel", ""))
    if not kernel.startswith("chromium-"):
        errors.append(f"{prefix}: browserKernel {kernel!r} is not a real kernel")
    if (manifest.get("dataset") or {}).get("rows") != rows:
        errors.append(
            f"{prefix}: dataset rows {(manifest.get('dataset') or {}).get('rows')} != {rows}"
        )
    if manifest.get("repetitions") != 1:
        errors.append(f"{prefix}: expected a single repetition")

    expected_refs = evidence.get("expectedRefs") or []
    details = evidence.get("details") or []
    verified = evidence.get("verifiedSuccessRefs") or []
    expected_keys = {_ref_key(ref) for ref in expected_refs}
    if len(expected_refs) != rows or len(expected_keys) != rows:
        errors.append(f"{prefix}: expectedRefs is not {rows} distinct rows")
    try:
        attempted = {_ref_key(_detail_ref(detail)) for detail in details}
    except (KeyError, IndexError, TypeError):
        errors.append(f"{prefix}: a detail has no input record reference")
        attempted = set()
    if attempted != expected_keys:
        errors.append(
            f"{prefix}: processed rows differ from selected rows "
            f"(missing {len(expected_keys - attempted)}, extra {len(attempted - expected_keys)})"
        )
    if not {_ref_key(ref) for ref in verified} <= expected_keys:
        errors.append(f"{prefix}: a verified success is not a selected row")

    metrics = {
        name: item.get("value") for name, item in (report.get("metrics") or {}).items()
    }
    expected_failed = EXPECTED_FAILURES[prefix]
    checks = {
        "distinct_rows_processed": rows,
        "rows_succeeded": rows - expected_failed,
        "tasks_failed": expected_failed,
    }
    for name, expected in checks.items():
        if metrics.get(name) != expected:
            errors.append(
                f"{prefix}: {name} is {metrics.get(name)}, expected {expected}"
            )
    if len(verified) != rows - expected_failed:
        errors.append(
            f"{prefix}: {len(verified)} verified successes, expected {rows - expected_failed}"
        )
    # The ratio is the baseline coverage of specific failure reasons. Today's
    # product reports generic reasons (0.0, see the M0 baseline record), which
    # M1 must raise, so the check is that the measurement exists and is valid.
    ratio = metrics.get("failure_reason_ratio")
    if not isinstance(ratio, (int, float)) or not 0 <= ratio <= 1:
        errors.append(f"{prefix}: failure_reason_ratio {ratio!r} is not within [0, 1]")
    for name in ("throughput_rows_per_min", "attempts_per_min", "loop_lag_p99_ms"):
        value = metrics.get(name)
        if not isinstance(value, (int, float)) or value < 0:
            errors.append(f"{prefix}: {name} is not a non-negative number")
    summary.update(
        {
            "commit": source_before.get("commit"),
            "kernel": kernel,
            "metrics": metrics,
            "hardware": manifest.get("hardware"),
        }
    )
    return errors, summary


def verify(
    results: Path, rows: int, commit: str | None = None
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    summaries: list[dict[str, Any]] = []
    for prefix in EXPECTED_FAILURES:
        reports = sorted(
            path
            for path in results.glob(f"{prefix}-*.json")
            if not path.name.endswith((".manifest.json", ".rows.json"))
        )
        if len(reports) != 1:
            errors.append(
                f"{prefix}: expected exactly one report, found {len(reports)}"
            )
            continue
        scenario_errors, summary = verify_scenario(reports[0], prefix, rows, commit)
        errors.extend(scenario_errors)
        summaries.append({"scenario": prefix, **summary})
    return errors, summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA"))
    args = parser.parse_args(argv)
    errors, summaries = verify(args.results, args.rows, args.commit)
    lines = [f"## Golden evidence check ({args.rows} rows)", ""]
    for summary in summaries:
        metrics = summary.get("metrics") or {}
        lines.append(
            f"- **{summary['scenario']}** `{summary.get('commit')}` {summary.get('kernel')}: "
            + ", ".join(f"{key}={metrics[key]}" for key in sorted(metrics))
        )
        hardware = summary.get("hardware") or {}
        lines.append(f"  - {hardware.get('os')} / {hardware.get('logicalCpu')} CPU")
    lines += ["", "Result: " + ("FAILED" if errors else "all checks passed")]
    lines += [f"- {error}" for error in errors]
    text = "\n".join(lines)
    print(text)
    for summary in summaries:
        print(
            f"::notice title=golden {summary['scenario']}::"
            + json.dumps(summary.get("metrics"), sort_keys=True)
        )
    for error in errors:
        print(f"::error title=golden evidence::{error}")
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        with open(destination, "a", encoding="utf-8") as output:
            output.write(text + "\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
