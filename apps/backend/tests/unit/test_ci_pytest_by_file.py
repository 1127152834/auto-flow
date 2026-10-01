"""The per-file diagnostic runner must name hung and failing files, not hide them."""

import sys
from pathlib import Path

from scripts import ci_pytest_by_file as runner

PY = sys.executable


def test_a_hung_file_is_killed_and_reported_as_timeout(tmp_path):
    target = tmp_path / "test_hang.py"
    target.write_text("")
    result = runner.run_file(
        target, 1.0, [PY, "-c", "import time; time.sleep(60)", "--"]
    )
    assert result.status == "timeout"
    assert result.code is None
    assert 0.9 <= result.seconds < 20


def test_exit_codes_map_to_status(tmp_path):
    target = tmp_path / "test_x.py"
    target.write_text("")
    ok = runner.run_file(target, 30, [PY, "-c", "raise SystemExit(0)"])
    nothing_collected = runner.run_file(target, 30, [PY, "-c", "raise SystemExit(5)"])
    failed = runner.run_file(
        target,
        30,
        [PY, "-c", "print('FAILED tests/x.py::test_y - boom'); raise SystemExit(1)"],
    )
    assert (ok.status, nothing_collected.status, failed.status) == (
        "passed",
        "passed",
        "failed",
    )
    assert failed.code == 1
    assert "FAILED tests/x.py::test_y - boom" in failed.detail


def test_report_lists_problem_files_and_the_slowest(tmp_path):
    results = [
        runner.FileResult("a.py", "passed", 1.0, 0),
        runner.FileResult("b.py", "timeout", 900.0, None, "b.py::test_hangs"),
        runner.FileResult("c.py", "failed", 5.0, 1, "FAILED c.py::test_c"),
    ]
    text, annotations = runner.build_report(results, slowest=2)
    assert "3 files, 1 passed, 1 failed, 1 timed out" in text
    assert "`b.py` timeout after 900s: b.py::test_hangs" in text
    assert annotations[0].startswith(
        "::error title=backend files failed or timed out::"
    )
    assert "b.py::test_hangs" in annotations[0]
    assert annotations[1] == "::notice title=slowest backend files::b.py:900s; c.py:5s"


def test_a_clean_run_has_no_error_annotation():
    _, annotations = runner.build_report([runner.FileResult("a.py", "passed", 1.0, 0)])
    assert all(not item.startswith("::error") for item in annotations)


def test_discovery_skips_caches_and_sorts(tmp_path):
    (tmp_path / "unit").mkdir()
    (tmp_path / "unit" / "test_b.py").write_text("")
    (tmp_path / "test_a.py").write_text("")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "test_c.py").write_text("")
    (tmp_path / "helper.py").write_text("")
    found = [
        Path(p).relative_to(tmp_path).as_posix() for p in runner.discover(tmp_path)
    ]
    assert found == ["test_a.py", "unit/test_b.py"]
