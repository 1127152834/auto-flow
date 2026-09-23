from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.events.workflows import StudioEvent, _frame, _scope_run_event
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.workflow_runs import (
    workflow_runs_router,
    workflow_variable_tracking_router,
)
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.domain.workflows.runs import WorkflowRunStart
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import WorkflowRunRow
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments


@pytest.fixture
def scoped_runs(tmp_path):
    database = tmp_path / "project-runs.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    with factory() as session:
        for project_id in ("a", "b"):
            session.add(ProjectRow(id=project_id, name=project_id, name_key=project_id,
                description="", search_text=project_id, default_resources={}, management_revision=1,
                lifecycle_state="active", created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
        session.commit()
    service = WorkflowRunService(SqlAlchemyWorkflowRuns(factory))
    for run_id, project_id in (("a-first", "a"), ("b-middle", "b"), ("a-last", "a")):
        service.start(WorkflowRunStart(run_id, run_id, run_id, run_id, {"nodes": []}, {}, "profile", {}, "run", project_id=project_id))
        service.finish(run_id, status="completed", cleanup_completed=True)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflow_runs_router(service, tmp_path))
    app.include_router(workflow_variable_tracking_router(service, tmp_path))
    with TestClient(app) as client:
        yield client, factory, service
    factory.dispose()


def test_project_run_pagination_filters_before_count_and_preserves_archived_history(scoped_runs):
    client, factory, _ = scoped_runs
    page = client.get("/api/workflow-runs?projectId=a&limit=1").json()
    assert page["total"] == 2
    assert [item["runId"] for item in page["items"]] == ["a-last"]
    assert page["nextCursor"] == 1
    second = client.get("/api/workflow-runs?projectId=a&limit=1&cursor=1").json()
    assert [item["runId"] for item in second["items"]] == ["a-first"]
    assert second["nextCursor"] is None
    assert client.get("/api/workflow-runs?projectId=b&documentId=a-first").json()["total"] == 0
    with factory() as session:
        session.get(ProjectRow, "a").lifecycle_state = "archived"
        session.commit()
    assert client.get("/api/workflow-runs?projectId=a").json()["total"] == 2
    assert client.get("/api/workflow-runs/a-first?projectId=a").status_code == 200
    with factory() as session:
        session.get(ProjectRow, "a").lifecycle_state = "deleted"
        session.commit()
    assert client.get("/api/workflow-runs?projectId=a").json()["total"] == 0
    assert client.get("/api/workflow-runs/a-first?projectId=a").status_code == 404
    assert client.get("/api/workflow-runs/a-first").status_code == 404


@pytest.mark.parametrize("path", [
    "", "/logs", "/logs/export", "/results", "/results/export?throughSequence=1",
    "/results/1/value?key=secret", "/artifacts", "/artifacts/asset",
    "/variable-tracking", "/variable-tracking/values?sequence=1&side=new_value",
    "/variable-tracking/export?throughSequence=1",
])
def test_cross_project_run_read_and_export_are_rejected_at_shared_boundary(scoped_runs, path):
    client, _, _ = scoped_runs
    separator = "&" if "?" in path else "?"
    response = client.get(f"/api/workflow-runs/a-first{path}{separator}projectId=b")
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_cross_project_diagnostic_clear_is_rejected(scoped_runs):
    client, _, service = scoped_runs
    before = service.get("a-first").event_count
    response = client.delete("/api/workflow-runs/a-first/variable-tracking?projectId=b")
    assert response.status_code == 404
    assert service.get("a-first").event_count == before


def test_legacy_saved_run_resolves_owner_without_rewriting_history(scoped_runs):
    client, factory, _ = scoped_runs
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    documents.create({"id": "a-first", "name": "旧流程", "nodes": [], "edges": [], "variables": [], "projectId": "a"}, client_request_id="legacy-document")
    with factory() as session:
        row = session.get(WorkflowRunRow, "a-first")
        row.payload = {key: value for key, value in row.payload.items() if key != "projectId"}
        session.commit()
        original = row.payload.copy()
    assert client.get("/api/workflow-runs/a-first?projectId=a").json()["projectId"] == "a"
    assert client.get("/api/workflow-runs?projectId=a").json()["total"] == 2
    assert client.get("/api/workflow-runs/a-first?projectId=b").status_code == 404
    with factory() as session:
        assert session.get(WorkflowRunRow, "a-first").payload == original


def test_scoped_event_replay_preserves_sequence_without_foreign_payload(scoped_runs):
    _, factory, service = scoped_runs
    events = [
        StudioEvent(1, "execution:started", {"runId": "a-first"}),
        StudioEvent(2, "execution:log", {"runId": "b-middle", "message": "other-project-secret"}),
        StudioEvent(3, "execution:input_prompt", {"runId": "a-last", "prompt": "own-prompt"}),
        StudioEvent(4, "execution:started", {"workflowId": "unknown-legacy"}),
    ]
    scoped = [_scope_run_event(event, "a", service) for event in events]
    assert [item.sequence for item in scoped] == [1, 2, 3, 4]
    assert scoped[0] == events[0]
    assert scoped[2] == events[2]
    assert scoped[1] == StudioEvent(2, "studio:cursor", {})
    assert scoped[3] == StudioEvent(4, "studio:cursor", {})
    assert b"other-project-secret" not in b"".join(_frame(item) for item in scoped)
    assert _scope_run_event(events[1], None, service) == events[1]
    with factory() as session:
        session.get(ProjectRow, "a").lifecycle_state = "deleted"
        session.commit()
    assert _scope_run_event(events[0], "a", service) == StudioEvent(1, "studio:cursor", {})


def test_legacy_workflow_diagnostics_filter_before_read_or_clear(scoped_runs):
    client, _, service = scoped_runs
    before = service.get("a-first").event_count
    assert client.get("/api/workflows/a-first/variable-tracking?projectId=b").json() == {"tracking": [], "count": 0}
    assert client.delete("/api/workflows/a-first/variable-tracking?projectId=b").status_code == 200
    assert service.get("a-first").event_count == before
