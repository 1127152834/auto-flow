"""Reject misleading throughput and row coverage independently of a browser."""

from copy import deepcopy

import pytest

from .harness import GoldenRun, assert_complete_coverage

REF = {
    "projectId": "p",
    "tableId": "t",
    "datasetGeneration": "g",
    "recordKey": {"type": "text", "value": "1"},
}


def detail(ref=REF, *, status="failed", error=None):
    return {
        "task": {"status": status},
        "run": {"error": error},
        "inputSnapshot": {"inputs": [{"recordRef": deepcopy(ref)}]},
    }


def test_thirty_failed_attempts_of_one_row_are_not_thirty_successful_rows():
    run = GoldenRun(
        details=[detail() for _ in range(30)], elapsed_seconds=60, expected_refs=[REF]
    )
    metrics = run.metrics()
    assert metrics["distinct_rows_processed"] == (1, "count")
    assert metrics["tasks_attempted"] == (30, "count")
    assert metrics["rows_succeeded"] == (0, "count")
    assert metrics["throughput_rows_per_min"] == (0, "rows_per_min")
    assert metrics["attempts_per_min"] == (30, "tasks_per_min")
    assert metrics["failure_reason_ratio"] == (0, "ratio")
    with pytest.raises(AssertionError):
        assert_complete_coverage([REF], run.details)


def test_success_requires_verified_output_and_is_counted_once():
    run = GoldenRun(
        details=[detail(status="succeeded")] * 2,
        elapsed_seconds=60,
        expected_refs=[REF],
    )
    assert run.metrics()["rows_succeeded"] == (0, "count")
    run.verified_success_refs.append(REF)
    assert run.metrics()["rows_succeeded"] == (1, "count")
    assert run.metrics()["throughput_rows_per_min"] == (1, "rows_per_min")
    assert run.metrics()["failure_reason_ratio"] == (None, "ratio")


def test_reference_type_and_generation_are_part_of_coverage():
    integer_ref = {**REF, "recordKey": {"type": "integer", "value": "1"}}
    new_generation = {**REF, "datasetGeneration": "g2"}
    refs = [REF, integer_ref, new_generation]
    details = [detail(ref) for ref in refs]
    assert_complete_coverage(refs, details)
    assert GoldenRun(details=details, elapsed_seconds=60, expected_refs=refs).metrics()[
        "distinct_rows_processed"
    ] == (3, "count")
    with pytest.raises(AssertionError):
        assert_complete_coverage(refs, details[:-1])


def test_blank_and_generic_errors_do_not_count_as_explained_failures():
    errors = [
        None,
        {},
        {"message": " "},
        {"message": "工作流节点执行失败"},
        {"message": "工作流未完整成功，请查看已提交的节点记录"},
        {"message": "selector #name was not found"},
    ]
    run = GoldenRun(
        details=[detail(error=error) for error in errors],
        elapsed_seconds=60,
        expected_refs=[REF],
    )
    assert run.metrics()["failure_reason_ratio"] == (1 / 6, "ratio")


def test_incomplete_attempts_or_invalid_timing_are_not_reportable():
    with pytest.raises(ValueError):
        GoldenRun(
            details=[detail(status="running")], elapsed_seconds=60, expected_refs=[REF]
        ).metrics()
    with pytest.raises(ValueError):
        GoldenRun(details=[detail()], elapsed_seconds=0, expected_refs=[REF]).metrics()


def test_golden_save_keeps_pre_execution_source(monkeypatch, tmp_path):
    import hashlib
    import json
    from pathlib import Path

    from tests.benchmarks import report

    from . import harness

    monkeypatch.setattr(report, "_commit", lambda: "before")
    monkeypatch.setattr(report, "_source_dirty", lambda: True)
    manifest = report.build_manifest(
        "golden-v1",
        {
            "rows": 1,
            "valuesSha256": hashlib.sha256(json.dumps(["row"]).encode()).hexdigest(),
        },
        browser_kernel="chromium-test",
    )
    run = GoldenRun(
        details=[detail(status="succeeded")],
        expected_refs=[REF],
        elapsed_seconds=1,
        verified_success_refs=[REF],
        manifest=manifest,
    )
    monkeypatch.setattr(report, "_commit", lambda: "after")
    monkeypatch.setattr(report, "_source_dirty", lambda: False)
    monkeypatch.setattr(
        harness,
        "write_report",
        lambda name, metrics, *, manifest: report.write_report(
            name, metrics, tmp_path, manifest=manifest
        ),
    )
    path = run.save(
        "test",
        browser_kernel=Path("/chromium-test/browser"),
        scenario_version="g2-v1",
        values=["row"],
    )
    metadata = json.loads(path.with_suffix(".manifest.json").read_text())
    assert metadata["commit"] == "before"
    assert metadata["comparable"] is False
    assert metadata["evidence"] == [path.with_suffix(".rows.json").name]
