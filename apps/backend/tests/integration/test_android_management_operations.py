from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


@pytest.fixture
def repository(tmp_path: Path) -> SqlAlchemyAndroidOperationRepository:
    database = tmp_path / "android-management.sqlite3"
    migrate_database(database)
    return SqlAlchemyAndroidOperationRepository(create_session_factory(database))


def test_request_id_is_idempotent_and_digest_conflict_is_rejected(repository):
    first = repository.accept("ws", "r1", "d1", "stop", "digest-a", {})
    again = repository.accept("ws", "r1", "d1", "stop", "digest-a", {})
    assert again.operation_id == first.operation_id
    with pytest.raises(AndroidError) as error:
        repository.accept("ws", "r1", "d2", "stop", "digest-b", {})
    assert error.value.status == 409


def test_transition_requires_expected_state_and_unknown_result_is_readable(repository):
    operation = repository.accept("ws", "r2", "d1", "start", "digest", {})
    running = repository.transition(operation.operation_id, "queued", "running", {"stage_code": "starting"})
    assert running.state == "running"
    with pytest.raises(AndroidError):
        repository.transition(operation.operation_id, "queued", "succeeded", {})
    unknown = repository.transition(operation.operation_id, "running", "needs_verification", {"message": "响应丢失"})
    assert unknown.state == "needs_verification"


def test_compaction_keeps_request_receipt(repository):
    first = repository.accept("ws", "old", "d", "stop", "hash", {"verbose": "detail"})
    repository.transition(first.operation_id, "queued", "cancelled", {})
    assert repository.compact(datetime.now(UTC) + timedelta(days=1)) == 1
    assert repository.by_request("ws", "old").operation_id == first.operation_id
    assert repository.accept("ws", "old", "d", "stop", "hash", {}).operation_id == first.operation_id
    with pytest.raises(AndroidError):
        repository.accept("ws", "old", "other", "stop", "other", {})


def test_terminal_operations_cannot_be_replayed(repository):
    first = repository.accept("ws", "closed", "d", "stop", "hash", {})
    repository.transition(first.operation_id, "queued", "cancelled", {})
    with pytest.raises(AndroidError):
        repository.transition(first.operation_id, "cancelled", "running", {})


def test_cursor_matches_timestamp_order(repository):
    expected = [repository.accept("ws", f"r{i}", "d", "stop", str(i), {}).operation_id for i in range(12)][::-1]
    seen = []
    cursor = None
    while page := repository.page(cursor=cursor, limit=2):
        seen.extend(item.operation_id for item in page)
        cursor = page[-1].operation_id
    assert seen == expected
