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
    other = client.post("/api/v1/projects", json={"name": "其他项目"}, headers={"Idempotency-Key": str(uuid4())}).json()["projectId"]
    pause = next(event.payload for event in client.app.state.workflow_services.runs.events("paused-project-run") if event.type == "execution:paused")
    control = {"runId": "paused-project-run", "pauseId": pause["pauseId"], "controlRevision": pause["controlRevision"], "commandId": "scoped-command"}
    for action, body in (
        ("stop", {"runId": "paused-project-run"}),
        ("debug/resume", control), ("debug/step", control),
        ("debug/variables", {**control, "changes": [{"name": "value", "value": "foreign"}]}),
        ("debug/breakpoints", {"breakpoints": []}),
    ):
        rejected = client.post(f"/api/workflows/paused-project/{action}?projectId={other}", json=body)
        assert rejected.status_code == 404, (action, rejected.text)
        assert client.get("/api/workflow-runs/paused-project-run").json()["status"] == "paused"
    applied = client.post(f"/api/workflows/paused-project/debug/variables?projectId={project_id}", json={**control, "changes": [{"name": "value", "value": "own"}]})
    assert applied.status_code == 200, applied.text
    assert client.get(f"/api/events/commands/scoped-command?projectId={project_id}").status_code == 200
    assert client.get(f"/api/events/commands/scoped-command?projectId={other}").status_code == 404
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


def test_project_input_roundtrip_rejects_foreign_answer_and_receipt(client: TestClient, profile_payload: dict[str, object]) -> None:
    projects = [client.post('/api/v1/projects', json={'name': name}, headers={'Idempotency-Key': str(uuid4())}).json()['projectId'] for name in ('输入所属项目', '其他输入项目')]
    own, other = projects
    profile = client.post('/api/v1/profiles', json=profile_payload).json()
    started = client.post(f'/api/workflows/project-input/execute?projectId={own}', json={
        'runId': 'project-input-run', 'documentId': 'project-input', 'profileId': profile['id'],
        'document': {'id': 'project-input', 'name': '真实输入回传', 'nodes': [{'id': 'prompt', 'type': 'moduleNode', 'data': {'moduleType': 'input_prompt', 'config': {'variableName': 'answer', 'inputMode': 'integer', 'promptTitle': '输入'}}}], 'edges': [], 'variables': [{'name': 'answer', 'value': 0}]},
    })
    assert started.status_code == 202, started.text
    assert started.json()['projectId'] == own
    for _ in range(300):
        events = client.app.state.workflow_services.runs.events('project-input-run')
        prompts = [event.payload for event in events if event.type == 'execution:input_prompt']
        if prompts:
            break
        time.sleep(0.02)
    assert prompts
    request_id = prompts[0]['requestId']
    path = f'/api/events/input-prompts/{request_id}'
    assert client.get(f'{path}?projectId={other}').status_code == 404
    assert client.get(f'{path}?projectId={own}').json()['status'] == 'pending'
    command = {'commandId': 'project-input-command', 'event': 'input_prompt_result', 'data': {'requestId': request_id, 'value': '42'}}
    rejected = client.post(f'/api/events/commands?projectId={other}', json=command)
    assert rejected.status_code == 404, rejected.text
    assert client.get(f'{path}?projectId={own}').json()['status'] == 'pending'
    applied = client.post(f'/api/events/commands?projectId={own}', json=command)
    assert applied.status_code == 200, applied.text
    assert applied.json()['success'] is True
    assert client.get(f'/api/events/commands/project-input-command?projectId={other}').status_code == 404
    assert client.get(f'/api/events/commands/project-input-command?projectId={own}').json()['success'] is True
    assert client.post(f'/api/events/commands?projectId={own}', json=command).json() == applied.json()
    for _ in range(300):
        run = client.get('/api/workflow-runs/project-input-run').json()
        if run['status'] in {'completed', 'failed', 'interrupted'}:
            break
        time.sleep(0.02)
    assert run['status'] == 'completed', run
    assert client.get('/api/workflow-runs/project-input-run/results').json()['items'][0]['values'] == {'value': 42}
    assert not client.app.state.workflow_services.workers.busy()
