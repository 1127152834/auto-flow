from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_assistant import (
    SqlAlchemyWorkflowAssistant,
)


def test_assistant_session_and_confirmed_tool_result_survive_reopen(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    first = create_session_factory(database)
    repository = SqlAlchemyWorkflowAssistant(first)
    created = repository.create("session-1", "新对话", now=datetime.now(UTC))
    saved = repository.save(
        created.with_changes(
            messages=({"id": "user-1", "role": "user", "content": "添加节点"},),
            status="waiting_for_action",
            pending_action={
                "commandId": "tool-1",
                "action": "add_nodes",
                "payload": {"nodes": [{"type": "open_page"}]},
            },
        )
    )
    command, created_command = repository.confirm_command(
        "tool-1",
        "session-1",
        request_hash="same-request",
        result={"success": True, "data": {"nodeIds": ["node-1"]}},
        now=datetime.now(UTC),
    )
    first.dispose()

    second = create_session_factory(database)
    restored = SqlAlchemyWorkflowAssistant(second)

    assert restored.get("session-1") == saved
    assert restored.get_command("tool-1") == command
    assert created_command is True
    second.dispose()


def test_assistant_command_id_is_idempotent_and_rejects_other_payload(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    repository = SqlAlchemyWorkflowAssistant(factory)
    repository.create("session-1", "新对话", now=datetime.now(UTC))
    original, created = repository.confirm_command(
        "tool-1",
        "session-1",
        request_hash="same-request",
        result={"success": True},
        now=datetime.now(UTC),
    )
    replay, replay_created = repository.confirm_command(
        "tool-1",
        "session-1",
        request_hash="same-request",
        result={"success": True},
        now=datetime.now(UTC),
    )

    assert created is True and replay_created is False and replay == original
    with pytest.raises(ValueError, match="commandId 已用于不同请求"):
        repository.confirm_command(
            "tool-1",
            "session-1",
            request_hash="different-request",
            result={"success": False},
            now=datetime.now(UTC),
        )
    factory.dispose()
