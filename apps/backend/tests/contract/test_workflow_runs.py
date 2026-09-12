import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient

from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifacts
from tests.fixtures.workflow_runs import workflow_runtime
from tests.fixtures.workflows import workflow_payload

ROOT = "/api/v1/workflows/runs"
HEADERS = {"x-autoflow-token": "renderer"}
HOST = {"x-autoflow-host-token": "host"}


def test_run_routes_contract_auth_list_stop_and_reconnect(tmp_path):
    app, profile, worker = workflow_runtime(tmp_path)
    payload = {"runId": str(uuid4()), **workflow_payload(), "profileId": profile.id}
    with TestClient(app, headers=HEADERS) as client:
        assert client.post(ROOT, json=payload, headers={"x-autoflow-token": "bad"}).status_code == 401
        response = client.post(ROOT, json=payload)
        assert response.status_code == 201, response.text
        run_id = response.json()["runId"]
        client.portal.call(worker.started.wait)
        assert client.get("/api/v1/workflows").json() == {"items": []}
        assert client.post(ROOT, json=payload).json()["runId"] == run_id
        assert worker.executions == 1
        assert client.post(ROOT, json={**payload, "profileId": str(uuid4())}).status_code == 409
        assert client.post(ROOT, json={**payload, "runId": str(uuid4())}).status_code == 409
        page = client.get(ROOT, params={"workflowId": payload["document"]["id"], "limit": 1}).json()
        assert page["activeRunId"] == run_id and page["nextOffset"] is None
        assert len(page["items"]) == 1
        assert "document" not in page["items"][0] and "nodeOrder" not in page["items"][0]
        events = client.get(f"{ROOT}/{run_id}/events", params={"limit": 1}).json()
        assert events["hasMore"] and events["nextSeq"] == 1
        assert events["items"][0]["type"] == "accepted"
        assert client.get(f"{ROOT}/{run_id}/events?afterSeq=-1").status_code == 422
        assert client.get(f"{ROOT}/{run_id}/events?limit=1001").status_code == 422
        paused = client.post("/internal/settings/quiesce", headers=HOST)
        assert paused.status_code == 409
        assert "workflow_run_active" in paused.json()["error"]["details"]["blockers"]
        assert client.delete(f"/api/v1/profiles/{profile.id}").status_code == 409
        stopped = client.post(f"{ROOT}/{run_id}/stop")
        assert stopped.status_code == 200
        assert stopped.json()["state"] == "cancelled" and worker.cleaned.is_set()
        assert client.post(f"{ROOT}/{run_id}/stop").json() == stopped.json()
        stream = client.get(f"{ROOT}/{run_id}/stream?afterSeq=1")
        assert stream.status_code == 200 and "event: run_event" in stream.text
        assert "id: 1\n" not in stream.text and '"state":' not in stream.text
        assert client.get(f"{ROOT}/{run_id}/stream", headers={"x-autoflow-token": "bad"}).status_code == 401
        schema = client.get("/openapi.json").json()
        assert {"RunRead", "RunSummary", "RunEvent", "RunArtifact", "RunStart", "RunEvents", "RunList"} <= schema["components"]["schemas"].keys()
        assert client.post("/internal/settings/quiesce", headers=HOST).status_code == 200
        blocked = client.post(ROOT, json={**payload, "runId": str(uuid4())})
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "SERVICE_QUIESCED"


def test_validation_errors_point_to_nodes_and_missing_profile(tmp_path):
    app, profile, _worker = workflow_runtime(tmp_path)
    payload = {"runId": str(uuid4()), **workflow_payload(), "profileId": profile.id}
    with TestClient(app, headers=HEADERS) as client:
        invalid = {**payload, "profileId": str(uuid4())}
        missing = client.post(ROOT, json=invalid)
        assert missing.status_code == 422
        assert missing.json()["error"]["details"]["issues"][0]["path"] == ["profileId"]
        payload["document"]["nodes"][0]["config"]["url"] = ""
        response = client.post(ROOT, json=payload)
        assert response.status_code == 422
        issue = response.json()["error"]["details"]["issues"][0]
        assert issue["nodeId"] == "n0" and issue["path"] == ["config", "url"]
        assert client.get(ROOT).json()["items"] == []
        assert client.get(f"{ROOT}/{uuid4()}").status_code == 404


def test_http_artifact_reads_only_registered_files_and_never_custom_targets(tmp_path):
    app, profile, worker = workflow_runtime(tmp_path)
    run_id = str(uuid4())
    payload = {"runId": run_id, **workflow_payload(), "profileId": profile.id}
    with TestClient(app, headers=HEADERS) as client:
        assert client.post(ROOT, json=payload).status_code == 201
        client.portal.call(worker.started.wait)
        files = WorkflowArtifacts(app.state.paths.workspace / "runs", run_id)
        artifact = files.save_json("n4", {"result": "x" * 70000})
        worker.artifact = artifact
        client.portal.call(worker.complete.set)
        client.portal.call(worker.cleaned.wait)
        endpoint = f"{ROOT}/{run_id}/artifacts/{artifact['id']}"
        response = client.get(endpoint)
        assert response.status_code == 200 and len(response.json()["result"]) == 70000
        assert response.headers["content-type"] == "application/json"
        assert client.get(endpoint, headers={"x-autoflow-token": "bad"}).status_code == 401
        assert client.get(f"{ROOT}/{run_id}/artifacts/{artifact['relativePath']}").status_code == 404
        path = files.root / artifact["relativePath"]
        path.unlink()
        path.symlink_to(tmp_path / "test-kernel")
        assert client.get(endpoint).status_code == 404


def test_public_start_admission_is_visible_to_quiesce_before_it_persists(tmp_path):
    app, profile, _worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    original = service.start
    entered, release = Event(), Event()

    async def held_start(*args, **kwargs):
        entered.set()
        await asyncio.to_thread(release.wait, 3)
        return await original(*args, **kwargs)

    service.start = held_start
    payload = {"runId": str(uuid4()), **workflow_payload(), "profileId": profile.id}
    with TestClient(app, headers=HEADERS) as client, ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, ROOT, json=payload)
        assert entered.wait(1)
        paused = client.post("/internal/settings/quiesce", headers=HOST)
        assert paused.status_code == 409
        assert "api_mutation_in_progress" in paused.json()["error"]["details"]["blockers"]
        release.set()
        assert pending.result(3).status_code == 201
        assert client.post(f"{ROOT}/{payload['runId']}/stop").json()["state"] == "cancelled"


def test_failed_cleanup_is_visible_and_second_http_stop_retries(tmp_path, monkeypatch):
    from autoflow.domain.workflows.models import WorkflowError

    app, profile, worker = workflow_runtime(tmp_path)
    run_id = str(uuid4())
    original = worker.stop
    attempts = 0

    async def fail_first_cleanup(run_id):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise WorkflowError("WORKFLOW_CLEANUP_FAILED", "浏览器清理尚未完成，请重试停止", 503)
        await original(run_id)

    monkeypatch.setattr(worker, "stop", fail_first_cleanup)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post(ROOT, json={"runId": run_id, **workflow_payload(), "profileId": profile.id})
        assert response.status_code == 201
        client.portal.call(worker.started.wait)
        first = client.post(f"{ROOT}/{run_id}/stop")
        assert first.status_code == 503
        assert first.json()["error"]["code"] == "WORKFLOW_CLEANUP_FAILED"
        current = client.get(f"{ROOT}/{run_id}").json()
        assert current["state"] == "stopping" and current["finishedAt"] is None
        assert current["error"]["code"] == "WORKFLOW_CLEANUP_FAILED"
        assert worker.busy() and not worker.cleaned.is_set()
        assert client.delete(f"/api/v1/profiles/{profile.id}").status_code == 409
        assert client.get(ROOT).json()["activeRunId"] == run_id
        second = client.post(f"{ROOT}/{run_id}/stop")
        assert second.status_code == 200 and second.json()["state"] == "cancelled"
        assert attempts == 2 and worker.cleaned.is_set()
        assert second.json()["error"] is None
        assert client.get(ROOT).json()["activeRunId"] is None
        assert client.post(f"{ROOT}/{run_id}/stop").json() == second.json()
