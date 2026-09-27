"""Read-only-to-production check: migrate a fresh temporary DB and compare ORM metadata."""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / "apps/backend/src"))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402

from autoflow.infrastructure.database.session import migrate_database  # noqa: E402

with tempfile.TemporaryDirectory(prefix="autoflow-audit-migration-") as directory:
    database = Path(directory) / "fresh.sqlite3"
    config = Config(str(root / "apps/backend/src/autoflow/infrastructure/database/alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, heads
    migrate_database(database)
    migrate_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [(heads[0],)]
        print(json.dumps({"head": heads[0], "freshUpgrade": "passed", "repeatUpgrade": "passed",
                          "integrityCheck": "passed", "foreignKeyCheck": "passed"}), flush=True)
    command.check(config)
