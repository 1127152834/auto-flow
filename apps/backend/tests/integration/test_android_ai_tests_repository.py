from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android_ai_tests import AiTestRepository
from autoflow.infrastructure.database.models import Base

T0 = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.fixture
def repo(tmp_path: Path) -> AiTestRepository:
    engine = create_engine(f"sqlite:///{tmp_path / 'ai.sqlite3'}")
    Base.metadata.create_all(engine)
    return AiTestRepository(sessionmaker(engine, expire_on_commit=False))


def run(n: int, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"run-{n}", "requestId": f"req-{n}", "deviceKind": "managed", "deviceId": "dev-1", "serial": None,
        "state": "queued", "createdAt": (T0 + timedelta(minutes=n)).isoformat(), "startedAt": None,
        "finishedAt": None, "instruction": "打开设置", "requestDigest": f"digest-{n}", **extra,
    }


def test_create_is_idempotent_and_detects_conflict(repo: AiTestRepository) -> None:
    first = repo.create(run(1))
    assert first["id"] == "run-1" and first["instruction"] == "打开设置"
    again = repo.create({**run(1), "id": "run-other"})
    assert again["id"] == "run-1"
    with pytest.raises(AndroidError) as err:
        repo.create({**run(1), "id": "run-other", "requestDigest": "different"})
    assert (err.value.code, err.value.status) == ("ANDROID_REQUEST_CONFLICT", 409)


def test_get_missing_and_update_splits_columns_and_payload(repo: AiTestRepository) -> None:
    with pytest.raises(AndroidError) as err:
        repo.get("nope")
    assert (err.value.code, err.value.status) == ("AI_TEST_NOT_FOUND", 404)
    repo.create(run(1))
    started = T0.isoformat()
    updated = repo.update("run-1", state="running", startedAt=started, traceId="t1")
    assert updated["state"] == "running" and updated["traceId"] == "t1"
    assert updated["startedAt"] == started
    assert repo.get("run-1")["traceId"] == "t1"


def test_append_step_keeps_last_200(repo: AiTestRepository) -> None:
    repo.create(run(1))
    for i in range(205):
        repo.append_step("run-1", {"n": i})
    steps = repo.get("run-1")["steps"]
    assert len(steps) == 200 and steps[0] == {"n": 5} and steps[-1] == {"n": 204}


def test_list_pages_newest_first_and_scopes_device(repo: AiTestRepository) -> None:
    for n in range(5):
        repo.create(run(n))
    repo.create(run(9, deviceId="dev-2"))
    repo.create(run(10, deviceKind="external", deviceId=None, serial="S1"))
    page1, cursor = repo.list("managed", "dev-1", None, None, limit=2)
    assert [r["id"] for r in page1] == ["run-4", "run-3"] and cursor
    page2, cursor = repo.list("managed", "dev-1", None, cursor, limit=2)
    assert [r["id"] for r in page2] == ["run-2", "run-1"] and cursor
    page3, cursor = repo.list("managed", "dev-1", None, cursor, limit=2)
    assert [r["id"] for r in page3] == ["run-0"] and cursor is None
    assert [r["id"] for r in repo.list("external", None, "S1", None)[0]] == ["run-10"]


def test_active_unfinished_and_delete(repo: AiTestRepository) -> None:
    repo.create(run(1, state="succeeded"))
    repo.create(run(2, state="running"))
    repo.create(run(3, deviceId="dev-2"))
    active = repo.active_for("managed", "dev-1", None)
    assert active is not None and active["id"] == "run-2"
    assert repo.active_for("managed", "dev-9", None) is None
    assert {r["id"] for r in repo.unfinished()} == {"run-2", "run-3"}
    assert repo.delete("run-2")["id"] == "run-2"
    with pytest.raises(AndroidError):
        repo.get("run-2")
