from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.workflows.browser import WorkflowWorkerSession
from fastapi.testclient import TestClient


def _workflow() -> dict[str, object]:
    return {
        "id": "workflow-run-contract",
        "name": "运行合同",
        "nodes": [
            {
                "id": "open",
                "type": "open_page",
                "position": {"x": 0, "y": 0},
                "data": {
                    "moduleType": "open_page",
                    "config": {"url": "https://example.test"},
                },
            }
        ],
        "edges": [],
        "variables": [],
        "clientRequestId": "create-run-workflow",
    }


def test_execute_uses_stable_run_identity_and_query_contract(
    client: TestClient, profile_payload: dict[str, object], monkeypatch
) -> None:
    workflow = client.post("/api/workflows", json=_workflow()).json()
    profile = client.post("/api/v1/profiles", json=profile_payload).json()
    accepted = {
        "runId": "run-contract",
        "workflowId": workflow["id"],
        "documentId": "document-contract",
        "workflowName": workflow["name"],
        "status": "starting",
        "startedAt": "2026-09-15T00:00:00+00:00",
        "finishedAt": None,
        "logCount": 0,
    }
    start = AsyncMock(return_value=accepted)
    monkeypatch.setattr(client.app.state.workflow_services.commands, "start", start)

    request = {
        "runId": "run-contract",
        "documentId": "document-contract",
        "profileId": profile["id"],
        "headless": False,
    }
    first = client.post(f"/api/workflows/{workflow['id']}/execute", json=request)
    repeated = client.post(f"/api/workflows/{workflow['id']}/execute", json=request)

    assert first.status_code == repeated.status_code == 202
    assert first.json() == repeated.json() == accepted
    assert start.await_count == 2
    start.assert_awaited_with(workflow["id"], request)


def test_stop_identity_log_paging_and_static_run_route(
    client: TestClient, monkeypatch
) -> None:
    stop = AsyncMock(return_value={"runId": "run-stop", "status": "stopping"})
    monkeypatch.setattr(client.app.state.workflow_services.commands, "stop", stop)

    response = client.post(
        "/api/workflows/workflow-stop/stop", json={"runId": "run-stop"}
    )
    missing = client.get("/api/workflow-runs/missing")

    assert response.status_code == 202
    assert response.json() == {"runId": "run-stop", "status": "stopping"}
    stop.assert_awaited_once_with("workflow-stop", "run-stop")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_workflow_write_is_blocked_while_service_is_quiesced(client: TestClient) -> None:
    client.app.state.settings_runtime.gate.pause(list)
    response = client.post(
        "/api/workflows", json={**_workflow(), "id": "quiesced-workflow"}
    )
    client.app.state.settings_runtime.gate.resume()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SERVICE_QUIESCED"


def test_real_run_coordinator_is_reached_through_http_and_stop_waits_for_cleanup(
    client: TestClient,
    profile_payload: dict[str, object],
    monkeypatch,
    tmp_path: Path,
) -> None:
    workflow = client.post("/api/workflows", json=_workflow()).json()
    profile = client.post("/api/v1/profiles", json=profile_payload).json()
    coordinator = client.app.state.workflow_services.commands
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")

    class Resources:
        owner_id: str | None = None

        async def acquire(self, owner_id: str, _profile_id: str, _kernel: Any) -> None:
            self.owner_id = owner_id

        async def release(self, owner_id: str) -> None:
            assert self.owner_id == owner_id
            self.owner_id = None

    class Workers:
        active = False

        async def start(
            self,
            run_id: str,
            profile_id: str,
            _executable: Path,
            _payload: dict[str, Any],
        ) -> WorkflowWorkerSession:
            self.active = True
            return WorkflowWorkerSession(run_id, profile_id, 10, 11)

        async def stop(self, run_id: str) -> None:
            self.active = False
            await coordinator.on_worker_exit(run_id, 0)

        def busy(self) -> bool:
            return self.active

    monkeypatch.setattr(coordinator, "_resources", Resources())
    monkeypatch.setattr(coordinator, "_workers", Workers())
    monkeypatch.setattr(
        coordinator,
        "_installed_kernels",
        lambda: [
            InstalledKernel("public", profile["browserVersion"], executable, 6)
        ],
    )
    monkeypatch.setattr(coordinator, "_resolve_proxy", _no_proxy)

    request = {
        "runId": "real-http-run",
        "documentId": "document-http",
        "profileId": profile["id"],
        "headless": True,
    }
    started = client.post(f"/api/workflows/{workflow['id']}/execute", json=request)
    repeated = client.post(f"/api/workflows/{workflow['id']}/execute", json=request)
    conflicting = client.post(
        f"/api/workflows/{workflow['id']}/execute",
        json={**request, "headless": False},
    )
    assert started.status_code == repeated.status_code == 202
    assert conflicting.status_code == 409
    assert conflicting.json()["error"]["code"] == "RUN_ID_CONFLICT"
    assert started.json()["status"] == repeated.json()["status"] == "running"
    artifact_root = coordinator._artifact_root
    artifact_file = artifact_root / "runs" / "real-http-run" / "artifacts" / "page.png"
    artifact_file.parent.mkdir(parents=True)
    artifact_file.write_bytes(b"\x89PNG\r\n\x1a\ncontract")
    client.portal.call(
        coordinator.on_worker_event,
        {
            "type": "artifact:registered",
            "runId": "real-http-run",
            "artifactId": "artifact-contract",
            "nodeId": "open",
            "executionId": "execution-contract",
            "relativePath": "runs/real-http-run/artifacts/page.png",
            "size": artifact_file.stat().st_size,
            "sha256": "fixture-hash",
            "mimeType": "image/png",
            "purpose": "result",
        },
    )
    client.portal.call(
        coordinator.on_worker_event,
        {
            "type": "execution:node_complete",
            "runId": "real-http-run",
            "nodeId": "open",
            "executionId": "execution-contract",
            "success": True,
            "message": "已提取结果",
            "data": {"value": "中文结果"},
            "artifactIds": ["artifact-contract"],
        },
    )

    results = client.get("/api/workflow-runs/real-http-run/results")
    artifacts = client.get("/api/workflow-runs/real-http-run/artifacts")
    downloaded = client.get(
        "/api/workflow-runs/real-http-run/artifacts/artifact-contract"
    )

    assert results.status_code == artifacts.status_code == downloaded.status_code == 200
    assert results.json()["items"][0]["values"] == {"value": "中文结果"}
    assert artifacts.json()["items"][0]["artifactId"] == "artifact-contract"
    assert downloaded.content == artifact_file.read_bytes()
    assert downloaded.headers["content-type"] == "image/png"
    stopped = client.post(
        f"/api/workflows/{workflow['id']}/stop", json={"runId": "real-http-run"}
    )
    assert stopped.status_code == 202
    assert stopped.json()["status"] == "stopped"
    assert client.get("/api/workflow-runs/real-http-run").json()["status"] == "stopped"
    assert coordinator._resources.owner_id is None


def test_page_load_family_is_admitted_by_the_real_http_coordinator(
    client: TestClient,
    profile_payload: dict[str, object],
    monkeypatch,
    tmp_path: Path,
) -> None:
    workflow_payload = {
        **_workflow(),
        "id": "workflow-page-load-contract",
        "name": "页面加载合同",
        "clientRequestId": "create-page-load-contract",
        "nodes": [
            {
                "id": "wait",
                "type": "moduleNode",
                "position": {"x": 0, "y": 0},
                "data": {
                    "moduleType": "wait_page_load",
                    "config": {"waitUntil": "load", "timeout": 5},
                },
            },
            {
                "id": "status",
                "type": "moduleNode",
                "position": {"x": 240, "y": 0},
                "data": {
                    "moduleType": "page_load_complete",
                    "config": {
                        "checkState": "domcontentloaded",
                        "saveToVariable": "loaded",
                    },
                },
            },
        ],
        "edges": [{"id": "edge", "source": "wait", "target": "status"}],
    }
    workflow = client.post("/api/workflows", json=workflow_payload).json()
    profile = client.post("/api/v1/profiles", json=profile_payload).json()
    coordinator = client.app.state.workflow_services.commands
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")

    class Resources:
        owner_id: str | None = None

        async def acquire(self, owner_id: str, _profile_id: str, _kernel: Any) -> None:
            self.owner_id = owner_id

        async def release(self, owner_id: str) -> None:
            assert self.owner_id == owner_id
            self.owner_id = None

    class Workers:
        payload: dict[str, Any] | None = None

        async def start(
            self,
            run_id: str,
            profile_id: str,
            _executable: Path,
            payload: dict[str, Any],
        ) -> WorkflowWorkerSession:
            self.payload = payload
            return WorkflowWorkerSession(run_id, profile_id, 30, 31)

        async def stop(self, _run_id: str) -> None:
            self.payload = None

        def busy(self) -> bool:
            return self.payload is not None

    resources = Resources()
    workers = Workers()
    monkeypatch.setattr(coordinator, "_resources", resources)
    monkeypatch.setattr(coordinator, "_workers", workers)
    monkeypatch.setattr(
        coordinator,
        "_installed_kernels",
        lambda: [InstalledKernel("public", profile["browserVersion"], executable, 6)],
    )
    monkeypatch.setattr(coordinator, "_resolve_proxy", _no_proxy)

    response = client.post(
        f"/api/workflows/{workflow['id']}/execute",
        json={
            "runId": "run-page-load-contract",
            "documentId": "document-page-load-contract",
            "profileId": profile["id"],
        },
    )

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "running"
    assert workers.payload is not None
    assert [
        node["data"]["moduleType"] for node in workers.payload["document"]["nodes"]
    ] == ["wait_page_load", "page_load_complete"]


def test_execute_accepts_an_unsaved_document_snapshot_without_creating_a_workflow(
    client: TestClient,
    profile_payload: dict[str, object],
    monkeypatch,
    tmp_path: Path,
) -> None:
    profile = client.post("/api/v1/profiles", json=profile_payload).json()
    coordinator = client.app.state.workflow_services.commands
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")

    class Resources:
        owner_id: str | None = None

        async def acquire(self, owner_id: str, _profile_id: str, _kernel: Any) -> None:
            self.owner_id = owner_id

        async def release(self, owner_id: str) -> None:
            assert self.owner_id == owner_id
            self.owner_id = None

    class Workers:
        payload: dict[str, Any] | None = None

        async def start(
            self,
            run_id: str,
            profile_id: str,
            _executable: Path,
            payload: dict[str, Any],
        ) -> WorkflowWorkerSession:
            self.payload = payload
            return WorkflowWorkerSession(run_id, profile_id, 20, 21)

        async def stop(self, _run_id: str) -> None:
            return None

        def busy(self) -> bool:
            return self.payload is not None

    resources = Resources()
    workers = Workers()
    monkeypatch.setattr(coordinator, "_resources", resources)
    monkeypatch.setattr(coordinator, "_workers", workers)
    monkeypatch.setattr(
        coordinator,
        "_installed_kernels",
        lambda: [
            InstalledKernel("public", profile["browserVersion"], executable, 6)
        ],
    )
    monkeypatch.setattr(coordinator, "_resolve_proxy", _no_proxy)

    document = _workflow()
    document["name"] = "尚未保存的草稿"
    response = client.post(
        "/api/workflows/editor-document/execute",
        json={
            "runId": "unsaved-run",
            "documentId": "editor-document",
            "profileId": profile["id"],
            "document": document,
        },
    )

    assert response.status_code == 202
    assert response.json()["workflowName"] == "尚未保存的草稿"
    assert client.get("/api/workflows/editor-document").status_code == 404
    assert workers.payload is not None
    assert workers.payload["document"]["nodes"][0]["id"] == "open"


async def _no_proxy(_profile: Any, _run_id: str) -> None:
    return None
