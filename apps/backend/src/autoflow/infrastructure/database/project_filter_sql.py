"""Translate validated record filters to SQLite predicates for claiming (remediation M3 R3-01).

The domain filter (``domain/project_data/query.matches``) stays the source of truth: every claimed
row is still checked in Python. A translation is therefore allowed to be a superset of the real
condition, never a subset. ``exact`` says whether the predicate equals the domain result, which is
required before it can be negated. Date comparisons are not translated (their normalisation lives
in Python) and simply widen to "every row".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, false, func, literal, not_, or_, true
from sqlalchemy.sql.elements import ColumnElement

from .project_data_models import DataRecordRow

_MAX_SAFE_INTEGER = 9007199254740991


@dataclass(frozen=True)
class SqlPredicate:
    clause: ColumnElement[bool]
    exact: bool


_EVERYTHING = SqlPredicate(true(), False)


def _path(field_id: str) -> str:
    return '$."' + field_id.replace('"', '""') + '"'


def _field(node: dict[str, Any]) -> SqlPredicate:
    path = literal(_path(node["fieldId"]))
    kind = func.json_type(DataRecordRow.values_json, path)
    value = func.json_extract(DataRecordRow.values_json, path)
    operator = node["operator"]
    if operator == "isNull":
        return SqlPredicate(or_(kind.is_(None), kind == "null"), True)
    if operator == "isNotNull":
        return SqlPredicate(and_(kind.is_not(None), kind != "null"), True)
    expected = node["value"]
    if isinstance(expected, str):
        text_value = and_(kind == "text", value.is_not(None))
        if operator == "eq":
            return SqlPredicate(and_(text_value, value == expected), True)
        if operator == "neq":
            return SqlPredicate(and_(text_value, value != expected), True)
        if operator == "contains":
            return SqlPredicate(and_(text_value, func.instr(value, expected) > 0), True)
        if operator == "startsWith":
            return SqlPredicate(and_(text_value, func.substr(value, 1, len(expected)) == expected), True)
        return _EVERYTHING
    if type(expected) is bool:
        boolean = kind.in_(("true", "false"))
        if operator == "eq":
            return SqlPredicate(and_(boolean, value == (1 if expected else 0)), True)
        if operator == "neq":
            return SqlPredicate(and_(boolean, value != (1 if expected else 0)), True)
        return _EVERYTHING
    if type(expected) in (int, float):
        number = or_(kind == "real", and_(kind == "integer", func.abs(value) <= _MAX_SAFE_INTEGER))
        comparison = {
            "eq": value == expected, "neq": value != expected, "gt": value > expected,
            "gte": value >= expected, "lt": value < expected, "lte": value <= expected,
        }.get(operator)
        return SqlPredicate(and_(number, comparison), True) if comparison is not None else _EVERYTHING
    return _EVERYTHING


def _status(node: dict[str, Any]) -> SqlPredicate:
    column = DataRecordRow.status_id
    operator = node["operator"]
    if operator == "isNull":
        return SqlPredicate(column.is_(None), True)
    if operator == "isNotNull":
        return SqlPredicate(column.is_not(None), True)
    if operator == "eq":
        return SqlPredicate(column == node["statusId"], True)
    return SqlPredicate(and_(column.is_not(None), column != node["statusId"]), True)


def _definite(predicate: SqlPredicate) -> SqlPredicate:
    # SQL NULL (e.g. a missing field) must read as "false", or NOT would drop the row.
    return SqlPredicate(func.coalesce(predicate.clause, 0) == 1, predicate.exact)


def translate_filter(node: dict[str, Any]) -> SqlPredicate:
    """Return a predicate no stricter than the domain filter (see module docstring)."""
    kind = node["type"]
    if kind == "all":
        parts = [translate_filter(item) for item in node["items"]]
        return SqlPredicate(and_(true(), *(part.clause for part in parts)), all(part.exact for part in parts))
    if kind == "any":
        parts = [translate_filter(item) for item in node["items"]]
        if not parts:
            return SqlPredicate(false(), True)
        return SqlPredicate(or_(*(part.clause for part in parts)), all(part.exact for part in parts))
    if kind == "not":
        inner = translate_filter(node["item"])
        return SqlPredicate(not_(inner.clause), True) if inner.exact else _EVERYTHING
    if kind == "status":
        return _definite(_status(node))
    return _definite(_field(node))
