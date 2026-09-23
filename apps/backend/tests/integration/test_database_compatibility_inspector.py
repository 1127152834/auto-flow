from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError

from autoflow.infrastructure.database import session as database_session
from scripts.inspect_database_compatibility import (
    CompatibilityInspectionError,
    inspect_database_compatibility,
)


def _config(database: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def _fingerprint(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, hashlib.sha256(path.read_bytes()).hexdigest()


def test_inspector_upgrades_a_copy_and_preserves_source_and_rows(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.sqlite3"
    target = tmp_path / "target.sqlite3"
    command.upgrade(_config(source), "0008_workflow_debug")
    with sqlite3.connect(source) as connection:
        connection.execute(
            "INSERT INTO workflow_documents VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "workflow",
                "保留流程",
                '{"nodes":[]}',
                "{}",
                7,
                "2026-09-15",
                "2026-09-15",
            ),
        )
        connection.execute(
            "CREATE TABLE compatibility_private (id TEXT PRIMARY KEY, display_name TEXT, api_token TEXT)"
        )
        connection.execute(
            "INSERT INTO compatibility_private VALUES ('one', '可核对名称', '不得出现在报告中')"
        )

    before = _fingerprint(source)
    report = inspect_database_compatibility(source, target)

    assert _fingerprint(source) == before
    assert report["source"]["unchanged"] is True
    assert report["source"]["revision"] == ["0008_workflow_debug"]
    assert report["target"]["revision"] == ["am01_management_operations"]
    assert report["comparison"]["preserved"] is True
    assert report["comparison"]["tables"]["workflow_documents"]["rowCount"] == {
        "before": 1,
        "after": 1,
    }
    serialized = json.dumps(report, ensure_ascii=False)
    assert "不得出现在报告中" not in serialized
    assert "可核对名称" not in serialized
    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT name, revision FROM workflow_documents WHERE id='workflow'"
        ).fetchone() == ("保留流程", 7)
        assert connection.execute(
            "SELECT api_token FROM compatibility_private WHERE id='one'"
        ).fetchone() == ("不得出现在报告中",)


@pytest.mark.parametrize("case", ["same-path", "existing-target", "not-sqlite"])
def test_inspector_rejects_unsafe_paths_and_inputs(tmp_path: Path, case: str) -> None:
    source = tmp_path / "source.sqlite3"
    target = tmp_path / "target.sqlite3"
    if case == "not-sqlite":
        source.write_text("不是 SQLite", encoding="utf-8")
    else:
        database_session.migrate_database(source)
    if case == "same-path":
        target = source
    elif case == "existing-target":
        target.write_bytes("保留目标".encode())

    source_before = _fingerprint(source)
    target_before = (
        target.read_bytes() if target.exists() and target != source else None
    )
    with pytest.raises(CompatibilityInspectionError):
        inspect_database_compatibility(source, target)

    assert _fingerprint(source) == source_before
    if target_before is not None:
        assert target.read_bytes() == target_before


def test_inspector_reports_unknown_revision_without_modifying_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "unknown.sqlite3"
    target = tmp_path / "copy.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.executescript(
            """
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version VALUES ('unknown_user_revision');
            CREATE TABLE retained_data (id TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO retained_data VALUES ('sentinel', '不得修改');
            """
        )

    before = _fingerprint(source)
    with pytest.raises(CommandError, match="unknown_user_revision"):
        inspect_database_compatibility(source, target)

    assert _fingerprint(source) == before
    with sqlite3.connect(source) as connection:
        assert connection.execute("SELECT * FROM retained_data").fetchall() == [
            ("sentinel", "不得修改")
        ]
