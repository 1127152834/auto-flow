"""Remediation M3 R3-01: SQL claim order equals the original Python claim collation."""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from autoflow.infrastructure.database import project_claims
from autoflow.infrastructure.database.project_data_models import DataRecordRow

FIELDS = {"s": "string", "n": "number", "b": "boolean"}
SAMPLES = {
    "s": ["a", "b", "B", "ä", "", 3, None, True, "a"],
    "n": [1, 2, 2.5, -1, 9007199254740993, "x", None, False, 2],
    "b": [True, False, 1, "no", None, True],
}
STATUS_ORDER = {"st-b": (0, "st-b"), "st-a": (1, "st-a")}


def keys(session, order, native):
    query = select(DataRecordRow).where(DataRecordRow.dataset_generation == "g", text("project_data_records.deleted = 0"))
    original = project_claims.native_claim_order
    try:
        if not native:
            project_claims.native_claim_order = lambda *_args: None
        rows = project_claims._ordered_candidate_rows(session, query, order, FIELDS, STATUS_ORDER, 0, 1000)
    finally:
        project_claims.native_claim_order = original
    return [(row.key_type, row.key_value) for row in rows]


def test_random_orders_match_the_collation():
    rng = random.Random(7)
    engine = create_engine("sqlite://")
    DataRecordRow.__table__.create(engine)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(engine) as session:
        for index in range(160):
            key_type = rng.choice(["text", "integer", "uuid"])
            key_value = str(rng.randint(-50, 500) * 1000 + index) if key_type == "integer" else f"{key_type}-{index:03d}"
            values = {field: rng.choice(choices) for field, choices in SAMPLES.items() if rng.random() < 0.85}
            stamp = start + timedelta(minutes=rng.randint(0, 20))
            session.add(DataRecordRow(
                project_id="p", table_id="t", dataset_generation="g", key_type=key_type, key_value=key_value,
                values_json=values, record_slots=[], status_id=rng.choice([None, "st-a", "st-b", "gone"]),
                current_environment_id=None, content_revision=1, status_revision=1, link_revision=1,
                deleted=False, created_at=stamp, updated_at=stamp,
            ))
            session.flush()
        session.commit()
        targets = [{"fieldId": "s"}, {"fieldId": "n"}, {"fieldId": "b"}, {"systemField": "status"},
                   {"systemField": "createdAt"}, {"systemField": "updatedAt"}, {"systemField": "recordKey"}]
        for _ in range(120):
            order = [{**target, "direction": rng.choice(["asc", "desc"])} for target in rng.sample(targets, rng.randint(0, 3))]
            assert keys(session, order, native=True) == keys(session, order, native=False), order
