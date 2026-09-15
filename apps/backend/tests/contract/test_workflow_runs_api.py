from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.workflows.browser import WorkflowWorkerSession


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


def test_workflow_write_is_blocked_while_service_is_quiesced(
    client: TestClient,
) -> None:
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
        lambda: [InstalledKernel("public", profile["browserVersion"], executable, 6)],
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
    assert workers.payload["requiresBrowser"] is True


def test_network_monitor_family_is_admitted_by_the_real_http_coordinator(
    client: TestClient,
    profile_payload: dict[str, object],
    monkeypatch,
    tmp_path: Path,
) -> None:
    module_types = [
        "network_monitor_start",
        "network_monitor_wait",
        "network_monitor_stop",
    ]
    workflow_payload = {
        **_workflow(),
        "id": "workflow-network-monitor-contract",
        "name": "网络监听合同",
        "clientRequestId": "create-network-monitor-contract",
        "nodes": [
            {
                "id": f"monitor-{index}",
                "type": "moduleNode",
                "position": {"x": index * 240, "y": 0},
                "data": {
                    "moduleType": module_type,
                    "config": {"monitorId": "orders"},
                },
            }
            for index, module_type in enumerate(module_types)
        ],
        "edges": [
            {
                "id": f"monitor-edge-{index}",
                "source": f"monitor-{index}",
                "target": f"monitor-{index + 1}",
            }
            for index in range(len(module_types) - 1)
        ],
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
            return WorkflowWorkerSession(run_id, profile_id, 50, 51)

        async def stop(self, _run_id: str) -> None:
            self.payload = None

        def busy(self) -> bool:
            return self.payload is not None

    workers = Workers()
    monkeypatch.setattr(coordinator, "_resources", Resources())
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
            "runId": "run-network-monitor-contract",
            "documentId": "document-network-monitor-contract",
            "profileId": profile["id"],
        },
    )

    assert response.status_code == 202, response.text
    assert workers.payload is not None
    assert workers.payload["requiresBrowser"] is True
    assert [
        node["data"]["moduleType"] for node in workers.payload["document"]["nodes"]
    ] == module_types


def test_web_browser_families_are_admitted_by_the_real_http_coordinator(
    client: TestClient,
    profile_payload: dict[str, object],
    monkeypatch,
    tmp_path: Path,
) -> None:
    module_types = [
        "use_opened_page",
        "close_page",
        "refresh_page",
        "go_back",
        "go_forward",
        "switch_iframe",
        "switch_to_main",
        "hover_element",
        "handle_dialog",
        "inject_javascript",
        "wait_element",
        "select_dropdown",
        "set_checkbox",
        "drag_element",
        "scroll_page",
        "upload_file",
        "download_file",
        "save_image",
        "get_child_elements",
        "get_sibling_elements",
        "element_exists",
        "element_visible",
        "switch_tab",
        "extract_table_data",
        "network_capture",
    ]
    workflow_payload = {
        **_workflow(),
        "id": "workflow-web-browser-contract",
        "name": "网页动作合同",
        "clientRequestId": "create-web-browser-contract",
        "nodes": [
            {
                "id": f"web-{index}",
                "type": "moduleNode",
                "position": {"x": index * 240, "y": 0},
                "data": {"moduleType": module_type, "config": {}},
            }
            for index, module_type in enumerate(module_types)
        ],
        "edges": [
            {
                "id": f"web-edge-{index}",
                "source": f"web-{index}",
                "target": f"web-{index + 1}",
            }
            for index in range(len(module_types) - 1)
        ],
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
            return WorkflowWorkerSession(run_id, profile_id, 60, 61)

        async def stop(self, _run_id: str) -> None:
            self.payload = None

        def busy(self) -> bool:
            return self.payload is not None

    workers = Workers()
    monkeypatch.setattr(coordinator, "_resources", Resources())
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
            "runId": "run-web-browser-contract",
            "documentId": "document-web-browser-contract",
            "profileId": profile["id"],
        },
    )

    assert response.status_code == 202, response.text
    assert workers.payload is not None
    assert workers.payload["requiresBrowser"] is True
    assert [
        node["data"]["moduleType"] for node in workers.payload["document"]["nodes"]
    ] == module_types


def test_pure_data_family_runs_through_http_without_browser_requirement(
    client: TestClient,
    profile_payload: dict[str, object],
    monkeypatch,
    tmp_path: Path,
) -> None:
    module_types = [
        "list_operation",
        "list_get",
        "list_length",
        "list_export",
        "dict_operation",
        "dict_get",
        "dict_keys",
        "regex_extract",
        "string_replace",
        "string_split",
        "string_join",
        "string_concat",
        "string_trim",
        "string_case",
        "string_substring",
        "list_sum",
        "list_average",
        "list_max",
        "list_min",
        "list_sort",
        "list_unique",
        "list_slice",
        "math_round",
        "math_base_convert",
        "math_floor",
        "math_modulo",
        "math_abs",
        "math_sqrt",
        "math_power",
        "math_log",
        "math_trig",
        "math_exp",
        "math_gcd",
        "math_lcm",
        "math_factorial",
        "math_permutation",
        "math_percentage",
        "math_clamp",
        "math_random_advanced",
        "stat_median",
        "stat_mode",
        "stat_variance",
        "stat_stdev",
        "stat_percentile",
        "stat_normalize",
        "stat_standardize",
        "random_password_generator",
        "url_encode_decode",
        "md5_encrypt",
        "sha_encrypt",
        "timestamp_converter",
        "rgb_to_hsv",
        "rgb_to_cmyk",
        "hex_to_cmyk",
        "uuid_generator",
        "list_reverse",
        "list_find",
        "list_count",
        "list_filter",
        "list_map",
        "list_merge",
        "list_flatten",
        "list_chunk",
        "list_remove_empty",
        "list_intersection",
        "list_union",
        "list_difference",
        "list_cartesian_product",
        "list_shuffle",
        "list_sample",
        "dict_merge",
        "dict_filter",
        "dict_map_values",
        "dict_invert",
        "dict_sort",
        "dict_deep_copy",
        "dict_get_path",
        "dict_flatten",
        "csv_parse",
        "csv_generate",
        "list_to_string_advanced",
        "table_add_row",
        "table_add_column",
        "table_set_cell",
        "table_get_cell",
        "table_delete_row",
        "table_clear",
        "table_export",
    ]
    workflow_payload = {
        **_workflow(),
        "id": "workflow-data-contract",
        "name": "纯数据合同",
        "clientRequestId": "create-data-contract",
        "nodes": [
            {
                "id": f"data-{index}",
                "type": "moduleNode",
                "position": {"x": index * 240, "y": 0},
                "data": {
                    "moduleType": module_type,
                    "config": {},
                },
            }
            for index, module_type in enumerate(module_types)
        ],
        "edges": [
            {
                "id": f"edge-{index}",
                "source": f"data-{index}",
                "target": f"data-{index + 1}",
            }
            for index in range(len(module_types) - 1)
        ],
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
            _executable: Path | None,
            payload: dict[str, Any],
        ) -> WorkflowWorkerSession:
            self.payload = payload
            return WorkflowWorkerSession(run_id, profile_id, 40, None)

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
            "runId": "run-data-contract",
            "documentId": "document-data-contract",
            "profileId": profile["id"],
        },
    )

    assert response.status_code == 202, response.text
    assert workers.payload is not None
    assert workers.payload["requiresBrowser"] is False
    assert [
        node["data"]["moduleType"] for node in workers.payload["document"]["nodes"]
    ] == module_types


def test_control_variable_family_is_admitted_by_the_real_http_coordinator(
    client: TestClient,
    profile_payload: dict[str, object],
    monkeypatch,
    tmp_path: Path,
) -> None:
    module_types = [
        "condition",
        "loop",
        "foreach",
        "infinite_loop",
        "foreach_dict",
        "break_loop",
        "continue_loop",
        "set_variable",
        "increment_decrement",
        "json_parse",
        "base64",
        "random_number",
        "get_time",
        "wait",
        "stop_workflow",
        "assert_checkpoint",
        "group",
        "note",
    ]
    workflow_payload = {
        **_workflow(),
        "id": "workflow-control-contract",
        "name": "控制变量合同",
        "clientRequestId": "create-control-contract",
        "nodes": [
            {
                "id": f"control-{index}",
                "type": "moduleNode",
                "position": {"x": index * 240, "y": 0},
                "data": {"moduleType": module_type, "config": {}},
            }
            for index, module_type in enumerate(module_types)
        ],
        "edges": [],
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
            _executable: Path | None,
            payload: dict[str, Any],
        ) -> WorkflowWorkerSession:
            self.payload = payload
            return WorkflowWorkerSession(run_id, profile_id, 41, None)

        async def stop(self, _run_id: str) -> None:
            self.payload = None

        def busy(self) -> bool:
            return self.payload is not None

    workers = Workers()
    monkeypatch.setattr(coordinator, "_resources", Resources())
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
            "runId": "run-control-contract",
            "documentId": "document-control-contract",
            "profileId": profile["id"],
        },
    )

    assert response.status_code == 202, response.text
    assert workers.payload is not None
    assert workers.payload["requiresBrowser"] is False
    assert [
        node["data"]["moduleType"] for node in workers.payload["document"]["nodes"]
    ] == module_types


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
        lambda: [InstalledKernel("public", profile["browserVersion"], executable, 6)],
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
