"""Real SQLite benchmarks and trustworthy, self-describing result artifacts."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from autoflow.infrastructure.database.project_data_models import DataRecordRow

from . import bench_claims, report

pytestmark = pytest.mark.benchmark


def test_claim_benchmark_measures_both_orderings_and_actual_row_count(tmp_path):
    factory, _, _, _ = bench_claims._seed(tmp_path, 200)
    try:
        with factory() as session:
            assert (
                session.scalar(select(func.count()).select_from(DataRecordRow)) == 200
            )
    finally:
        factory.dispose()
    metrics = bench_claims.run(200)
    assert metrics["rows"] == (200, "count")
    for name in ("claim_ms_key_order", "claim_ms_field_order"):
        assert metrics[name][0] > 0
        assert metrics[name][1] == "ms"


@pytest.mark.parametrize("rows", [0, -1])
def test_claim_benchmark_rejects_empty_or_negative_workload(rows):
    with pytest.raises(ValueError):
        bench_claims.run(rows)


def test_reports_pair_metrics_with_manifest_and_preserve_null(tmp_path):
    manifest = report.build_manifest("claims-v1", {"rows": 200})
    path = report.write_report(
        "claims",
        {"rows": (200, "count"), "failure_reason_ratio": (None, "ratio")},
        tmp_path / "nested",
        manifest=manifest,
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    metadata = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert set(raw) == {"schemaVersion", "commit", "platform", "metrics"}
    assert raw["metrics"]["failure_reason_ratio"] == {"value": None, "unit": "ratio"}
    assert metadata["reports"] == [path.name]
    assert metadata["commit"] == raw["commit"]
    assert metadata["scenarioVersion"] == "claims-v1"
    assert metadata["executionProfile"] == "offline-v1"
    assert metadata["dataset"] == {"rows": 200}
    assert metadata["concurrency"] == metadata["repetitions"] == 1
    assert metadata["browserKernel"] == "not-applicable"
    assert "logicalCpu" in metadata["hardware"]
    assert "totalMemoryBytes" in metadata["hardware"]
    assert metadata["pythonVersion"] and metadata["sqliteVersion"]
    assert "commit" not in manifest  # writer does not mutate shared metadata


def test_report_survives_missing_git_and_marks_unknown_incomparable(
    monkeypatch, tmp_path
):
    def no_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(report.subprocess, "run", no_git)
    path = report.write_report(
        "offline",
        {"rows": (1, "count")},
        tmp_path,
        manifest=report.build_manifest("claims-v1", {"rows": 1}),
    )
    assert json.loads(path.read_text(encoding="utf-8"))["commit"] == "unknown"
    assert (
        json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))["comparable"]
        is False
    )


def test_report_uses_repository_commit_when_launched_elsewhere(monkeypatch, tmp_path):
    expected = report.build_report({})["commit"]
    assert expected != "unknown"
    monkeypatch.chdir(tmp_path)
    assert report.build_report({})["commit"] == expected


def test_incomplete_manifest_is_rejected_without_writing_results(tmp_path):
    with pytest.raises(ValueError):
        report.write_report("bad", {"rows": (1, "count")}, tmp_path, manifest={})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("metric", [(float("nan"), "ms"), (1, "invalid"), (None, "ms")])
def test_invalid_metric_cannot_produce_misleading_json(metric):
    with pytest.raises(ValueError):
        report.build_report({"invalid": metric})


def test_concurrent_reports_do_not_overwrite_each_other(tmp_path):
    manifest = report.build_manifest("claims-v1", {"rows": 1})

    def write(index):
        return report.write_report(
            "same", {"rows": (index, "count")}, tmp_path, manifest=manifest
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(write, range(12)))
    assert len(set(paths)) == 12
    assert {
        json.loads(p.read_text(encoding="utf-8"))["metrics"]["rows"]["value"] for p in paths
    } == set(range(12))
    assert all(p.with_suffix(".manifest.json").is_file() for p in paths)


def test_uncommitted_source_is_identified_and_not_comparable(monkeypatch, tmp_path):
    monkeypatch.setattr(report, "_source_dirty", lambda: True, raising=False)
    path = report.write_report(
        "dirty",
        {"rows": (1, "count")},
        tmp_path,
        manifest=report.build_manifest("claims-v1", {"rows": 1}),
    )
    metadata = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert metadata["sourceDirty"] is True
    assert metadata["comparable"] is False


def test_runtime_overhead_benchmark_records_actual_completed_nodes():
    from . import bench_runtime_overhead

    metrics = bench_runtime_overhead.run(50)
    assert metrics["nodes_executed"] == (250, "count")
    assert metrics["framework_ms_per_node"][0] > 0
    assert metrics["events_per_node"][0] >= 4


def test_runtime_overhead_rejects_successful_but_empty_workload(monkeypatch):
    from . import bench_runtime_overhead

    monkeypatch.setattr(
        bench_runtime_overhead, "g4_document", lambda _: {"nodes": [], "edges": []}
    )
    with pytest.raises(RuntimeError):
        bench_runtime_overhead.run(2)


def test_runtime_overhead_rejects_zero_iterations():
    from . import bench_runtime_overhead

    with pytest.raises(ValueError):
        bench_runtime_overhead.run(0)


def test_event_commit_benchmark_reports_real_commit_percentiles():
    from . import bench_event_commit

    metrics = bench_event_commit.run(50)
    assert metrics["events"] == (50, "count")
    assert metrics["event_commit_ms_p99"][0] >= metrics["event_commit_ms_p50"][0] > 0


def test_event_commit_rejects_empty_sample():
    from . import bench_event_commit

    with pytest.raises(ValueError):
        bench_event_commit.run(0)


@pytest.mark.parametrize(
    "initial_dirty, final_commit, final_dirty, comparable",
    [
        (True, "B", False, False),
        (False, "B", False, False),
        (False, "A", True, False),
        (False, "A", False, True),
    ],
)
def test_report_preserves_measured_source_not_only_save_time_state(
    monkeypatch, tmp_path, initial_dirty, final_commit, final_dirty, comparable
):
    monkeypatch.setattr(report, "_commit", lambda: "A")
    monkeypatch.setattr(report, "_source_dirty", lambda: initial_dirty)
    manifest = report.build_manifest("test-v1", {"rows": 1})
    # Keep hardware known so only the source consistency gate is exercised.
    manifest["hardware"] = {
        "os": "test",
        "arch": "test",
        "logicalCpu": 1,
        "totalMemoryBytes": 1,
    }
    monkeypatch.setattr(report, "_commit", lambda: final_commit)
    monkeypatch.setattr(report, "_source_dirty", lambda: final_dirty)
    path = report.write_report(
        "changed", {"rows": (1, "count")}, tmp_path, manifest=manifest
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    metadata = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert raw["commit"] == "A"
    assert metadata["sourceBefore"] == {"commit": "A", "dirty": initial_dirty}
    assert metadata["sourceAfter"] == {"commit": final_commit, "dirty": final_dirty}
    assert metadata["comparable"] is comparable
