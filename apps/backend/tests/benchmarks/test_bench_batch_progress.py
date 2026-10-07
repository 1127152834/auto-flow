"""Smoke test: the batch progress benchmark seeds exactly the rows it reports and measures a real call."""

import pytest

from . import bench_batch_progress

pytestmark = pytest.mark.benchmark


def test_batch_progress_benchmark_reports_actual_rows_and_positive_timings():
    metrics = bench_batch_progress.run(150)
    assert metrics["rows"] == (150, "count")
    assert metrics["progress_ms_p50"][0] > 0 and metrics["loop_lag_samples"][0] > 0


def test_batch_progress_benchmark_rejects_empty_workload(tmp_path):
    with pytest.raises(ValueError):
        bench_batch_progress._seed(tmp_path, 0)
