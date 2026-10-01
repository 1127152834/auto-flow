"""Real-row golden scenario support; never equate attempts with successful rows."""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import math
import os
import shutil
import socket
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import uvicorn

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.profiles.models import ProfileSpec
from tests.benchmarks.report import Unit, build_manifest, write_report
from tests.integration.test_project_input_groups import (
    _add_record,
    _empty_table,
    _input,
)


def _ref_key(ref: dict) -> str:
    # Keep the complete frozen RecordRef including key type and generation.
    return json.dumps(
        {
            key: ref[key]
            for key in ("projectId", "tableId", "datasetGeneration", "recordKey")
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _detail_ref(detail: dict) -> dict:
    inputs = detail["inputSnapshot"]["inputs"]
    if len(inputs) != 1:
        raise ValueError("M0 golden workloads require exactly one input record")
    return inputs[0]["recordRef"]


def assert_complete_coverage(expected_refs: list[dict], details: list[dict]) -> None:
    expected = Counter(_ref_key(ref) for ref in expected_refs)
    actual = Counter(_ref_key(_detail_ref(detail)) for detail in details)
    assert expected and all(count == 1 for count in expected.values()), (
        "Expected unique nonempty inputs"
    )
    assert actual == expected, (
        f"Incomplete or repeated row coverage: expected {expected}, got {actual}"
    )


@dataclass
class GoldenRun:
    details: list[dict[str, Any]]
    elapsed_seconds: float
    expected_refs: list[dict]
    verified_success_refs: list[dict] = field(default_factory=list)
    loop_lag_p99_ms: float = 0.0
    concurrency: int = 2
    manifest: dict | None = None

    def metrics(self) -> dict[str, tuple[float | None, Unit]]:
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds <= 0:
            raise ValueError("A positive elapsed duration is required")
        if any(
            detail["task"]["status"] not in {"succeeded", "failed", "interrupted"}
            for detail in self.details
        ):
            raise ValueError("Unfinished or cancelled runs are not valid baselines")
        refs = {_ref_key(_detail_ref(detail)) for detail in self.details}
        verified = {_ref_key(ref) for ref in self.verified_success_refs}
        successes = {
            _ref_key(_detail_ref(detail))
            for detail in self.details
            if detail["task"]["status"] == "succeeded"
        } & verified
        failures = [
            detail for detail in self.details if detail["task"]["status"] != "succeeded"
        ]
        generic = {
            "工作流节点执行失败",
            "工作流节点执行超时",
            "工作流执行失败",
            "工作流未完整成功，请查看已提交的节点记录",
        }
        explained = 0
        for detail in failures:
            error = (
                detail.get("run", {}).get("error") or detail["task"].get("error") or {}
            )
            message = error.get("message", "").strip()
            explained += bool(message and message not in generic)
        return {
            "tasks_attempted": (len(self.details), "count"),
            "distinct_rows_processed": (len(refs), "count"),
            "rows_succeeded": (len(successes), "count"),
            "tasks_failed": (len(failures), "count"),
            "throughput_rows_per_min": (
                len(successes) * 60 / self.elapsed_seconds,
                "rows_per_min",
            ),
            "attempts_per_min": (
                len(self.details) * 60 / self.elapsed_seconds,
                "tasks_per_min",
            ),
            "failure_reason_ratio": (
                explained / len(failures) if failures else None,
                "ratio",
            ),
            "loop_lag_p99_ms": (self.loop_lag_p99_ms, "ms"),
        }

    def save(
        self,
        name: str,
        *,
        browser_kernel: Path,
        scenario_version: str,
        values: list[str],
    ) -> Path:
        assert_complete_coverage(self.expected_refs, self.details)
        version = next(
            parent.name
            for parent in browser_kernel.parents
            if parent.name.startswith("chromium-")
        )
        if self.manifest is None:
            raise ValueError("Golden report requires pre-execution metadata")
        dataset = {
            "rows": len(values),
            "valuesSha256": hashlib.sha256(json.dumps(values).encode()).hexdigest(),
        }
        if (
            self.manifest["dataset"] != dataset
            or self.manifest["browserKernel"] != version
        ):
            raise ValueError(
                "Golden report dimensions differ from the executed workload"
            )
        path = write_report(
            name,
            self.metrics(),
            manifest={**self.manifest, "scenarioVersion": scenario_version},
        )
        evidence = path.with_suffix(".rows.json")
        evidence.write_text(
            json.dumps(
                {
                    "expectedRefs": self.expected_refs,
                    "verifiedSuccessRefs": self.verified_success_refs,
                    "details": self.details,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        manifest_path = path.with_suffix(".manifest.json")
        metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
        metadata["evidence"] = [evidence.name]
        manifest_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return path


def golden_rows(scenario: str, default: int = 30) -> int:
    rows = int(
        os.environ.get(
            f"AUTOFLOW_GOLDEN_{scenario.upper()}_ROWS",
            os.environ.get("AUTOFLOW_GOLDEN_ROWS", default),
        )
    )
    if rows < 1:
        raise ValueError("Golden row count must be positive")
    return rows


def flow_node(identity: str, kind: str, index: int, **config) -> dict:
    return {
        "id": identity,
        "type": kind,
        "position": {"x": 0, "y": index * 100},
        "data": {"moduleType": kind, "label": identity, **config},
    }


def chain(nodes: list[dict]) -> list[dict]:
    return [
        {"id": f"e-{index}", "source": a["id"], "target": b["id"]}
        for index, (a, b) in enumerate(itertools.pairwise(nodes))
    ]


def input_reference(input_spec: dict) -> str:
    return (
        "{PROJECT_INPUTS['"
        + input_spec["inputId"]
        + "']['values']['"
        + input_spec["fieldBindings"][0]["inputFieldId"]
        + "']}"
    )


async def run_golden(
    tmp_path,
    executable,
    profile_values,
    *,
    values,
    build,
    concurrency=2,
    timeout_seconds=3600,
) -> GoldenRun:
    if not values or len(set(values)) != len(values) or not 1 <= concurrency <= 2:
        raise ValueError(
            "M0 requires unique nonempty values and one or two concurrent batches"
        )
    kernel = next(
        parent for parent in executable.parents if parent.name.startswith("chromium-")
    )
    manifest = build_manifest(
        "golden-v1",
        {
            "rows": len(values),
            "valuesSha256": hashlib.sha256(json.dumps(values).encode()).hexdigest(),
        },
        execution_profile="controlled-one-row-batches-v1",
        browser_kernel=kernel.name,
        concurrency=concurrency,
        fault_seed="name-prefix-v1",
    )
    await asyncio.to_thread(
        shutil.copytree,
        kernel,
        tmp_path / "data" / "kernels" / kernel.name,
        symlinks=True,
    )
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="golden",
            instance_token="golden-local-token",
        )
    )
    server = uvicorn.Server(
        uvicorn.Config(app, lifespan="off", access_log=False, log_level="warning")
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server_task = None
    pending = set()
    terminal = {"completed", "failed", "interrupted", "stopped"}
    try:
        profile = app.state.profile_service.create(
            ProfileSpec.from_values(
                {
                    **profile_values,
                    "headless": True,
                    "browser_version": kernel.name.removeprefix("chromium-"),
                }
            )
        )
        await app.state.loop_lag.start()
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        async with asyncio.timeout(10):
            while not server.started:
                await asyncio.sleep(0.01)
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
            headers={"x-autoflow-token": "golden-local-token"},
            trust_env=False,
            timeout=60,
        ) as client:

            async def api(method, path, body=None, status=200):
                response = await client.request(
                    method, path, json=body, headers={"Idempotency-Key": str(uuid4())}
                )
                assert response.status_code == status, (
                    f"{method} {path}: {response.status_code} {response.text}"
                )
                return response.json()

            project = await api(
                "POST",
                "/api/v1/projects",
                {"name": "Golden rows", "description": ""},
                201,
            )
            prefix = f"/api/v1/projects/{project['projectId']}"
            factory = app.state.session_factory
            table, field = _empty_table(factory, project["projectId"], "Golden inputs")
            expected_refs = [
                _add_record(factory, project["projectId"], table, field, value)["ref"]
                for value in values
            ]
            input_spec = _input(project["projectId"], table, field, "source")
            nodes, edges = build(input_spec)
            for node in nodes:
                if node["data"]["moduleType"] == "open_page":
                    node["data"]["browserEnvironment"] = {
                        "source": "profile",
                        "profileId": profile.id,
                    }
            automation = await api(
                "POST",
                prefix + "/automations",
                {
                    "name": "Golden automation",
                    "description": "",
                    "parameterSchema": [],
                    "inputPlan": {"inputs": [input_spec]},
                    "environmentPolicy": {
                        "source": "newFromProfile",
                        "profileId": profile.id,
                        "proxyOverride": {"mode": "none"},
                        "modelProviderId": None,
                    },
                    "runPolicy": {
                        "maxTasks": 1,
                        "concurrency": 1,
                        "maxLiveInstances": 1,
                        "continueAfterFailure": False,
                        "automaticExecutionTimeoutSeconds": 60,
                        "manualDeadlineSeconds": 120,
                    },
                },
                201,
            )
            workflow_path = f"/api/workflows/{automation['workflowId']}"
            workflow = await api("GET", workflow_path)
            await api(
                "PUT",
                workflow_path,
                {
                    **workflow,
                    "clientRequestId": str(uuid4()),
                    "expectedRevision": workflow["revision"],
                    "nodes": nodes,
                    "edges": edges,
                },
            )
            automation_path = prefix + f"/automations/{automation['automationId']}"
            # Enumerate through the public cursor; do not silently truncate at 100.
            choices, cursor = [], None
            while True:
                page = await api(
                    "POST",
                    automation_path + "/debug-inputs",
                    {
                        "expectedAutomationRevision": automation["managementRevision"],
                        "inputId": input_spec["inputId"],
                        "pageSize": 100,
                        "cursor": cursor,
                    },
                )
                choices.extend(item["selection"] for item in page["items"])
                cursor = page["nextCursor"]
                if cursor is None:
                    break
            assert Counter(
                _ref_key(choice["recordRef"]) for choice in choices
            ) == Counter(_ref_key(ref) for ref in expected_refs)
            semaphore = asyncio.Semaphore(concurrency)

            async def one(choice):
                async with semaphore:
                    accepted = await api(
                        "POST",
                        automation_path + "/batches",
                        {
                            "expectedAutomationRevision": automation[
                                "managementRevision"
                            ],
                            "parameters": {},
                            "maxTasks": 1,
                            "concurrency": 1,
                            "debugSelection": {input_spec["inputId"]: choice},
                        },
                        202,
                    )
                    batch_id = accepted["operation"]["result"]["batch"]["batchId"]
                    batch_path = prefix + f"/batches/{batch_id}"
                    pending.add(batch_path)
                    while True:
                        batch = (await api("GET", batch_path))["batch"]
                        if batch["status"] in terminal:
                            break
                        await asyncio.sleep(0.05)
                    tasks = (await api("GET", prefix + f"/tasks?batchId={batch_id}"))[
                        "items"
                    ]
                    assert len(tasks) == 1 and batch["activeTaskCount"] == 0, batch
                    detail_path = prefix + f"/tasks/{tasks[0]['taskId']}"
                    detail = await api("GET", detail_path)
                    assert _ref_key(_detail_ref(detail)) == _ref_key(
                        choice["recordRef"]
                    )
                    detail["outputs"] = (await api("GET", detail_path + "/outputs"))[
                        "items"
                    ]
                    pending.remove(batch_path)
                    return detail

            app.state.loop_lag.reset()
            started = time.perf_counter()
            try:
                async with (
                    asyncio.timeout(timeout_seconds),
                    asyncio.TaskGroup() as group,
                ):
                    tasks = [group.create_task(one(choice)) for choice in choices]
                result = GoldenRun(
                    details=[task.result() for task in tasks],
                    elapsed_seconds=time.perf_counter() - started,
                    expected_refs=expected_refs,
                    loop_lag_p99_ms=app.state.loop_lag.snapshot().p99_ms,
                    concurrency=concurrency,
                    manifest=manifest,
                )
                assert_complete_coverage(expected_refs, result.details)
                return result
            finally:
                # Stop only batches owned by this invocation and wait for terminal cleanup.
                for batch_path in pending:
                    batch = (await api("GET", batch_path))["batch"]
                    if batch["status"] not in terminal:
                        await api(
                            "POST",
                            batch_path + "/stop",
                            {
                                "expectedStatusRevision": batch["statusRevision"],
                                "reason": "golden harness cleanup",
                            },
                            202,
                        )
                async with asyncio.timeout(90):
                    while pending:
                        for batch_path in list(pending):
                            if (await api("GET", batch_path))["batch"][
                                "status"
                            ] in terminal:
                                pending.remove(batch_path)
                        if pending:
                            await asyncio.sleep(0.1)
    finally:
        try:
            if server_task is not None:
                server.should_exit = True
                await asyncio.wait_for(server_task, 10)
        finally:
            listener.close()
            await app.router.on_shutdown[-1]()
