"""Claim latency benchmark (remediation M0, R0-01).

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_claims --rows 10000
"""

from __future__ import annotations

import argparse
import copy
import tempfile
import time
import uuid
from pathlib import Path

from sqlalchemy import select

from autoflow.application.projects.service import ProjectService
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from tests.integration.test_project_input_groups import (
    _add_record,
    _empty_table,
    _input,
    uid,
)

from .report import Unit, build_manifest, write_report


def _seed(directory: Path, rows: int):
    if rows < 1:
        raise ValueError("rows must be positive")
    path = directory / "bench.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = (
        ProjectService(SqlAlchemyProjects(factory))
        .create(uid(), {"name": "bench"})[0]
        .project_id
    )
    table, field = _empty_table(factory, project_id, "账号")
    _add_record(factory, project_id, table, field, "acct-00000")
    field_id = field["ref"]["fieldId"]
    with factory() as session:
        template = session.scalars(select(DataRecordRow)).one()
        template.key_value = str(uuid.UUID(int=1))
        session.flush()
        columns = {
            column.name: getattr(template, column.key)
            for column in DataRecordRow.__table__.columns
        }
        for index in range(1, rows):
            values = dict(template.values_json)
            values[field_id] = f"acct-{index:05d}"
            session.execute(
                DataRecordRow.__table__.insert().values(
                    **{
                        **columns,
                        "key_value": str(uuid.UUID(int=index + 1)),
                        "values_json": values,
                    }
                )
            )
        session.commit()
    return factory, project_id, table, field


def plans(project_id: str, table: dict, field: dict) -> dict[str, dict]:
    key_order = {"inputs": [_input(project_id, table, field, "账号")]}
    field_order = copy.deepcopy(key_order)
    field_order["inputs"][0]["orderBy"] = [
        {"fieldId": field["ref"]["fieldId"], "direction": "desc"}
    ]
    return {"claim_ms_key_order": key_order, "claim_ms_field_order": field_order}


def run(rows: int) -> dict[str, tuple[float | None, Unit]]:
    with tempfile.TemporaryDirectory() as raw:
        factory, project_id, table, field = _seed(Path(raw), rows)
        metrics: dict[str, tuple[float | None, Unit]] = {"rows": (rows, "count")}
        try:
            for name, plan in plans(project_id, table, field).items():
                started = time.perf_counter()
                with factory() as session:
                    selection = SqlAlchemyProjectInputGroups(session).select_required(
                        project_id, plan
                    )
                metrics[name] = ((time.perf_counter() - started) * 1000, "ms")
                if selection.status != "ready":
                    raise RuntimeError(
                        f"{name}: unexpected selection status {selection.status}"
                    )
        finally:
            factory.dispose()
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=2000)
    arguments = parser.parse_args()
    write_report(
        f"claims-{arguments.rows}",
        run(arguments.rows),
        manifest=build_manifest("claims-v1", {"rows": arguments.rows}),
    )


if __name__ == "__main__":
    main()
