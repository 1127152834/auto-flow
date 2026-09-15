#!/usr/bin/env python3
"""Inspect an AutoFlow SQLite database and migrate a separate copy.

The source is always opened through SQLite's read-only URI mode. The command
prints schema metadata and hashes only; it never includes row values.
"""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from autoflow.infrastructure.database.session import migrate_database

_SQLITE_HEADER = b"SQLite format 3\x00"
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "credential",
    "license",
    "password",
    "proxy_password",
    "secret",
    "token",
)


class CompatibilityInspectionError(ValueError):
    """The requested inspection would be unsafe or cannot inspect SQLite."""


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _fingerprint(path: Path) -> dict[str, int | str]:
    stat = path.stat()
    return {
        "mtimeNs": stat.st_mtime_ns,
        "size": stat.st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _read_only_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _is_secret_column(name: str) -> bool:
    normalized = name.lower()
    return any(marker in normalized for marker in _SECRET_MARKERS)


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytesSha256": hashlib.sha256(value).hexdigest(), "size": len(value)}
    return value


def _data_hash(connection: sqlite3.Connection, table: str, columns: list[str]) -> str:
    digest = hashlib.sha256()
    if not columns:
        return digest.hexdigest()
    selected = ", ".join(_quote(column) for column in columns)
    rows = connection.execute(f"SELECT {selected} FROM {_quote(table)}").fetchall()
    encoded_rows = sorted(
        json.dumps(
            [_json_value(value) for value in row], ensure_ascii=False, sort_keys=True
        )
        for row in rows
    )
    for encoded in encoded_rows:
        digest.update(encoded.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _table_metadata(connection: sqlite3.Connection, table: str) -> dict[str, Any]:
    columns = [
        {
            "position": row[0],
            "name": row[1],
            "type": row[2],
            "notNull": bool(row[3]),
            "default": row[4],
            "primaryKeyPosition": row[5],
        }
        for row in connection.execute(f"PRAGMA table_info({_quote(table)})")
    ]
    indexes = []
    for row in connection.execute(f"PRAGMA index_list({_quote(table)})"):
        index_name = row[1]
        indexes.append(
            {
                "name": index_name,
                "unique": bool(row[2]),
                "origin": row[3],
                "partial": bool(row[4]),
                "columns": [
                    index_row[2]
                    for index_row in connection.execute(
                        f"PRAGMA index_info({_quote(index_name)})"
                    )
                ],
            }
        )
    foreign_keys = [
        {
            "id": row[0],
            "sequence": row[1],
            "table": row[2],
            "from": row[3],
            "to": row[4],
            "onUpdate": row[5],
            "onDelete": row[6],
            "match": row[7],
        }
        for row in connection.execute(f"PRAGMA foreign_key_list({_quote(table)})")
    ]
    safe_columns = [
        column["name"] for column in columns if not _is_secret_column(column["name"])
    ]
    return {
        "columns": columns,
        "indexes": indexes,
        "foreignKeys": foreign_keys,
        "rowCount": connection.execute(
            f"SELECT COUNT(*) FROM {_quote(table)}"
        ).fetchone()[0],
        "hashedColumns": safe_columns,
        "dataHash": _data_hash(connection, table, safe_columns),
    }


def _snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    revision = []
    if "alembic_version" in tables:
        revision = sorted(
            row[0]
            for row in connection.execute("SELECT version_num FROM alembic_version")
        )
    return {
        "revision": revision,
        "tables": {table: _table_metadata(connection, table) for table in tables},
        "foreignKeyViolations": [
            list(row) for row in connection.execute("PRAGMA foreign_key_check")
        ],
    }


def _comparison(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    tables: dict[str, Any] = {}
    preserved = not after["foreignKeyViolations"]
    for table, source_metadata in before["tables"].items():
        if table == "alembic_version":
            continue
        target_metadata = after["tables"].get(table)
        if target_metadata is None:
            tables[table] = {"missing": True}
            preserved = False
            continue
        source_columns = set(source_metadata["hashedColumns"])
        target_columns = set(target_metadata["hashedColumns"])
        common_columns = sorted(source_columns & target_columns)
        source_hash = _data_hash(source, table, common_columns)
        target_hash = _data_hash(target, table, common_columns)
        row_count = {
            "before": source_metadata["rowCount"],
            "after": target_metadata["rowCount"],
        }
        data_hash = {"before": source_hash, "after": target_hash}
        table_preserved = (
            row_count["before"] == row_count["after"] and source_hash == target_hash
        )
        tables[table] = {
            "columnsCompared": common_columns,
            "rowCount": row_count,
            "dataHash": data_hash,
            "preserved": table_preserved,
        }
        preserved = preserved and table_preserved
    return {"preserved": preserved, "tables": tables}


def inspect_database_compatibility(source: Path, target: Path) -> dict[str, Any]:
    """Inspect *source*, migrate a new *target* copy, and compare existing rows."""

    source = Path(source).expanduser().resolve()
    target = Path(target).expanduser().resolve()
    if source == target:
        raise CompatibilityInspectionError("源数据库与目标副本必须是不同路径")
    if not source.is_file():
        raise CompatibilityInspectionError("源数据库不存在或不是文件")
    if target.exists():
        raise CompatibilityInspectionError("目标副本已经存在，拒绝覆盖")
    if source.read_bytes()[: len(_SQLITE_HEADER)] != _SQLITE_HEADER:
        raise CompatibilityInspectionError("源文件不是可识别的 SQLite 数据库")

    target.parent.mkdir(parents=True, exist_ok=True)
    source_before = _fingerprint(source)
    with _read_only_connection(source) as source_connection:
        before = _snapshot(source_connection)
        with sqlite3.connect(target) as target_connection:
            source_connection.backup(target_connection)

    migrate_database(target)

    with (
        _read_only_connection(source) as source_connection,
        _read_only_connection(target) as target_connection,
    ):
        after = _snapshot(target_connection)
        comparison = _comparison(source_connection, target_connection, before, after)

    source_after = _fingerprint(source)
    if source_after != source_before:
        raise CompatibilityInspectionError("检查期间源数据库发生变化，结果无效")
    if not comparison["preserved"]:
        raise CompatibilityInspectionError("迁移副本未通过业务数据完整性比较")
    return {
        "source": {**source_before, "path": str(source), "unchanged": True, **before},
        "target": {"path": str(target), **_fingerprint(target), **after},
        "comparison": comparison,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="只读检查的源 SQLite 数据库")
    parser.add_argument("target", type=Path, help="必须尚不存在的迁移副本路径")
    args = parser.parse_args()
    report = inspect_database_compatibility(args.source, args.target)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
