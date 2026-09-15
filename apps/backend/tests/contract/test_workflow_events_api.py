from __future__ import annotations

import asyncio

import pytest
from autoflow.adapters.events.workflows import StudioEvent, StudioEventJournal, _frame
from autoflow.domain.workflows.runs import WorkflowRunError


@pytest.mark.asyncio
async def test_event_journal_replays_strict_sequence_without_duplicates() -> None:
    journal = StudioEventJournal()
    first = await journal.publish("execution:started", {"runId": "run-1"})
    second = await journal.publish(
        "execution:log", {"runId": "run-1", "message": "中文日志"}
    )

    assert [item.sequence for item in journal.replay(after_sequence=0)] == [1, 2]
    assert journal.replay(after_sequence=1) == (second,)
    assert first.event == "execution:started"

    async with journal.subscribe(after_sequence=2) as stream:
        third = await journal.publish("execution:completed", {"runId": "run-1"})
        assert await asyncio.wait_for(stream.get(), timeout=1) == third


def test_event_journal_rejects_impossible_resume_cursor() -> None:
    journal = StudioEventJournal()

    with pytest.raises(WorkflowRunError) as invalid:
        journal.replay(after_sequence=1)

    assert invalid.value.code == "EVENT_CURSOR_AHEAD"


def test_sse_frame_preserves_event_identity_and_utf8() -> None:
    assert _frame(
        StudioEvent(7, "execution:log", {"runId": "run-1", "message": "中文"})
    ).decode() == (
        'id: 7\nevent: execution:log\ndata: {"runId":"run-1","message":"中文"}\n\n'
    )
