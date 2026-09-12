from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("verify-openrouter-live.py")
SPEC = importlib.util.spec_from_file_location("verify_openrouter_live", SCRIPT)
assert SPEC and SPEC.loader
live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live)


def test_failed_write_ref_is_still_cleaned(monkeypatch: pytest.MonkeyPatch) -> None:
    report = live.Report()
    tracking = object.__new__(live.TrackingCredentialStore)
    tracking.report = report
    stored: set[str] = set()

    def write_then_maybe_fail(_store: object, key: str, _value: bytes) -> None:
        stored.add(key)
        if key.endswith("orphan"):
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(live.SystemCredentialStore, "write", write_then_maybe_fail)
    tracking.write("model-provider/live-provider", b"synthetic")
    with pytest.raises(RuntimeError, match="synthetic failure"):
        tracking.write("model-provider/orphan", b"synthetic")

    class FakeCleanupStore:
        def delete(self, key: str) -> None:
            stored.discard(key)

        def read(self, key: str) -> bytes | None:
            return b"synthetic" if key in stored else None

    cleanup = FakeCleanupStore()
    live.cleanup_refs(report, cleanup)

    assert report.refs == ["model-provider/live-provider", "model-provider/orphan"]
    assert stored == set()
    assert report.steps[-1] == {
        "name": "finally_credential_cleanup",
        "status": "PASS",
        "code": "OK",
        "count": 2,
    }
