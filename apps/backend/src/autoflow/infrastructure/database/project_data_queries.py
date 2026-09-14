from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import Integer, case, func, select, text
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.project_data.query import (
    MISSING,
    compare_values,
    compatible,
    date_value,
    matches,
    validate_filter,
    validate_order,
)
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataRecordRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)


class SqlAlchemyProjectDataQueries:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def query(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        filter_value: Any,
        order_value: Any,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            session.execute(text("BEGIN"))
            try:
                SqlAlchemyProjectData._guard_project_read(session, project_id)
                table = session.scalar(
                    select(DataTableRow).where(
                        DataTableRow.published.is_(True),
                        DataTableRow.project_id == project_id,
                        DataTableRow.id == table_id,
                    )
                )
                if table is None:
                    raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
                if table.current_generation != generation:
                    raise ProjectError(
                        "DATASET_GENERATION_GONE",
                        "Dataset generation is no longer current",
                        410,
                    )
                fields = list(
                    session.scalars(
                        select(DataFieldRow)
                        .where(
                            DataFieldRow.project_id == project_id,
                            DataFieldRow.table_id == table_id,
                            DataFieldRow.dataset_generation == generation,
                        )
                        .order_by(DataFieldRow.position, DataFieldRow.id)
                    )
                )
                field_types = {field.id: field.type for field in fields}
                statuses = list(
                    session.scalars(
                        select(DataStatusRow).where(
                            DataStatusRow.project_id == project_id,
                            DataStatusRow.table_id == table_id,
                            DataStatusRow.deleted.is_(False),
                        )
                    )
                )
                status_order = {row.id: (row.position, row.id) for row in statuses}
                filter_expr = validate_filter(
                    filter_value, field_types, set(status_order)
                )
                order = validate_order(order_value, field_types)
                raw = cast(
                    sqlite3.Connection,
                    session.connection().connection.driver_connection,
                )
                trivial_filter = filter_expr == {"type": "all", "items": []}
                if not trivial_filter:
                    raw.create_function(
                        "autoflow_query_match",
                        2,
                        lambda values, status: int(
                            matches(filter_expr, json.loads(values), status)
                        ),
                    )
                if order:
                    field_targets = [
                        item["fieldId"] for item in order if "fieldId" in item
                    ]

                    def sort_projection(
                        values: str,
                        status: str | None,
                        created: str,
                        updated: str,
                        key_type: str,
                        key_value: str,
                    ) -> str:
                        decoded = json.loads(values)
                        return json.dumps(
                            [
                                {key: decoded.get(key) for key in field_targets},
                                status,
                                created,
                                updated,
                                key_type,
                                key_value,
                            ],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )

                    raw.create_function(
                        "autoflow_query_sort",
                        6,
                        sort_projection,
                    )
                    raw.create_collation(
                        "AUTOFLOW_QUERY", _collation(order, field_types, status_order)
                    )
                base: tuple[Any, ...] = (
                    DataRecordRow.project_id == project_id,
                    DataRecordRow.table_id == table_id,
                    DataRecordRow.dataset_generation == generation,
                    DataRecordRow.deleted.is_(False),
                )
                if not trivial_filter:
                    base += (
                        func.autoflow_query_match(
                            DataRecordRow.values_json, DataRecordRow.status_id
                        )
                        == 1,
                    )
                total = (
                    session.scalar(
                        select(func.count()).select_from(DataRecordRow).where(*base)
                    )
                    or 0
                )
                statement = select(DataRecordRow).where(*base)
                if order:
                    statement = statement.order_by(
                        text(
                            "autoflow_query_sort(values_json,status_id,created_at,updated_at,key_type,key_value) COLLATE AUTOFLOW_QUERY"
                        )
                    )
                else:
                    rank = case(
                        (DataRecordRow.key_type == "text", 0),
                        (DataRecordRow.key_type == "integer", 1),
                        else_=2,
                    )
                    statement = statement.order_by(
                        rank,
                        case(
                            (
                                DataRecordRow.key_type == "integer",
                                sql_cast(DataRecordRow.key_value, Integer),
                            ),
                            else_=None,
                        ),
                        DataRecordRow.key_value,
                    )
                rows = list(
                    session.scalars(
                        statement.limit(page_size).offset((page - 1) * page_size)
                    )
                )
                items = [_snapshot(row, fields) for row in rows]
                return {
                    "items": items,
                    "total": total,
                    "page": page,
                    "pageSize": page_size,
                    "sort": json.dumps(
                        [
                            *order,
                            {"systemField": "recordKey", "direction": "asc"},
                        ],
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ),
                }
            finally:
                try:
                    if "raw" in locals():
                        raw.create_function("autoflow_query_match", 2, None)
                        raw.create_function("autoflow_query_sort", 6, None)
                        raw.create_collation("AUTOFLOW_QUERY", None)
                finally:
                    session.rollback()


def _collation(
    order: list[dict[str, str]],
    field_types: dict[str, str],
    status_order: dict[str, tuple[int, str]],
) -> Callable[[str, str], int]:
    def compare(left_text: str, right_text: str) -> int:
        left, right = json.loads(left_text), json.loads(right_text)
        for item in order:
            if "fieldId" in item:
                field_id = item["fieldId"]
                a, b = left[0].get(field_id, MISSING), right[0].get(field_id, MISSING)
                if (a is MISSING or a is None) != (b is MISSING or b is None):
                    return 1 if a is MISSING or a is None else -1
                valid_a = compatible(field_types[field_id], a)
                valid_b = compatible(field_types[field_id], b)
                if valid_a != valid_b:
                    return -1 if valid_a else 1
                if field_types[field_id] == "date":
                    date_a, date_b = date_value(a), date_value(b)
                    if (date_a is None) != (date_b is None):
                        return 1 if date_a is None else -1
                    if (
                        date_a is not None
                        and date_b is not None
                        and date_a[0] != date_b[0]
                    ):
                        return (date_a[0] > date_b[0]) - (date_a[0] < date_b[0])
                result = _sort_value(field_types[field_id], a, b)
            else:
                target = item["systemField"]
                if target == "status":
                    a = status_order.get(left[1], MISSING)
                    b = status_order.get(right[1], MISSING)
                    if (a is MISSING) != (b is MISSING):
                        return 1 if a is MISSING else -1
                    result = _nullable_compare(
                        a,
                        b,
                    )
                elif target in {"createdAt", "updatedAt"}:
                    result = _nullable_compare(
                        left[2 if target == "createdAt" else 3],
                        right[2 if target == "createdAt" else 3],
                    )
                else:
                    result = _record_key_compare(left[4], left[5], right[4], right[5])
            if result:
                return result if item["direction"] == "asc" else -result
        return _record_key_compare(left[4], left[5], right[4], right[5])

    return compare


def _nullable_compare(left: Any, right: Any) -> int:
    left_null, right_null = (
        left is MISSING or left is None,
        right is MISSING or right is None,
    )
    if left_null or right_null:
        return (1 if left_null else -1) if left_null != right_null else 0
    return (left > right) - (left < right)


def _sort_value(kind: str, left: Any, right: Any) -> int:
    if left is MISSING or left is None or right is MISSING or right is None:
        return _nullable_compare(left, right)
    if kind == "date":
        a, b = date_value(left), date_value(right)
        if a is None or b is None:
            return _nullable_compare(a, b)
        return (a > b) - (a < b)
    result = compare_values(kind, left, right)
    return (
        _nullable_compare(
            None if result is None else left, None if result is None else right
        )
        if result is None
        else result
    )


def _record_key_compare(lt: str, lv: str, rt: str, rv: str) -> int:
    ranks = {"text": 0, "integer": 1, "uuid": 2}
    if lt != rt:
        return (ranks[lt] > ranks[rt]) - (ranks[lt] < ranks[rt])
    if lt == "integer":
        return (int(lv) > int(rv)) - (int(lv) < int(rv))
    return (lv > rv) - (lv < rv)


def _snapshot(row: DataRecordRow, fields: list[DataFieldRow]) -> dict[str, Any]:
    snapshot = SqlAlchemyProjectDataRecords._snapshot(row, fields)
    snapshot["values"] = [
        cell for cell in snapshot["values"] if cell["fieldId"] in row.values_json
    ]
    return snapshot
