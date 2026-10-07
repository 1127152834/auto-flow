"""Remediation M5 5B-A1 (B13): a preview run through real HTTP, scheduler and worker process changes nothing durable."""

import asyncio
import inspect
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy import text

from autoflow.application.workflows.service import WorkflowService
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_project_run_data_start import _input, _table, uid

TERMINAL = {"completed", "failed", "stopped", "interrupted"}
WATCHED = (
    "project_data_records",
    "automation_record_ledger",
    "project_sync_operations",
    "project_sync_record_marks",
    "project_environments",
    "project_environment_saves",
)


def _snapshot(factory) -> dict[str, list]:
    with factory() as session:
        return {
            name: sorted(map(tuple, session.execute(text(f'select * from "{name}"')).all()), key=repr)
            for name in WATCHED
        }


def _counts(factory, *names: str) -> dict[str, int]:
    with factory() as session:
        return {name: session.scalar(text(f'select count(*) from "{name}"')) for name in names}


@asynccontextmanager
async def _world(tmp_path, *, retain: bool = False, fail_at_end: bool = False) -> AsyncIterator:
    settings = Settings(data_dir=str(tmp_path / "workspace"), instance_id=uid(), instance_token=uid())
    app = create_app(settings)
    factory = app.state.session_factory
    # Browser-free seam: this suite proves data isolation, not a browser launch.
    app.state.project_run_coordinator._resolve_resources = lambda *_a, **_k: {"browser": "none", "modelProviderId": None}
    try:
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"x-autoflow-token": settings.instance_token},
        ) as client:
            created = await client.post(
                "/api/v1/projects", headers={"Idempotency-Key": uid()}, json={"name": "试跑验收", "description": ""}
            )
            assert created.status_code == 201, created.text
            project = created.json()["projectId"]
            table, field = _table(factory, project, "账号", "original")
            field_id = field["ref"]["fieldId"]
            source = _input(project, table, field, "账号")
            root = "{PROJECT_INPUTS['" + source["inputId"] + "']"

            def grant(*operations: str) -> dict:
                return {
                    "tableId": table["tableId"],
                    "datasetGeneration": table["datasetGeneration"],
                    "operations": list(operations),
                    "fieldIds": [field_id],
                    "readPurposes": ["workflow"] if "readRecord" in operations else [],
                }

            ref = root + "['recordRef']}"
            steps = [
                ("write", "project_data", {
                    "operation": "updateRecord", "bindingProjectId": project, "tableGrant": grant("updateRecord"),
                    "variableName": "written",
                    "arguments": {"recordRef": ref, "changes": {field_id: "试跑值"}, "expectedContentRevision": root + "['contentRevision']}"},
                }),
                ("read", "project_data", {
                    "operation": "readRecord", "bindingProjectId": project, "tableGrant": grant("readRecord"),
                    "variableName": "after",
                    "arguments": {"recordRef": ref, "fieldIds": [field_id], "readPurpose": "workflow"},
                }),
                ("check", "assert_checkpoint", {
                    "actualValue": "{after['values'][0]['value']}",
                    "expectedValue": "不可能的值" if fail_at_end else "试跑值",
                    "variableName": "checked",
                }),
                ("end", "project_end", {"retainEnvironment": retain, "saveMode": "save_as"}),
            ]
            prefix = f"/api/v1/projects/{project}"
            response = await client.post(prefix + "/automations", headers={"Idempotency-Key": uid()}, json={
                "name": "读写再读", "description": "", "inputPlan": {"inputs": [source]}, "parameterSchema": [],
                "environmentPolicy": {"source": "newFromProfile"},
                "runPolicy": {"maxTasks": 1, "concurrency": 1, "maxLiveInstances": 1, "continueAfterFailure": False,
                              "automaticExecutionTimeoutSeconds": 60, "manualDeadlineSeconds": 300},
            })
            assert response.status_code == 201, response.text
            automation = response.json()
            document = workflow_payload(automation["workflowId"])
            document["content"].update({
                "schemaVersion": 3,
                "nodes": [
                    {"id": name, "type": kind, "position": {"x": index * 160, "y": 0},
                     "data": {"moduleType": kind, "label": name, **config}}
                    for index, (name, kind, config) in enumerate(steps)
                ],
                "edges": [
                    {"id": str(index), "source": steps[index][0], "target": steps[index + 1][0]}
                    for index in range(len(steps) - 1)
                ],
                "variables": [],
            })
            WorkflowService(SqlAlchemyWorkflowRepository(factory)).save(automation["workflowId"], document, 1, uid())
            base = prefix + f"/automations/{automation['automationId']}"

            async def start(mode: str | None):
                debug = await client.post(base + "/debug-inputs", json={"expectedAutomationRevision": automation["managementRevision"]})
                assert debug.status_code == 200, debug.text
                body = {
                    "expectedAutomationRevision": automation["managementRevision"], "parameters": {},
                    "maxTasks": 1, "concurrency": 1, "debugSelection": debug.json()["selection"],
                }
                if mode:
                    body["executionMode"] = mode
                return await client.post(base + "/batches", headers={"Idempotency-Key": uid()}, json=body)

            async def finish(started):
                assert started.status_code == 202, started.text
                batch_id = started.json()["operation"]["result"]["batch"]["batchId"]
                async with asyncio.timeout(90):
                    while (await client.get(prefix + f"/batches/{batch_id}")).json()["batch"]["status"] not in TERMINAL:
                        await asyncio.sleep(0.1)
                task = (await client.get(prefix + "/tasks", params={"batchId": batch_id})).json()["items"][0]
                events = (await client.get(prefix + f"/tasks/{task['taskId']}/events", params={"afterSequence": 0})).json()["items"]
                return task, [str(event["payload"].get("message", "")) for event in events if event["kind"] == "log"]

            yield factory, start, finish
    finally:
        for callback in app.router.on_shutdown:
            result = callback()
            if inspect.isawaitable(result):
                await result


@pytest.mark.asyncio
async def test_preview_reads_its_own_write_and_leaves_real_data_untouched_while_real_writes_change_it(tmp_path):
    async with _world(tmp_path) as (factory, start, finish):
        before = _snapshot(factory)
        task, _logs = await finish(await start(None))
        assert task["status"] == "succeeded", task  # the read-after-write check saw the preview value
        assert _snapshot(factory) == before
        control, _logs = await finish(await start("realWrites"))
        assert control["status"] == "succeeded", control
        after = _snapshot(factory)
        changed = {name for name in WATCHED if after[name] != before[name]}
        assert "project_data_records" in changed
        # The watched tables are live: real writes also leave bookkeeping behind, which the preview must not.
        assert changed & {"automation_record_ledger", "project_sync_operations"}, changed
        with factory() as session:
            values = [json.loads(raw) if isinstance(raw, str) else raw for raw in session.scalars(text("select values_json from project_data_records"))]
        assert [list(item.values()) for item in values] == [["试跑值"]]


@pytest.mark.asyncio
async def test_a_failed_preview_shows_the_original_reason_in_the_run_log(tmp_path):
    async with _world(tmp_path, fail_at_end=True) as (factory, start, finish):
        before = _snapshot(factory)
        task, logs = await finish(await start(None))
        assert task["status"] == "failed"
        assert any("不可能的值" in message for message in logs), logs
        assert _snapshot(factory) == before


@pytest.mark.asyncio
async def test_preview_with_retained_environment_is_refused_before_anything_starts(tmp_path):
    names = ("project_batches", "project_tasks", "workflow_runs", "project_operations")
    async with _world(tmp_path, retain=True) as (factory, start, _finish):
        before = _counts(factory, *names)
        refused = await start(None)
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "PREVIEW_CANNOT_SAVE_ENVIRONMENT", refused.text
        assert _counts(factory, *names) == before
