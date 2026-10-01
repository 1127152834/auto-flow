"""The post-run verifier must reject evidence that the run itself would accept."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.benchmarks import report

from . import harness, verify_results
from .harness import GoldenRun

KERNEL = Path("/kernels/chromium-145.0.7632.109.2/Chromium")
SHA = "a" * 40


def _ref(index: int) -> dict:
    return {
        "projectId": "p",
        "tableId": "t",
        "datasetGeneration": "g",
        "recordKey": {"type": "text", "value": f"row-{index}"},
    }


def _detail(index: int, *, ok: bool) -> dict:
    return {
        "task": {"status": "succeeded" if ok else "failed"},
        "run": {"error": None if ok else {"message": "页面加载超时"}},
        "inputSnapshot": {"inputs": [{"recordRef": _ref(index)}]},
    }


def _write(
    monkeypatch, directory: Path, name: str, version: str, rows: int, failed: int
) -> Path:
    values = [f"row-{i}" for i in range(rows)]
    monkeypatch.setattr(report, "_commit", lambda: SHA)
    monkeypatch.setattr(report, "_source_dirty", lambda: False)
    manifest = report.build_manifest(
        version,
        {
            "rows": rows,
            "valuesSha256": hashlib.sha256(json.dumps(values).encode()).hexdigest(),
        },
        browser_kernel="chromium-145.0.7632.109.2",
        concurrency=2,
    )
    # os.sysconf does not exist on Windows; memory is not what these tests check.
    manifest["hardware"]["totalMemoryBytes"] = 8 * 1024**3
    run = GoldenRun(
        details=[_detail(i, ok=i >= failed) for i in range(rows)],
        expected_refs=[_ref(i) for i in range(rows)],
        elapsed_seconds=10,
        verified_success_refs=[_ref(i) for i in range(failed, rows)],
        manifest=manifest,
    )
    monkeypatch.setattr(
        harness,
        "write_report",
        lambda n, m, *, manifest: report.write_report(
            n, m, directory, manifest=manifest
        ),
    )
    return run.save(
        name, browser_kernel=KERNEL, scenario_version=version, values=values
    )


@pytest.fixture
def results(tmp_path, monkeypatch):
    _write(monkeypatch, tmp_path, "g2-scrape", "g2-scrape-v1", 30, 2)
    _write(monkeypatch, tmp_path, "g3-click", "g3-click-v1", 30, 1)
    _write(monkeypatch, tmp_path, "g3-enter", "g3-enter-v1", 30, 1)
    return tmp_path


def _edit(path: Path, change) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def _find(results: Path, prefix: str, suffix: str = ".json") -> Path:
    return next(
        p
        for p in results.glob(f"{prefix}-*{suffix}")
        if suffix != ".json" or not p.name.endswith((".manifest.json", ".rows.json"))
    )


def test_complete_evidence_passes(results):
    errors, summaries = verify_results.verify(results, 30, SHA)
    assert errors == []
    assert [s["scenario"] for s in summaries] == ["g2-scrape", "g3-click", "g3-enter"]


def test_wrong_commit_is_rejected(results):
    errors, _ = verify_results.verify(results, 30, "b" * 40)
    assert any("is not the requested" in e for e in errors)


def test_missing_scenario_report_is_rejected(results):
    for path in list(results.glob("g3-click-*")):
        path.unlink()
    errors, _ = verify_results.verify(results, 30, SHA)
    assert any("g3-click: expected exactly one report" in e for e in errors)


def test_the_enter_version_is_verified_with_its_own_scenario_version(results):
    manifest = _find(results, "g3-enter", ".manifest.json")
    _edit(manifest, lambda d: d.update(scenarioVersion="g3-click-v1"))
    errors, _ = verify_results.verify(results, 30, SHA)
    assert any("g3-enter: unexpected scenarioVersion" in e for e in errors)


def test_row_count_must_match_the_requested_rows(results):
    errors, _ = verify_results.verify(results, 101, SHA)
    assert any("dataset rows 30 != 101" in e for e in errors)


def test_dirty_or_changed_source_is_rejected(results):
    manifest = _find(results, "g2-scrape", ".manifest.json")
    _edit(manifest, lambda d: d["sourceAfter"].update(dirty=True, commit="c" * 40))
    errors, _ = verify_results.verify(results, 30, SHA)
    assert any("source changed during the run" in e for e in errors)


def test_a_missing_row_is_reported_even_if_counts_look_right(results):
    rows = _find(results, "g3-click", ".rows.json")

    def drop_and_duplicate(data):
        data["details"][5] = data["details"][4]

    _edit(rows, drop_and_duplicate)
    errors, _ = verify_results.verify(results, 30, SHA)
    assert any("processed rows differ from selected rows" in e for e in errors)


def test_unverified_success_count_is_rejected(results):
    rows = _find(results, "g2-scrape", ".rows.json")
    _edit(rows, lambda d: d["verifiedSuccessRefs"].pop())
    errors, _ = verify_results.verify(results, 30, SHA)
    assert any("verified successes" in e for e in errors)


def test_a_fake_kernel_name_is_rejected(results):
    manifest = _find(results, "g2-scrape", ".manifest.json")
    _edit(manifest, lambda d: d.update(browserKernel="not-applicable"))
    errors, _ = verify_results.verify(results, 30, SHA)
    assert any("is not a real kernel" in e for e in errors)


def test_measured_zero_failure_reason_coverage_is_a_valid_baseline(results):
    report_path = _find(results, "g3-click")

    def generic(data):
        data["metrics"]["failure_reason_ratio"]["value"] = 0.0

    _edit(report_path, generic)
    errors, _ = verify_results.verify(results, 30, SHA)
    assert errors == []


def test_a_missing_failure_reason_measurement_is_rejected(results):
    report_path = _find(results, "g2-scrape")

    def missing(data):
        data["metrics"]["failure_reason_ratio"]["value"] = None

    _edit(report_path, missing)
    errors, _ = verify_results.verify(results, 30, SHA)
    assert any("failure_reason_ratio" in e for e in errors)


def test_cli_exit_code_and_summary_file(results, tmp_path, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert verify_results.main([str(results), "--rows", "30", "--commit", SHA]) == 0
    assert "all checks passed" in summary.read_text(encoding="utf-8")
    assert verify_results.main([str(results), "--rows", "31", "--commit", SHA]) == 1
    assert "::error title=golden evidence::" in capsys.readouterr().out
