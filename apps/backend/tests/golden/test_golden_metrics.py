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
        {"message": "selector #name was not found"},
    ]
    run = GoldenRun(
        details=[detail(error=error) for error in errors],
        elapsed_seconds=60,
        expected_refs=[REF],
    )
    assert run.metrics()["failure_reason_ratio"] == (0.2, "ratio")


def test_incomplete_attempts_or_invalid_timing_are_not_reportable():
    with pytest.raises(ValueError):
        GoldenRun(
            details=[detail(status="running")], elapsed_seconds=60, expected_refs=[REF]
        ).metrics()
    with pytest.raises(ValueError):
        GoldenRun(details=[detail()], elapsed_seconds=0, expected_refs=[REF]).metrics()
