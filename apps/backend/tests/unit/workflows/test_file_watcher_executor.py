from __future__ import annotations

from autoflow.application.workflows.executors.file_watcher import _changes


def test_file_watcher_detects_source_event_types_and_pattern() -> None:
    previous = {
        "/watch/modified.txt": (1.0, 1),
        "/watch/deleted.txt": (1.0, 1),
        "/watch/ignored.log": (1.0, 1),
    }
    current = {
        "/watch/modified.txt": (2.0, 2),
        "/watch/created.txt": (2.0, 1),
        "/watch/ignored.log": (2.0, 2),
    }

    assert _changes(previous, current, "any", "*.txt") == [
        ("created", "/watch/created.txt"),
        ("modified", "/watch/modified.txt"),
        ("deleted", "/watch/deleted.txt"),
    ]
    assert _changes(previous, current, "created", "*.txt") == [
        ("created", "/watch/created.txt")
    ]
    assert _changes(previous, current, "modified", "*.txt") == [
        ("modified", "/watch/modified.txt")
    ]
    assert _changes(previous, current, "deleted", "*.txt") == [
        ("deleted", "/watch/deleted.txt")
    ]
