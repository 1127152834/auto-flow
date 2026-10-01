import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
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


SQLITE_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
)


def checkpoint_wal(factory) -> None:
    """Checkpoint a quiescent database; callers must keep writes stopped during a copy."""
    with factory() as session:
        busy, _, _ = session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)")).one()
        if busy:
            raise RuntimeError("SQLite WAL checkpoint is busy")


def create_session_factory(path: Path):
    engine = create_engine(_url(path), future=True)

    @event.listens_for(engine, "connect")
    def configure_connection(connection, _record):
        # Remediation M1 R1-13: WAL lets readers proceed during writes; NORMAL is durable
        # across application crashes in WAL mode; busy_timeout absorbs short lock waits.
        cursor = connection.cursor()
        try:
            for pragma in SQLITE_PRAGMAS:
                cursor.execute(pragma)
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
