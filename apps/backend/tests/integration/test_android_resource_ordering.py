"""Resources written within one clock tick keep insertion order (Windows clock ticks are ~15.6 ms)."""

from pathlib import Path

from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def test_list_breaks_created_at_ties_by_insertion_order(tmp_path: Path):
    database = tmp_path / "order.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    try:
        resources = AndroidResourceRepository(sessions)
        # Ids sort opposite to insertion order, so an unordered read would return them reversed.
        for identifier in ("f-last-alphabetically", "e", "d", "c", "b", "a-first-alphabetically"):
            resources.save("bulk", {"id": identifier, "createdAt": "2026-10-07T00:00:00.000000+00:00"})
        assert [item["id"] for item in resources.list("bulk")] == [
            "f-last-alphabetically", "e", "d", "c", "b", "a-first-alphabetically",
        ]
    finally:
        sessions.dispose()
