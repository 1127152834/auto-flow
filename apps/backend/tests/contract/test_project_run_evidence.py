from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.project_run_evidence import project_run_evidence_router
from autoflow.application.project_runs.evidence import ProjectRunEvidence
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
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
        events = [
            ("nodeAttempt", {"status": "started"}, "visit-1", 1),
            ("log", {"level": "warning", "message": "先忽略"}, "visit-1", 1),
            ("log", {"level": "info", "message": "已打开"}, "visit-1", 1),
            ("output", {"name": "标题", "value": {"ok": True}}, "visit-1", 1),
            ("nodeAttempt", {"status": "succeeded", "durationMs": 4}, "visit-1", 1),
        ]
        for index, (kind, payload, visit, attempt) in enumerate(events):
            repository.append_event(
                {
                    "eventId": str(uuid4()),
                    "runId": task.run_id,
                    "executionGeneration": 0,
                    "kind": kind,
                    "nodeId": "open",
                    "nodeVisitId": visit,
                    "attempt": attempt,
                    "occurredAt": (NOW + timedelta(seconds=index)).isoformat(),
                    "payload": payload,
                }
            )
    app = FastAPI()
    install_error_handlers(app)
    evidence = ProjectRunEvidence(factory, tmp_path / "workspace")
    app.include_router(project_run_evidence_router(evidence))
    return TestClient(app), evidence, factory, project, task


def add_artifact(factory, task, root, *, available=True):
    artifact_id = str(uuid4())
    relative_path = (
        f"runs/{task.run_id}/generation-0/{artifact_id}.png" if available else None
    )
    content = b"png" if available else None
    if relative_path and content:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    with factory.begin() as session:
        SqlAlchemyWorkflowRuntimeRepository(session).append_event(
            {
                "eventId": str(uuid4()),
                "runId": task.run_id,
                "executionGeneration": 0,
                "kind": "artifact",
                "nodeId": "open",
                "nodeVisitId": "visit-artifact",
                "attempt": 1,
                "occurredAt": NOW.isoformat(),
                "payload": {
                    "artifactId": artifact_id,
                    "kind": "screenshot",
                    "purpose": "error",
                    "availability": "available" if available else "unavailable",
                    "relativePath": relative_path,
                    "mediaType": "image/png" if available else None,
                    "byteSize": len(content) if content else None,
                    "sha256": sha256(content).hexdigest() if content else None,
                    "unavailableReason": None
                    if available
                    else "SCREENSHOT_CAPTURE_FAILED",
                    "createdAt": NOW.isoformat(),
                },
            }
        )
    return artifact_id, content


def test_reads_persisted_attempt_logs_and_value_outputs(tmp_path):
    client, _, factory, project, task = prepared(tmp_path)
    prefix = f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}"

    attempt = client.get(f"{prefix}/node-attempts").json()["items"][0]
    assert attempt["nodeVisitId"] == "visit-1"
    assert attempt["status"] == "succeeded"
    assert attempt["startedAt"] and attempt["completedAt"]

    logs = client.get(f"{prefix}/logs", params={"level": "info", "pageSize": 1}).json()
    assert [item["message"] for item in logs["items"]] == ["已打开"]
    assert logs["items"][0]["sequence"] == 3
    assert logs["afterSequence"] == 3
    assert logs["lastSequence"] == 5

    output = client.get(f"{prefix}/outputs").json()["items"][0]
    assert output["kind"] == "value"
    assert output["value"] == {"ok": True}
    assert output["nodeVisitId"] == "visit-1" and output["sequence"] == 4
    assert "artifactId" not in output
    factory.dispose()


def test_log_cursor_does_not_skip_a_later_matching_event(tmp_path):
    client, _, factory, project, task = prepared(tmp_path)
    path = f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}/logs"

    first = client.get(path, params={"pageSize": 1}).json()
    second = client.get(
        path, params={"pageSize": 1, "afterSequence": first["afterSequence"]}
    ).json()

    assert first["items"][0]["sequence"] == 2 and first["hasMore"] is True
    assert second["items"][0]["sequence"] == 3 and second["hasMore"] is False
    factory.dispose()


def test_log_message_search_composes_with_filters_and_keeps_sequence_cursor(tmp_path):
    client, _, factory, project, task = prepared(tmp_path)
    path = f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}/logs"
    with factory.begin() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        for index, (level, message) in enumerate(
            [
                ("info", "其他日志"),
                ("info", "TARGET 第一条"),
                ("error", "target 级别不符"),
                ("info", "Target 第二条"),
            ]
        ):
            repository.append_event(
                {
                    "eventId": str(uuid4()),
                    "runId": task.run_id,
                    "executionGeneration": 0,
                    "kind": "log",
                    "nodeId": "search-node",
                    "nodeVisitId": "visit-search",
                    "attempt": 1,
                    "occurredAt": (NOW + timedelta(seconds=10 + index)).isoformat(),
                    "payload": {"level": level, "message": message},
                }
            )

    first = client.get(
        path,
        params={
            "query": "target",
            "nodeId": "search-node",
            "level": "info",
            "pageSize": 1,
        },
    ).json()
    second = client.get(
        path,
        params={
            "query": "target",
            "nodeId": "search-node",
            "level": "info",
            "pageSize": 1,
            "afterSequence": first["afterSequence"],
        },
    ).json()

    assert [item["message"] for item in first["items"]] == ["TARGET 第一条"]
    assert first["hasMore"] is True
    assert [item["message"] for item in second["items"]] == ["Target 第二条"]
    assert second["items"][0]["sequence"] > first["afterSequence"]
    assert second["hasMore"] is False
    factory.dispose()


def test_evidence_is_strictly_project_and_task_scoped(tmp_path):
    _, evidence, factory, _, task = prepared(tmp_path)

    with pytest.raises(ProjectRunError) as caught:
        evidence.outputs(str(uuid4()), task.task_id)

    assert caught.value.code == "NOT_FOUND"
    factory.dispose()


def test_lists_and_reads_a_project_scoped_screenshot_without_exposing_a_path(tmp_path):
    client, _, factory, project, task = prepared(tmp_path)
    artifact_id, content = add_artifact(factory, task, tmp_path / "workspace")
    prefix = f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}/artifacts"

    page = client.get(prefix).json()
    assert page["total"] == 1
    assert page["items"][0] == {
        "artifactId": artifact_id,
        "kind": "screenshot",
        "purpose": "error",
        "availability": "available",
        "nodeId": "open",
        "nodeVisitId": "visit-artifact",
        "eventSequence": 6,
        "executionGeneration": 0,
        "mediaType": "image/png",
        "byteSize": 3,
        "sha256": sha256(b"png").hexdigest(),
        "createdAt": NOW.isoformat().replace("+00:00", "Z"),
        "unavailableReason": None,
        "contentUrl": f"{prefix}/{artifact_id}/content",
    }
    assert "relativePath" not in page["items"][0]
    assert client.get(f"{prefix}/{artifact_id}").json() == page["items"][0]
    response = client.get(f"{prefix}/{artifact_id}/content")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == content
    factory.dispose()


def test_unavailable_or_corrupt_artifact_is_explicit_and_never_reads_outside_workspace(
    tmp_path,
):
    client, _, factory, project, task = prepared(tmp_path)
    unavailable_id, _ = add_artifact(
        factory, task, tmp_path / "workspace", available=False
    )
    prefix = f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}/artifacts"

    item = client.get(f"{prefix}/{unavailable_id}").json()
    assert item["availability"] == "unavailable"
    response = client.get(f"{prefix}/{unavailable_id}/content")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_ARTIFACT_UNAVAILABLE"

    artifact_id, _ = add_artifact(factory, task, tmp_path / "workspace")
    path = (
        tmp_path
        / "workspace"
        / "runs"
        / task.run_id
        / "generation-0"
        / f"{artifact_id}.png"
    )
    path.unlink()
    path.symlink_to(tmp_path / "outside.png")
    (tmp_path / "outside.png").write_bytes(b"secret")
    response = client.get(f"{prefix}/{artifact_id}/content")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_ARTIFACT_UNAVAILABLE"
    factory.dispose()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"after_sequence": -1},
        {"page_size": 0},
        {"page_size": 201},
    ],
)
def test_log_cursor_and_page_size_are_bounded(tmp_path, kwargs):
    _, evidence, factory, project, task = prepared(tmp_path)

    with pytest.raises(ProjectRunError) as caught:
        evidence.logs(project.project_id, task.task_id, **kwargs)

    assert caught.value.status == 422
    factory.dispose()


@pytest.mark.parametrize("kind", ["gap", "future"])
def test_incomplete_event_history_never_advances_cursor_as_if_complete(tmp_path, kind):
    from sqlalchemy import delete

    from autoflow.infrastructure.database.workflow_runtime_models import (
        WorkflowRunEventRow,
    )

    _, evidence, factory, project, task = prepared(tmp_path)
    if kind == "gap":
        with factory.begin() as session:
            session.execute(
                delete(WorkflowRunEventRow).where(
                    WorkflowRunEventRow.run_id == task.run_id,
                    WorkflowRunEventRow.sequence == 2,
                )
            )
    with pytest.raises(ProjectRunError) as error:
        evidence.logs(
            project.project_id,
            task.task_id,
            after_sequence=100 if kind == "future" else 0,
        )
    assert error.value.code == "RUN_EVENT_HISTORY_UNAVAILABLE"
    factory.dispose()
