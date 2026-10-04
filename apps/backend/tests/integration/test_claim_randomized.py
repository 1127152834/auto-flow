"""Remediation M3 AC3-07: randomized filters and concurrency claim every match exactly once."""

import random

import pytest
from sqlalchemy import select

from autoflow.domain.project_data.query import matches
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from tests.integration.test_record_ledger_claims import World

SCENARIOS = 26  # 1,052 claims in total with these seeds (counted 2026-10-03)
ROWS = 95  # with the fixture row at most 96 matches, inside one 100-unit batch


def leaf(rng, field_id):
    operator = rng.choice(["eq", "neq", "contains", "startsWith", "isNotNull"])
    node = {"type": "compare", "fieldId": field_id, "operator": operator}
    if operator != "isNotNull":
        node["value"] = rng.choice(["v-1", "v-2", "v-", "1", "v-3"])
    return node


def tree(rng, field_id, depth=0):
    roll = rng.random()
    if depth >= 2 or roll < 0.4:
        return leaf(rng, field_id)
    if roll < 0.55:
        return {"type": "not", "item": tree(rng, field_id, depth + 1)}
    return {"type": rng.choice(["all", "any"]), "items": [tree(rng, field_id, depth + 1) for _ in range(rng.randint(1, 3))]}


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", range(SCENARIOS))
async def test_random_filters_and_concurrency_claim_each_match_once(tmp_path, scenario):
    rng = random.Random(1000 + scenario)
    world = World(tmp_path, claimMode="unprocessed", concurrency=4, maxLiveInstances=4)
    for index in range(ROWS):
        world.add_person(f"v-{rng.randint(0, 40)}-{index}")
    node = tree(rng, world.field_id)
    with world.factory.begin() as session:
        row = session.get(ProjectAutomationRow, world.automation.automation_id)
        plan = dict(row.input_plan)
        plan["inputs"] = [dict(item) for item in plan["inputs"]]
        plan["inputs"][0]["filter"] = node
        plan["inputs"][0]["orderBy"] = rng.choice([
            [{"systemField": "recordKey", "direction": "asc"}],
            [{"fieldId": world.field_id, "direction": rng.choice(["asc", "desc"])}],
            [{"systemField": "createdAt", "direction": "desc"}],
        ])
        row.input_plan = plan
    with world.factory() as session:
        records = session.scalars(select(DataRecordRow).where(DataRecordRow.table_id == world.people_table)).all()
        expected = sorted(record.values_json[world.field_id] for record in records if matches(node, record.values_json, record.status_id))
    batch = world.start(max_tasks=100)
    with world.factory.begin() as session:
        stored = session.get(ProjectBatchRow, batch.batch_id)
        stored.frozen_request = {**stored.frozen_request, "concurrency": rng.randint(1, 4)}
    for _ in range(4 * ROWS):  # bounded: a claim loop that never ends fails the test
        await world.settle(rounds=1)
        if world.batch(batch.batch_id).status in {"completed", "failed", "stopped", "interrupted"}:
            break
    claimed = world.processed_people(batch.batch_id)
    assert world.batch(batch.batch_id).status == "completed", (node, claimed)
    assert sorted(claimed) == expected, node
