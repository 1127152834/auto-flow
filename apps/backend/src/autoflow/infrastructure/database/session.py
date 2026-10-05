import asyncio
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker


def _url(path: Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


BACKUPS_KEPT = 5


def migrate_database(path: Path) -> None:
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", _url(path))
    _backup_before_upgrade(path, config)
    command.upgrade(config, "head")


def _backup_before_upgrade(path: Path, config: Config) -> None:
    """Copy an existing database before any schema change (remediation M4 R4-10).

    Uses SQLite's online backup so a WAL database is copied consistently; keeps the newest five.
    A database already at head is not copied.
    """
    if not path.exists():
        return
    head = ScriptDirectory.from_config(config).get_current_head()
    with sqlite3.connect(path) as source:
        try:
            row = source.execute("SELECT version_num FROM alembic_version").fetchone()
        except sqlite3.OperationalError:
            row = None
        current = row[0] if row else None
        if current is None or current == head:
            return
        directory = path.parent / "backups"
        directory.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = directory / f"{path.stem}-{current}-{stamp}.sqlite3"
        with sqlite3.connect(target) as destination:
            source.backup(destination)
    for old in sorted(directory.glob(f"{path.stem}-*.sqlite3"))[:-BACKUPS_KEPT]:
        old.unlink(missing_ok=True)


SQLITE_PRAGMAS = (
    # busy_timeout first so switching an older database to WAL waits for a concurrent connection.
    "PRAGMA busy_timeout=5000",
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
)


def checkpoint_wal(factory: sessionmaker[Session]) -> None:
    """Checkpoint a quiescent database; callers must keep writes stopped during a copy."""
    with factory() as session:
        busy, _, _ = session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)")).one()
        if busy:
            raise RuntimeError("SQLite WAL checkpoint is busy")


class WalCheckpointer:
    """Remediation M3 AC3-02: PASSIVE checkpoints off the event loop keep the WAL short.

    SQLite's automatic checkpoint runs inside whichever commit crosses 1000 pages; when that
    commit is on the event loop it copies and syncs the database there. Checkpointing once a
    second from a thread means commits rarely cross the limit (the automatic one stays as a net).
    PASSIVE never waits for readers or writers.
    """

    def __init__(self, factory: sessionmaker[Session], interval: float = 1.0) -> None:
        self._factory, self._interval = factory, interval
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await asyncio.to_thread(self._checkpoint)
            except Exception as error:  # noqa: BLE001 -- the automatic checkpoint still covers it
                logging.getLogger(__name__).warning("SQLite 后台检查点失败：%s", error)

    def _checkpoint(self) -> None:
        with self._factory() as session:
            session.execute(text("PRAGMA wal_checkpoint(PASSIVE)"))


def create_session_factory(path: Path):
    engine = create_engine(_url(path), future=True)

    @event.listens_for(engine, "connect")
    def configure_connection(connection: sqlite3.Connection, _record: object) -> None:
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
