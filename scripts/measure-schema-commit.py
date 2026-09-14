"""Measure R3 schema boundaries against owned temporary SQLite databases.

Run: uv run --directory apps/backend python ../../scripts/measure-schema-commit.py
No database-path option is accepted: this program never opens a user database.
Fixtures use real application services; setup time is reported separately.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/backend/src"))

from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.schema import DataSchemaService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.domain.project_data.schema import canonical_bytes
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data import (
    SqlAlchemyProjectData,
)
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_data_schema import (
    SqlAlchemyProjectDataSchema,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)

LIMIT_BYTES = 4 * 1024 * 1024
CASES = {
    "1000_rows": (1000, None, False, False),
    "4mib_exact": (1000, LIMIT_BYTES, False, False),
    "1001_rows_rejected": (1001, None, False, True),
    "4mib_plus_one_rejected": (1000, LIMIT_BYTES + 1, False, True),
    "10000_rows_rules_only": (10000, None, True, False),
}


def uid() -> str:
    return str(uuid4())


def elapsed(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def latencies(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {
        "count": len(ordered),
        "min_ms": round(ordered[0], 3) if ordered else None,
        "median_ms": round(statistics.median(ordered), 3) if ordered else None,
        "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 3)
        if ordered
        else None,
        "max_ms": round(ordered[-1], 3) if ordered else None,
    }


def run_case(name: str, root: Path) -> dict:
    count, target_bytes, rules_only, rejected = CASES[name]
    database = root / f"{name}.sqlite3"
    setup_start = perf_counter()
    migrate_database(database)
    factory = create_session_factory(database)
    engine = factory.kw["bind"]
    stop, ready = threading.Event(), threading.Event()
    phase = ["idle"]
    samples: dict[str, list[float]] = {"preview": [], "commit": []}
    failures: list[dict] = []
    transaction_start: list[float] = []
    transaction_ms: list[float] = []
    main_thread = threading.get_ident()

    def before_sql(_connection, _cursor, statement, _parameters, _context, _many):
        if (
            phase[0] == "commit"
            and threading.get_ident() == main_thread
            and statement.strip().upper() == "BEGIN IMMEDIATE"
        ):
            transaction_start.append(perf_counter())

    def after_commit(session):
        if (
            session.bind is engine
            and threading.get_ident() == main_thread
            and phase[0] == "commit"
            and transaction_start
        ):
            # Session.after_commit runs after the DBAPI commit, unlike Engine.commit.
            transaction_ms.append(elapsed(transaction_start[-1]))

    def concurrent_reader():
        while not stop.is_set():
            label = phase[0]
            started = perf_counter()
            try:
                with factory() as session:
                    session.scalar(select(func.count()).select_from(DataRecordRow))
            except Exception as error:  # noqa: BLE001 -- record failures and fail the case
                failures.append(
                    {
                        "phase": label,
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                )
            else:
                if label in samples:
                    samples[label].append((perf_counter() - started) * 1000)
            ready.set()
            stop.wait(0.002)

    event.listen(engine, "before_cursor_execute", before_sql)
    event.listen(Session, "after_commit", after_commit)
    try:
        project = (
            ProjectService(SqlAlchemyProjects(factory))
            .create(uid(), {"name": name})[0]
            .project_id
        )
        table = DataTableService(SqlAlchemyProjectData(factory)).create(
            project, uid(), {"name": "Measured table"}
        )[0]
        table_id, generation = table["tableId"], table["datasetGeneration"]
        definition = {
            "key": "value",
            "name": "Value",
            "type": "string",
            "required": False,
            "validation": {},
        }
        catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
        field = catalog.create_field(
            project,
            table_id,
            uid(),
            {
                "definition": definition,
                "expectedTableRevision": 1,
                "sourceColumnPolicy": "localOnly",
            },
        )[0]["field"]
        field_id = field["ref"]["fieldId"]
        # Persistent UUID field IDs have fixed length, so this yields exact postwrite bytes.
        overhead = len(canonical_bytes({field_id: "", "0" * 36: False}))
        if target_bytes is None:
            lengths = [16] * count
        else:
            quotient, remainder = divmod(target_bytes - count * overhead, count)
            assert quotient >= 0
            lengths = [quotient + (index < remainder) for index in range(count)]
        records = DataRecordService(SqlAlchemyProjectDataRecords(factory))
        original_bytes = 0
        postwrite_bytes = 0
        for length in lengths:
            value = "a" * length
            original_bytes += len(canonical_bytes({field_id: value}))
            postwrite_bytes += len(canonical_bytes({field_id: value, "0" * 36: False}))
            records.create(
                project,
                table_id,
                uid(),
                {
                    "datasetGeneration": generation,
                    "values": [{"fieldId": field_id, "value": value}],
                },
            )
        draft = {
            "datasetGeneration": generation,
            "expectedTableRevision": 2,
            "fields": [
                {
                    "kind": "existing",
                    "fieldId": field_id,
                    "expectedFieldRevision": 1,
                    "definition": {
                        **definition,
                        "validation": {"maxLength": 100} if rules_only else {},
                    },
                }
            ],
        }
        if not rules_only:
            draft["fields"].append(
                {
                    "kind": "new",
                    "clientId": uid(),
                    "sourceColumnPolicy": "localOnly",
                    "definition": {
                        "key": "flag",
                        "name": "Flag",
                        "type": "boolean",
                        "required": False,
                        "validation": {},
                    },
                    "existingRecordDefault": False,
                }
            )
        setup_ms = elapsed(setup_start)
        with factory() as session:
            journal_mode = session.scalar(text("PRAGMA journal_mode"))
        size_before = database.stat().st_size
        service = DataSchemaService(SqlAlchemyProjectDataSchema(factory))
        with ThreadPoolExecutor(max_workers=1) as pool:
            reader = pool.submit(concurrent_reader)
            if not ready.wait(10):
                stop.set()
                raise RuntimeError("Concurrent reader did not start")
            try:
                phase[0] = "preview"
                started = perf_counter()
                impact = service.preview(project, table_id, draft)
                preview_ms = elapsed(started)
                expected_bytes = 0 if rules_only else postwrite_bytes
                assert impact["backfillBytes"] == expected_bytes, impact
                assert bool(impact["blockers"]) is rejected, impact
                if rejected:
                    assert any(
                        issue["code"] == "SCHEMA_BACKFILL_LIMIT"
                        for issue in impact["blockers"]
                    ), impact
                phase[0] = "commit"
                key = uid()
                started = perf_counter()
                commit_error = None
                result = None
                try:
                    result, _, replayed = service.commit(
                        project,
                        table_id,
                        key,
                        {
                            "candidate": draft,
                            "impactRevision": impact["impactRevision"],
                        },
                    )
                    assert not rejected and not replayed
                except ProjectError as error:
                    if not rejected or error.code != "IMPACT_STALE":
                        raise
                    commit_error = {"code": error.code, "status": error.status}
                commit_call_ms = elapsed(started)
            finally:
                phase[0] = "idle"
                stop.set()
                reader.result(timeout=15)
        with factory() as session:
            actual_count = session.scalar(
                select(func.count()).select_from(DataRecordRow)
            )
            field_count = session.scalar(select(func.count()).select_from(DataFieldRow))
            actual_bytes = sum(
                len(canonical_bytes(row.values_json))
                for row in session.scalars(
                    select(DataRecordRow).execution_options(yield_per=200)
                )
            )
            revision_counts = dict(
                session.execute(
                    select(DataRecordRow.content_revision, func.count()).group_by(
                        DataRecordRow.content_revision
                    )
                ).all()
            )
            operation = session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
        assert actual_count == count
        assert field_count == (1 if rejected or rules_only else 2)
        assert actual_bytes == (
            original_bytes if rejected or rules_only else postwrite_bytes
        )
        assert revision_counts == {(1 if rejected or rules_only else 2): count}
        assert (operation is None) is rejected
        assert len(transaction_ms) == (0 if rejected else 1)
        if result:
            assert result["backfilledRecords"] == (0 if rules_only else count)
        assert not failures, failures
        return {
            "case": name,
            "status": "passed",
            "rows": count,
            "journal_mode": journal_mode,
            "setup_ms": setup_ms,
            "preview_ms": preview_ms,
            "commit_call_ms": commit_call_ms,
            "begin_immediate_to_commit_ms": transaction_ms[0]
            if transaction_ms
            else None,
            "expected_rejection": rejected,
            "commit_error": commit_error,
            "canonical_bytes_before": original_bytes,
            "canonical_bytes_after": actual_bytes,
            "candidate_backfill_bytes": impact["backfillBytes"],
            "target_boundary_bytes": target_bytes,
            "backfilled_records": result["backfilledRecords"] if result else 0,
            "db_bytes_before": size_before,
            "db_bytes_after": database.stat().st_size,
            "database_sidecar_bytes": {
                suffix: database.with_name(database.name + suffix).stat().st_size
                if database.with_name(database.name + suffix).exists()
                else 0
                for suffix in ("-wal", "-shm", "-journal")
            },
            "concurrent_reads": {
                label: latencies(values) for label, values in samples.items()
            },
            "concurrent_read_failures": failures,
        }
    finally:
        stop.set()
        event.remove(engine, "before_cursor_execute", before_sql)
        event.remove(Session, "after_commit", after_commit)
        factory.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="JSON report path; defaults to a new file in the system temporary directory",
    )
    parser.add_argument(
        "--case",
        action="append",
        choices=CASES,
        help="Run selected case(s); default is all five",
    )
    args = parser.parse_args()
    if args.output is None:
        with tempfile.NamedTemporaryFile(
            prefix="autoflow-schema-measure-", suffix=".json", delete=False
        ) as report:
            output = Path(report.name)
    else:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="autoflow-schema-databases-") as directory:
        for name in dict.fromkeys(args.case or CASES):
            try:
                results.append(run_case(name, Path(directory)))
            except Exception as error:  # noqa: BLE001 -- persist failed evidence and exit nonzero
                results.append(
                    {
                        "case": name,
                        "status": "failed",
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                )
    document = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "status": "passed"
        if all(item["status"] == "passed" for item in results)
        else "failed",
        "database_policy": "owned temporary databases removed after measurement; no user database opened",
        "timing": "Preview wall time; successful commit timer from SQLAlchemy BEGIN IMMEDIATE execution to Session.after_commit. Rejections have no successful commit duration. Read count zero means no measured sample, not zero latency.",
        "cases": results,
    }
    output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(str(output))
    return 0 if document["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
