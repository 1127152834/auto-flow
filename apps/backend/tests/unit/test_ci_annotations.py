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
