from __future__ import annotations

import time
from uuid import uuid4

from fastapi.testclient import TestClient


def test_real_worker_preserves_unsaved_project_run_and_archive_blocks_new_start(
    client: TestClient, profile_payload: dict[str, object],
) -> None:
    project = client.post("/api/v1/projects", json={"name": "运行所属项目"}, headers={"Idempotency-Key": str(uuid4())})
    assert project.status_code == 201, project.text
    project_id = project.json()["projectId"]
    profile = client.post("/api/v1/profiles", json=profile_payload)
    assert profile.status_code == 201, profile.text
    request = {
        "runId": "project-run", "documentId": "project-draft", "profileId": profile.json()["id"], "projectId": project_id,
        "document": {"id": "project-draft", "name": "项目未保存草稿", "nodes": [
            {"id": "set", "type": "moduleNode", "data": {"moduleType": "set_variable", "variableName": "message", "variableValue": "真实项目运行"}},
        ], "edges": [], "variables": []},
    }
    started = client.post("/api/workflows/project-draft/execute", json=request)
    assert started.status_code == 202, started.text
    assert started.json()["projectId"] == project_id
    for _ in range(300):
        run = client.get("/api/workflow-runs/project-run").json()
        if run["status"] in {"completed", "failed", "interrupted"}:
            break
        time.sleep(0.02)
    assert run["status"] == "completed", run
    assert run["projectId"] == project_id
    results = client.get("/api/workflow-runs/project-run/results").json()
    assert results["items"][0]["values"] == {"value": "真实项目运行"}
    assert client.get(f"/api/workflows?projectId={project_id}").json() == []
    assert client.get("/api/workflows/project-draft").status_code == 404
    replayed = client.post("/api/workflows/project-draft/execute", json=request)
    assert replayed.status_code == 202, replayed.text
    assert replayed.json()["status"] == "completed"
    assert client.get("/api/workflow-runs?documentId=project-draft").json()["total"] == 1

    impact = client.get(f"/api/v1/projects/{project_id}/lifecycle-impact?action=archive").json()
    archived = client.post(f"/api/v1/projects/{project_id}/archive", json={"impactRevision": impact["impactRevision"], "expectedManagementRevision": 1}, headers={"Idempotency-Key": str(uuid4())})
    assert archived.status_code in {200, 202}, archived.text
    rejected = client.post("/api/workflows/project-draft/execute", json={**request, "runId": "after-archive"})
    assert rejected.status_code in {409, 423}, rejected.text
    assert rejected.json()["error"]["code"] in {"LIFECYCLE_CONFLICT", "PROJECT_CLOSING"}
    assert client.get("/api/workflow-runs/after-archive").status_code == 404
    assert not client.app.state.workflow_services.workers.busy()


def test_project_archive_waits_for_actual_paused_worker_cleanup(client: TestClient, profile_payload: dict[str, object]) -> None:
    project = client.post("/api/v1/projects", json={"name": "调试归档保护"}, headers={"Idempotency-Key": str(uuid4())}).json()
    project_id = project["projectId"]
    profile = client.post("/api/v1/profiles", json=profile_payload).json()
    started = client.post("/api/workflows/paused-project/execute", json={
        "runId": "paused-project-run", "documentId": "paused-project", "profileId": profile["id"], "projectId": project_id, "stepMode": True,
        "document": {"id": "paused-project", "name": "等待清理的调试", "nodes": [{"id": "set", "type": "moduleNode", "data": {"moduleType": "set_variable", "variableName": "value", "variableValue": "never"}}], "edges": [], "variables": []},
    })
    assert started.status_code == 202, started.text
    for _ in range(300):
        run = client.get("/api/workflow-runs/paused-project-run").json()
        if run["status"] == "paused":
            break
        time.sleep(0.02)
    assert run["status"] == "paused", run
    impact = client.get(f"/api/v1/projects/{project_id}/lifecycle-impact?action=archive").json()
    assert any(row["code"] == "STUDIO_RUN_ACTIVE" for row in impact["blockers"])
    archived = client.post(f"/api/v1/projects/{project_id}/archive", json={"impactRevision": impact["impactRevision"], "expectedManagementRevision": 1}, headers={"Idempotency-Key": str(uuid4())})
    assert archived.status_code in {200, 202}, archived.text
    time.sleep(0.3)
    assert client.get(f"/api/v1/projects/{project_id}").json()["lifecycleState"] == "closing"
    assert client.get("/api/workflow-runs/paused-project-run").json()["status"] == "paused"
    stopped = client.post("/api/workflows/paused-project/stop", json={"runId": "paused-project-run"})
    assert stopped.status_code == 202, stopped.text
    for _ in range(300):
        state = client.get(f"/api/v1/projects/{project_id}").json()["lifecycleState"]
        if state == "archived":
            break
        time.sleep(0.02)
    assert state == "archived"
    assert client.get("/api/workflow-runs/paused-project-run").json()["status"] == "stopped"
    assert client.get("/api/workflow-runs/paused-project-run/results").json()["items"] == []
    assert not client.app.state.workflow_services.workers.busy()
