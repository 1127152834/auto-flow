from __future__ import annotations

from sqlalchemy import UniqueConstraint, inspect

from autoflow.infrastructure.database.project_run_models import (
    ProjectTaskRecordCursorRow,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def test_cursor_identity_matches_migrated_record_ref_constraint(tmp_path):
    path = tmp_path / "cursor.sqlite"
    migrate_database(path)
    factory = create_session_factory(path)
    try:
        actual = inspect(factory.kw["bind"]).get_unique_constraints("project_task_record_cursors")
        expected = {("uq_project_task_record_cursors_ref", ("task_id", "record_ref"))}
        assert {(item["name"], tuple(item["column_names"])) for item in actual} == expected
        declared = {
            (item.name, tuple(column.name for column in item.columns))
            for item in ProjectTaskRecordCursorRow.__table__.constraints
            if isinstance(item, UniqueConstraint)
        }
        assert declared == expected
    finally:
        factory.dispose()
