from tests.fixtures import ci_annotations


def test_failures_are_grouped_into_bounded_escaped_annotations():
    failures = [(f"tests/test_{i}.py::t [call]", "boom 100%\nsecond line") for i in range(60)]
    annotations = ci_annotations.render(failures)
    assert annotations
    assert all(a.startswith("::error title=") for a in annotations)
    assert all(len(a) < 4_000 for a in annotations)
    assert all("\n" not in a for a in annotations)
    assert "100%25" in annotations[0]
    assert "tests/test_0.py::t [call]" in annotations[0]


def test_overflow_is_counted_not_silently_dropped():
    failures = [(f"tests/test_{i}.py::t [call]", "x" * 590) for i in range(200)]
    annotations = ci_annotations.render(failures)
    assert len(annotations) == ci_annotations.MAX_ANNOTATIONS + 1
    assert annotations[-1].startswith("::error title=more failed tests::")


def test_no_failures_means_no_annotations():
    assert ci_annotations.render([]) == []


def test_a_real_pytest_run_prints_the_annotation_at_the_start_of_a_line(tmp_path):
    """print() from a session hook is swallowed by capture; a real run must still show it."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    (tmp_path / "test_boom.py").write_text("def test_boom():\n    assert 1 == 2\n", encoding="utf-8")
    backend = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "tests.fixtures.ci_annotations", "-p", "no:cacheprovider"],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_ACTIONS": "true", "PYTHONPATH": os.pathsep.join([str(backend), os.environ.get("PYTHONPATH", "")])},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    lines = result.stdout.splitlines()
    assert any(line.startswith("::error title=failed tests (1/1)::") and "test_boom" in line for line in lines), result.stdout
