import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from autoflow.adapters.http.project_run_events import project_run_events_router
from autoflow.application.project_runs.events import ProjectRunEvents
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)
from tests.integration.test_project_run_start import setup, start_payload

NOW = datetime(2026, 9, 15, tzinfo=UTC)


def prepared(tmp_path):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    batch, _, _ = coordinator.start(
        project.project_id,
        automation.automation_id,
        str(uuid4()),
        start_payload(automation),
    )
    task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
    with factory.begin() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        for index, event in enumerate(
            (
                {
                    "kind": "nodeAttempt",
                    "nodeId": "open",
                    "nodeVisitId": "visit",
                    "attempt": 1,
                    "payload": {"status": "started", "privatePath": "/tmp/secret"},
                },
                {
                    "kind": "output",
                    "nodeId": "open",
                    "nodeVisitId": "visit",
                    "attempt": 1,
                    "payload": {
                        "name": "结果",
                        "value": False,
                        "artifactPath": "/tmp/secret",
                    },
                },
            ),
            start=1,
        ):
            repository.append_event(
                {
                    "eventId": str(uuid4()),
                    "runId": task.run_id,
                    "executionGeneration": 0,
                    "occurredAt": NOW.isoformat(),
                    **event,
                }
            )
        row = session.get(WorkflowRunRow, task.run_id)
        assert row is not None
        row.status, row.status_revision, row.completed_at = "succeeded", 2, NOW
    service = ProjectRunEvents(factory)
    app = FastAPI()
    app.include_router(project_run_events_router(service))
    return TestClient(app), service, factory, project, task


def test_json_page_replays_public_persisted_events_without_private_payload(tmp_path):
    client, _, factory, project, task = prepared(tmp_path)
    response = client.get(
        f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}/events"
    )
    assert response.status_code == 200
    page = response.json()
    assert [item["sequence"] for item in page["items"]] == [1, 2]
    assert page["items"][1]["payload"] == {"name": "结果", "value": False}
    assert "/tmp/secret" not in response.text
    assert page["terminal"] is True and page["hasMore"] is False
    factory.dispose()


def test_failure_artifact_event_is_replayable_without_exposing_storage_details(tmp_path):
    client, _, factory, project, task = prepared(tmp_path)
    with factory.begin() as session:
        SqlAlchemyWorkflowRuntimeRepository(session).append_event(
            {
                "eventId": str(uuid4()),
                "runId": task.run_id,
                "executionGeneration": 0,
                "kind": "artifact",
                "nodeId": "click",
                "nodeVisitId": "visit-click",
                "attempt": 1,
                "occurredAt": NOW.isoformat(),
                "payload": {
                    "artifactId": str(uuid4()),
                    "kind": "screenshot",
                    "purpose": "error",
                    "availability": "available",
                    "relativePath": (
                        f"runs/{task.run_id}/generation-0/"
                        "6c1fa28a-ef24-47c0-a476-7780bf84dfeb.png"
                    ),
                    "mediaType": "image/png",
                    "byteSize": 42,
                    "sha256": "d" * 64,
                },
            }
        )

    response = client.get(
        f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}/events",
        params={"afterSequence": 2},
    )

    assert response.status_code == 200
    event = response.json()["items"][0]
    assert event["kind"] == "artifact"
    assert event["payload"] == {
        "artifactId": event["payload"]["artifactId"],
        "kind": "screenshot",
        "purpose": "error",
        "availability": "available",
    }
    assert "generation-0" not in response.text
    assert "d" * 64 not in response.text
    factory.dispose()


def test_user_log_identity_survives_event_replay_without_private_fields(tmp_path):
    client, _, factory, project, task = prepared(tmp_path)
    with factory.begin() as session:
        SqlAlchemyWorkflowRuntimeRepository(session).append_event(
            {
                "eventId": str(uuid4()), "runId": task.run_id,
                "executionGeneration": 0, "kind": "log", "nodeId": "open",
                "nodeVisitId": "visit", "attempt": 1,
                "occurredAt": NOW.isoformat(),
                "payload": {"level": "error", "message": "需要人工复核", "isUserLog": True, "privatePath": "/tmp/secret"},
            }
        )
    path = f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}/events"
    response = client.get(path, params={"afterSequence": 2})
    assert response.status_code == 200
    assert response.json()["items"][0]["payload"] == {
        "level": "error", "message": "需要人工复核", "isUserLog": True,
    }
    assert "/tmp/secret" not in response.text
    factory.dispose()


def test_repeated_cursor_is_empty_and_sse_last_event_id_replays_only_the_gap(tmp_path):
    client, _, factory, project, task = prepared(tmp_path)
    path = f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}/events"
    assert client.get(path, params={"afterSequence": 2}).json()["items"] == []
    response = client.get(f"{path}/stream", headers={"Last-Event-ID": "1"})
    assert response.status_code == 200
    blocks = [block for block in response.text.split("\n\n") if block]
    assert len(blocks) == 1 and blocks[0].startswith("id: 2\nevent: output\n")
    data = json.loads(blocks[0].split("data: ", 1)[1])
    assert data["sequence"] == 2
    factory.dispose()


def test_gap_and_future_cursor_are_explicitly_rejected(tmp_path):
    _, service, factory, project, task = prepared(tmp_path)
    with factory.begin() as session:
        session.execute(
            delete(WorkflowRunEventRow).where(
                WorkflowRunEventRow.run_id == task.run_id,
                WorkflowRunEventRow.sequence == 1,
            )
        )
    with pytest.raises(ProjectRunError) as gap:
        service.page(project.project_id, task.task_id, 0)
    with pytest.raises(ProjectRunError) as future:
        service.page(project.project_id, task.task_id, 3)
    assert gap.value.code == "RUN_EVENT_HISTORY_UNAVAILABLE"
    assert future.value.status == 422
    factory.dispose()


def test_missing_tail_is_rejected_before_returning_a_partial_page(tmp_path):
    _, service, factory, project, task = prepared(tmp_path)
    with factory.begin() as session:
        session.execute(
            delete(WorkflowRunEventRow).where(
                WorkflowRunEventRow.run_id == task.run_id,
                WorkflowRunEventRow.sequence == 2,
            )
        )

    with pytest.raises(ProjectRunError) as caught:
        service.page(project.project_id, task.task_id, 0)

    assert caught.value.code == "RUN_EVENT_HISTORY_UNAVAILABLE"
    factory.dispose()


def test_page_uses_one_snapshot_when_an_event_commits_after_run_read(
    tmp_path, monkeypatch
):
    _, service, factory, project, task = prepared(tmp_path)
    with factory() as session:
        session.execute(text("PRAGMA journal_mode=WAL"))
    original = SqlAlchemyWorkflowRuntimeRepository.get_run
    injected = False

    def get_run_then_commit(self, **identity):
        nonlocal injected
        run = original(self, **identity)
        if not injected:
            injected = True
            with factory.begin() as writer:
                SqlAlchemyWorkflowRuntimeRepository(writer).append_event(
                    {
                        "eventId": str(uuid4()),
                        "runId": task.run_id,
                        "executionGeneration": 0,
                        "kind": "log",
                        "occurredAt": NOW.isoformat(),
                        "payload": {"level": "info", "message": "稍后提交"},
                    }
                )
        return run

    monkeypatch.setattr(
        SqlAlchemyWorkflowRuntimeRepository, "get_run", get_run_then_commit
    )

    page = service.page(project.project_id, task.task_id, 0)

    assert page["lastSequence"] == page["afterSequence"] == 2
    assert [item["sequence"] for item in page["items"]] == [1, 2]
    assert (
        service.page(project.project_id, task.task_id, 2)["items"][0]["sequence"] == 3
    )
    factory.dispose()


def test_cross_project_task_is_not_visible(tmp_path):
    _, service, factory, _, task = prepared(tmp_path)
    with pytest.raises(ProjectRunError) as caught:
        service.page(str(uuid4()), task.task_id)
    assert caught.value.code == "NOT_FOUND"
    factory.dispose()
