from collections import Counter

import pytest

from scripts.check_strict_types import diagnostics


def test_strict_gate_tracks_symbol_message_and_multiplicity_without_line_churn(tmp_path):
    source = tmp_path / "example.py"
    source.write_text("def first():\n    pass\ndef second():\n    pass\n")
    old = "example.py:1: error: Function is missing a return type annotation  [no-untyped-def]"
    baseline = diagnostics(old, tmp_path)
    source.write_text("\n\ndef first():\n    pass\ndef second():\n    pass\n")
    moved = old.replace(":1:", ":3:")
    assert diagnostics(moved, tmp_path) == baseline
    assert (diagnostics(moved + "\n" + moved, tmp_path) - baseline).total() == 1
    other = moved.replace(":3:", ":5:")
    assert (diagnostics(other, tmp_path) - baseline).total() == 1
    assert (diagnostics(moved.replace("return type", "parameter"), tmp_path) - baseline).total() == 1
    assert diagnostics("Success: no issues found", tmp_path) == Counter()
    with pytest.raises(ValueError, match="Unrecognized"):
        diagnostics("example.py: error: unknown diagnostic format", tmp_path)
