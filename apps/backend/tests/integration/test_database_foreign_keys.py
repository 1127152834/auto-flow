import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from autoflow.infrastructure.database.session import create_session_factory, migrate_database


def test_session_factory_enforces_foreign_keys_on_every_connection(tmp_path):
    path = tmp_path / "foreign-keys.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    try:
        # Two checked-out sessions require two physical connections, not one pooled connection.
        with factory() as first, factory() as second:
            for session in (first, second):
                assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        with factory.begin() as session:
            session.execute(text("CREATE TABLE fk_parent (id INTEGER PRIMARY KEY)"))
            session.execute(text("CREATE TABLE fk_child (parent_id INTEGER REFERENCES fk_parent(id))"))
        with pytest.raises(IntegrityError), factory.begin() as session:
            session.execute(text("INSERT INTO fk_child VALUES (999)"))
    finally:
        factory.dispose()
