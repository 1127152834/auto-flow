import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker


def _url(path: Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def migrate_database(path: Path) -> None:
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", _url(path))
    command.upgrade(config, "head")


def create_session_factory(path: Path):
    engine = create_engine(_url(path), future=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    factory.dispose = engine.dispose  # type: ignore[attr-defined]
    return factory


def is_sqlite_contention(error: OperationalError) -> bool:
    code = getattr(error.orig, "sqlite_errorcode", None)
    if isinstance(code, int) and code & 0xFF in {
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    }:
        return True
    message = str(error.orig).lower()
    return message in {
        "database is busy",
        "database is locked",
        "database schema is locked",
        "database table is locked",
    }
