"""Remediation M1 R1-13: every connection is configured for concurrent local use."""

import shutil

import pytest
from sqlalchemy import text

from autoflow.infrastructure.database import session as session_module
from autoflow.infrastructure.database.session import (
    checkpoint_wal,
    create_session_factory,
    migrate_database,
)


def test_every_connection_uses_wal_normal_sync_and_busy_timeout(tmp_path):
    path = tmp_path / "db.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    try:
        with factory() as first, factory() as second:
            for session in (first, second):  # hold both so the pool must open two connections
                assert session.execute(text("PRAGMA journal_mode")).scalar() == "wal"
                assert session.execute(text("PRAGMA synchronous")).scalar() == 1
                assert session.execute(text("PRAGMA busy_timeout")).scalar() == 5000
                assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
        checkpoint_wal(factory)
        wal = path.with_name(path.name + "-wal")
        assert not wal.exists() or wal.stat().st_size == 0
    finally:
        factory.dispose()


def _factory_with_short_busy_timeout(tmp_path, monkeypatch):
    path = tmp_path / "db.sqlite3"
    migrate_database(path)
    pragmas = tuple(
        "PRAGMA busy_timeout=50" if item.startswith("PRAGMA busy_timeout") else item
        for item in session_module.SQLITE_PRAGMAS
    )
    monkeypatch.setattr(session_module, "SQLITE_PRAGMAS", pragmas)
    return path, create_session_factory(path)


def test_checkpoint_reports_busy_instead_of_letting_a_copy_miss_wal_pages(tmp_path, monkeypatch):
    """A reader holding an old snapshot keeps pages in the WAL; copying the main file then loses rows."""
    path, factory = _factory_with_short_busy_timeout(tmp_path, monkeypatch)
    try:
        with factory() as setup:
            setup.execute(text("CREATE TABLE IF NOT EXISTS probe (value TEXT)"))
            setup.commit()
        reader = factory()
        writer = factory()
        try:
            # pysqlite does not begin a transaction for SELECT; an explicit BEGIN keeps the snapshot open.
            reader.connection().exec_driver_sql("BEGIN")
            reader.execute(text("SELECT count(*) FROM probe")).scalar()
            writer.execute(text("INSERT INTO probe VALUES ('new-row')"))
            writer.commit()
            with pytest.raises(RuntimeError, match="busy"):
                checkpoint_wal(factory)
        finally:
            reader.close()
            writer.close()
        checkpoint_wal(factory)  # snapshot released: now the main file holds every page
        copy = tmp_path / "copy.sqlite3"
        shutil.copy2(path, copy)
        copied = create_session_factory(copy)
        try:
            with copied() as session:
                assert session.execute(text("SELECT value FROM probe")).scalars().all() == ["new-row"]
        finally:
            copied.dispose()
    finally:
        factory.dispose()
