from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path

import pytest
from sqlalchemy.exc import DatabaseError

from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.domain.workflows.errors import WorkflowDocumentError
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments


def _payload(name: str = "真实工作流") -> dict:
    return {
        "name": name,
        "schemaVersion": 3,
        "nodes": [
            {
                "id": "open",
                "type": "open_page",
                "position": {"x": 10, "y": 20},
                "selected": True,
                "data": {"moduleType": "open_page", "url": "https://example.invalid"},
            }
        ],
        "edges": [],
        "variables": [],
    }


@pytest.fixture
def service(tmp_path: Path) -> WorkflowDocumentService:
    database = tmp_path / "workflows.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowDocuments(create_session_factory(database))
    minutes = count()
    return WorkflowDocumentService(
        repository,
        clock=lambda: (
            datetime(2026, 9, 15, 1, 0, tzinfo=UTC) + timedelta(minutes=next(minutes))
        ),
    )


def test_create_read_update_list_and_delete_roundtrip(
    service: WorkflowDocumentService,
) -> None:
    created = service.create(_payload(), client_request_id="create-request")
    assert created.id
    assert created.revision == 1
    assert created.to_payload()["nodes"][0]["position"] == {"x": 10, "y": 20}
    assert "selected" not in created.to_payload()["nodes"][0]

    loaded = service.get(created.id)
    assert loaded == created

    changed_payload = created.to_payload()
    changed_payload["name"] = "更新名称"
    changed_payload["future"] = {"preserved": True}
    changed = service.update(
        created.id,
        changed_payload,
        expected_revision=1,
        client_request_id="update-request",
    )
    assert changed.revision == 2
    assert changed.name == "更新名称"
    assert changed.to_payload()["future"] == {"preserved": True}

    page = service.list_summaries(cursor=0, limit=20)
    assert [item.id for item in page.items] == [created.id]
    assert page.items[0].revision == 2
    assert page.next_cursor is None

    service.delete(created.id, expected_revision=2)
    with pytest.raises(WorkflowDocumentError) as raised:
        service.get(created.id)
    assert raised.value.code == "WORKFLOW_NOT_FOUND"


def test_create_and_update_requests_are_idempotent_and_detect_reuse(
    service: WorkflowDocumentService,
) -> None:
    first = service.create(_payload(), client_request_id="stable-create")
    repeated = service.create(_payload(), client_request_id="stable-create")
    assert repeated == first

    with pytest.raises(WorkflowDocumentError) as reused:
        service.create(_payload("不同请求"), client_request_id="stable-create")
    assert reused.value.code == "IDEMPOTENCY_CONFLICT"

    payload = first.to_payload()
    payload["name"] = "第二版"
    updated = service.update(
        first.id,
        payload,
        expected_revision=1,
        client_request_id="stable-update",
    )
    assert (
        service.update(
            first.id,
            payload,
            expected_revision=1,
            client_request_id="stable-update",
        )
        == updated
    )


def test_revision_conflict_keeps_current_document(
    service: WorkflowDocumentService,
) -> None:
    created = service.create(_payload(), client_request_id="create")
    payload = created.to_payload()
    payload["name"] = "不会覆盖"

    with pytest.raises(WorkflowDocumentError) as raised:
        service.update(
            created.id,
            payload,
            expected_revision=9,
            client_request_id="stale-update",
        )

    assert raised.value.code == "WORKFLOW_REVISION_CONFLICT"
    assert raised.value.details == {"expectedRevision": 9, "currentRevision": 1}
    assert service.get(created.id).name == "真实工作流"


def test_update_failure_rolls_back_document_and_idempotency_receipt(
    tmp_path: Path,
) -> None:
    database = tmp_path / "rollback.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowDocuments(create_session_factory(database))
    now = datetime(2026, 9, 15, tzinfo=UTC)
    service = WorkflowDocumentService(repository, clock=lambda: now)
    created = service.create(_payload(), client_request_id="create")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_workflow_update BEFORE UPDATE ON workflow_documents
            BEGIN SELECT RAISE(ABORT, 'synthetic workflow write failure'); END
            """
        )
    payload = created.to_payload()
    payload["name"] = "不得部分保存"

    with pytest.raises(DatabaseError):
        service.update(
            created.id,
            payload,
            expected_revision=1,
            client_request_id="failed-update",
        )

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT name, revision FROM workflow_documents WHERE id=?", (created.id,)
        ).fetchone() == ("真实工作流", 1)
        assert connection.execute(
            "SELECT COUNT(*) FROM workflow_document_requests WHERE id='failed-update'"
        ).fetchone() == (0,)


def test_summaries_use_recent_update_order_and_stable_cursor(tmp_path: Path) -> None:
    database = tmp_path / "pages.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowDocuments(create_session_factory(database))
    start = datetime(2026, 9, 15, tzinfo=UTC)
    index = 0

    def clock() -> datetime:
        nonlocal index
        value = start + timedelta(minutes=index)
        index += 1
        return value

    service = WorkflowDocumentService(repository, clock=clock)
    created = [
        service.create(_payload(f"流程 {number}"), client_request_id=f"create-{number}")
        for number in range(3)
    ]

    first = service.list_summaries(cursor=0, limit=2)
    second = service.list_summaries(cursor=first.next_cursor or 0, limit=2)
    assert [item.id for item in first.items] == [created[2].id, created[1].id]
    assert [item.id for item in second.items] == [created[0].id]
