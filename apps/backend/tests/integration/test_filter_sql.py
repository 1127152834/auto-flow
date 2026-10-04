"""Remediation M3 R3-01: SQL claim predicates are never stricter than the domain filter."""

import random
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from autoflow.domain.project_data.query import matches
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_filter_sql import translate_filter

FIELDS = {"s": "string", "n": "number", "b": "boolean"}
VALUES = {
    "s": ["", "abc", "abd", "xabc", "ABC", 5, None, True],
    "n": [0, 1, 1.5, -2, 9007199254740993, "1", None, False],
    "b": [True, False, 1, 0, "true", None],
}
OPERATORS = {
    "s": [("eq", "abc"), ("neq", "abc"), ("contains", "bc"), ("startsWith", "ab"), ("isNull", None), ("isNotNull", None)],
    "n": [("eq", 1), ("neq", 1), ("gt", 0), ("gte", 1.5), ("lt", 1), ("lte", 0), ("eq", 1.5), ("isNull", None)],
    "b": [("eq", True), ("neq", False), ("isNotNull", None)],
}
STATUSES = ["s1", "s2", None]


def leaf(rng):
    if rng.random() < 0.2:
        operator = rng.choice(["eq", "neq", "isNull", "isNotNull"])
        node = {"type": "status", "operator": operator}
        if operator in {"eq", "neq"}:
            node["statusId"] = rng.choice(["s1", "s2"])
        return node
    field = rng.choice(list(FIELDS))
    operator, value = rng.choice(OPERATORS[field])
    node = {"type": "compare", "fieldId": field, "operator": operator}
    if value is not None:
        node["value"] = value
    return node


def tree(rng, depth=0):
    roll = rng.random()
    if depth >= 3 or roll < 0.45:
        return leaf(rng)
    if roll < 0.65:
        return {"type": "not", "item": tree(rng, depth + 1)}
    return {"type": rng.choice(["all", "any"]), "items": [tree(rng, depth + 1) for _ in range(rng.randint(0, 3))]}


def test_random_filters_are_supersets_and_exact_ones_are_equal():
    rng = random.Random(20261003)
    engine = create_engine("sqlite://")
    DataRecordRow.__table__.create(engine)
    now = datetime(2026, 10, 3, tzinfo=UTC)
    rows = []
    with Session(engine) as session:
        for index in range(300):
            values = {}
            for field in FIELDS:
                if rng.random() < 0.85:
                    values[field] = rng.choice(VALUES[field])
            status = rng.choice(STATUSES)
            rows.append((str(index), values, status))
            session.add(DataRecordRow(
                project_id="p", table_id="t", dataset_generation="g", key_type="text", key_value=str(index),
                values_json=values, record_slots=[], status_id=status, current_environment_id=None,
                content_revision=1, status_revision=1, link_revision=1, deleted=False, created_at=now, updated_at=now,
            ))
        session.commit()
        exact_seen = 0
        for _ in range(400):
            node = tree(rng)
            predicate = translate_filter(node)
            selected = set(session.scalars(select(DataRecordRow.key_value).where(predicate.clause)))
            expected = {key for key, values, status in rows if matches(node, values, status)}
            assert expected <= selected, node
            if predicate.exact:
                exact_seen += 1
                assert selected == expected, node
        assert exact_seen > 100
