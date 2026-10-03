"""native-batch-v1 (remediation M2 Task 11 / AC2-01, AC2-19): real ledger claiming plus write-back.

One automation processes every row through ordinary batches (claimMode=unprocessed, failure
thresholds, retry budget 3): open the row's item page, read its title and write it back to the row.
1% of rows are permanently gone (HTTP 404) and must be tried exactly 3 times and then isolated;
every other row must be written once. Each sample is a fresh app and database so samples compare
like for like. Run with ``-o faulthandler_timeout=0``: one sample takes longer than the default dump timer.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import shutil
import socket
import time
from uuid import uuid4

import httpx
import pytest
import uvicorn

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.profiles.models import ProfileSpec
from tests.benchmarks.report import build_manifest, write_report
from tests.integration.test_project_input_groups import (
    _add_record,
    _empty_table,
    _input,
)

from .harness import chain, flow_node, input_reference
from .site import GoldenSite

pytestmark = [pytest.mark.golden, pytest.mark.asyncio]

SCENARIO = "native-batch-v1"
ROWS = int(os.environ.get("AUTOFLOW_NATIVE_BATCH_ROWS", "200"))
CONCURRENCY = 2
BATCH_UNITS = 100  # the per-batch unit limit; more rows run as consecutive batches
TERMINAL = {"completed", "failed", "interrupted", "stopped"}


def _values() -> list[str]:
    gone = max(1, ROWS // 100)  # 1% permanently missing rows, spread evenly
    step = ROWS // gone
    return [f"gone-{i:05}" if i % step == step // 2 else f"row-{i:05}" for i in range(ROWS)]


@pytest.mark.parametrize("sample", [1, 2, 3, 4, 5])
async def test_native_batch_processes_every_row_once_and_isolates_gone_rows(
    tmp_path, valid_profile_values, real_cloak_page, sample
):
    executable, _, _ = real_cloak_page
    kernel = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    values = _values()
    manifest = build_manifest(
        SCENARIO,
        {"rows": len(values), "valuesSha256": hashlib.sha256(json.dumps(values).encode()).hexdigest()},
        execution_profile="ledger-batches-writeback-v1",
        browser_kernel=kernel.name,
        concurrency=CONCURRENCY,
        repetitions=5,
        fault_seed="gone-1pct-v1",
    )
    await asyncio.to_thread(shutil.copytree, kernel, tmp_path / "data" / "kernels" / kernel.name, symlinks=True)
    app = create_app(Settings(data_dir=str(tmp_path), instance_id="native", instance_token="native-token"))
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", access_log=False, log_level="warning"))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server_task = None
    try:
        profile = app.state.profile_service.create(ProfileSpec.from_values(
            {**valid_profile_values, "headless": True, "browser_version": kernel.name.removeprefix("chromium-")}))
        await app.state.loop_lag.start()
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        async with asyncio.timeout(10):
            while not server.started:
                await asyncio.sleep(0.01)
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
            headers={"x-autoflow-token": "native-token"}, trust_env=False, timeout=60,
        ) as client:

            async def api(method, path, body=None, status=200):
                response = await client.request(method, path, json=body, headers={"Idempotency-Key": str(uuid4())})
                assert response.status_code == status, f"{method} {path}: {response.status_code} {response.text}"
                return response.json()

            project = await api("POST", "/api/v1/projects", {"name": f"native {sample}", "description": ""}, 201)
            prefix = f"/api/v1/projects/{project['projectId']}"
            factory = app.state.session_factory
            table, key_field = _empty_table(factory, project["projectId"], "Native rows")
            title = (await api("POST", prefix + f"/tables/{table['tableId']}/fields", {
                "definition": {"key": "title", "name": "标题", "type": "string", "required": False, "validation": {}},
                "sourceColumnPolicy": "localOnly", "expectedTableRevision": 2,
            }))["field"]["ref"]["fieldId"]
            refs = {value: _add_record(factory, project["projectId"], table, key_field, value)["ref"] for value in values}
            input_spec = _input(project["projectId"], table, key_field, "rows")
            record_ref = "{PROJECT_INPUTS['" + input_spec["inputId"] + "']['recordRef']}"
            with GoldenSite() as site:
                nodes = [
                    flow_node("open", "open_page", 0, url=f"{site.base_url}/item/{input_reference(input_spec)}", timeout=15,
                              browserEnvironment={"source": "profile", "profileId": profile.id}),
                    flow_node("read", "get_element_info", 1, selector="#title", attribute="text", variableName="title", timeout=2),
                    flow_node("write", "project_data", 2, operation="updateRecord", bindingProjectId=project["projectId"],
                              variableName="written", arguments={"recordRef": record_ref, "changes": {title: "{title}"}},
                              tableGrant={"tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"],
                                          "operations": ["updateRecord"], "fieldIds": [title], "readPurposes": []}),
                ]
                automation = await api("POST", prefix + "/automations", {
                    "name": "Native batch", "description": "", "parameterSchema": [],
                    "inputPlan": {"inputs": [input_spec]},
                    "environmentPolicy": {"source": "newFromProfile", "profileId": profile.id, "proxyOverride": {"mode": "none"}, "modelProviderId": None},
                    "runPolicy": {
                        "maxTasks": BATCH_UNITS, "concurrency": CONCURRENCY, "maxLiveInstances": CONCURRENCY,
                        "continueAfterFailure": False, "automaticExecutionTimeoutSeconds": 60, "manualDeadlineSeconds": 120,
                        "claimMode": "unprocessed", "failurePolicy": "thresholds", "retryBudget": 3, "retryBackoffSeconds": [1, 1],
                    },
                }, 201)
                workflow_path = f"/api/workflows/{automation['workflowId']}"
                workflow = await api("GET", workflow_path)
                await api("PUT", workflow_path, {**workflow, "clientRequestId": str(uuid4()), "expectedRevision": workflow["revision"], "nodes": nodes, "edges": chain(nodes)})
                automation_path = prefix + f"/automations/{automation['automationId']}"
                app.state.loop_lag.reset()
                started = time.perf_counter()
                batches = []
                for _ in range(math.ceil(len(values) / BATCH_UNITS)):
                    accepted = await api("POST", automation_path + "/batches", {
                        "expectedAutomationRevision": automation["managementRevision"], "parameters": {},
                        "maxTasks": BATCH_UNITS, "concurrency": CONCURRENCY, "executionMode": "realWrites",
                    }, 202)
                    batch_path = prefix + f"/batches/{accepted['operation']['result']['batch']['batchId']}"
                    async with asyncio.timeout(3600):
                        while (batch := (await api("GET", batch_path))["batch"])["status"] not in TERMINAL:
                            assert batch["status"] != "paused", batch
                            await asyncio.sleep(0.2)
                    batches.append(batch)
                elapsed = time.perf_counter() - started
                lag = app.state.loop_lag.snapshot().p99_ms
                units, after = [], None
                while True:
                    page = await api("GET", automation_path + "/processing-units?limit=200" + (f"&after={after}" if after else ""))
                    units += page["items"]
                    if not (after := page["nextAfter"]):
                        break
                rows = []
                for page_number in range(1, math.ceil(len(values) / 200) + 1):
                    rows += (await api("GET", prefix + f"/tables/{table['tableId']}/records?datasetGeneration={table['datasetGeneration']}&pageSize=200&page={page_number}"))["items"]
                hits = {value: site.hits(f"/item/{value}") for value in values}
        by_key = {unit["recordRef"]["recordKey"]["value"]: unit for unit in units}
        written = {row["ref"]["recordKey"]["value"]: {cell["fieldId"]: cell["value"] for cell in row["values"]}.get(title) for row in rows}
        gone = [value for value in values if value.startswith("gone-")]
        good = [value for value in values if not value.startswith("gone-")]
        assert set(by_key) == {ref["recordKey"]["value"] for ref in refs.values()}, "every row has exactly one processing record"
        for value in good:
            unit = by_key[refs[value]["recordKey"]["value"]]
            assert (unit["state"], unit["attempts"]) == ("succeeded", 1), unit
            assert written[refs[value]["recordKey"]["value"]] == f"title-{value}"
        for value in gone:
            unit = by_key[refs[value]["recordKey"]["value"]]
            assert (unit["state"], unit["attempts"]) == ("quarantined", 3), unit
            assert hits[value] == 3
        attempts = sum(unit["attempts"] for unit in units)
        path = write_report(f"{SCENARIO}-s{sample}", {
            "rows_succeeded": (float(len(good)), "count"),
            "rows_quarantined": (float(len(gone)), "count"),
            "tasks_attempted": (float(attempts), "count"),
            "batches": (float(len(batches)), "count"),
            "throughput_rows_per_min": (len(good) * 60 / elapsed, "rows_per_min"),
            "attempts_per_min": (attempts * 60 / elapsed, "tasks_per_min"),
            "loop_lag_p99_ms": (lag, "ms"),
        }, manifest={**manifest, "sample": sample})
        assert path.exists()
    finally:
        await app.state.project_run_scheduler.shutdown()
        await app.state.project_workflow_dispatcher.shutdown()
        server.should_exit = True
        if server_task is not None:
            await server_task
        listener.close()
