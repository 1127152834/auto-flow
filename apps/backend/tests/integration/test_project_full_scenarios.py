"""PM9 real browser -> project data chain, with production admission and workers."""

import asyncio
import inspect
import json
import os
import shutil
from pathlib import Path

import httpx
import pytest

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.workflows.service import WorkflowService
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.profiles.models import ProfileSpec
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_project_run_data_start import _input, _table, uid
from tests.integration.test_workflow_real_cloakbrowser import (
    real_cloak_page as cloak_fixture,
)

real_cloak_page = cloak_fixture


@pytest.mark.asyncio
async def test_browser_result_updates_claimed_record_and_status(
    tmp_path,
    valid_profile_values,
    real_cloak_page,
):
    executable, url, requests = real_cloak_page
    source = next(
        parent for parent in executable.parents if parent.name.startswith("chromium-")
    )
    workspace = tmp_path / "pm9-real-workspace"
    await asyncio.to_thread(
        shutil.copytree,
        source,
        workspace / "data" / "kernels" / source.name,
        symlinks=True,
    )
    settings = Settings(
        data_dir=str(workspace), instance_id=uid(), instance_token=uid()
    )
    app = create_app(settings)
    factory = app.state.session_factory
    if frozen_worker := os.environ.get("AUTOFLOW_TEST_PROJECT_WORKER"):
        app.state.project_workflow_worker_manager._command = (
            str(Path(frozen_worker).resolve(strict=True)),
            "--project-workflow-worker",
        )
    try:
        profile = app.state.profile_service.create(
            ProfileSpec.from_values(
                {
                    **valid_profile_values,
                    "headless": True,
                    "browser_version": source.name.removeprefix("chromium-"),
                }
            )
        )
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"x-autoflow-token": settings.instance_token},
        ) as client:
            created = await client.post(
                "/api/v1/projects",
                headers={"Idempotency-Key": uid()},
                json={"name": "PM9 仓库元数据浏览器回写验收", "description": ""},
            )
            assert created.status_code == 201, created.text
            project = created.json()["projectId"]
            prefix = f"/api/v1/projects/{project}"
            # Real repository metadata enters the page through the claimed input.
            package = json.loads(
                (Path(__file__).resolve().parents[4] / "package.json").read_text()
            )
            original = package["name"]
            table, field = _table(factory, project, "仓库包", original)
            field_id = field["ref"]["fieldId"]
            catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
            status = catalog.create_status(
                project,
                table["tableId"],
                uid(),
                {
                    "name": "浏览器已核验",
                    "color": "#8f4b2b",
                    "order": 1,
                    "expectedTableRevision": catalog.fields(project, table["tableId"])[
                        "tableRevision"
                    ],
                },
            )[0]["status"]
            def grant(operation: str, *, read_purposes: list[str] | None = None):
                return {
                    "tableId": table["tableId"],
                    "datasetGeneration": table["datasetGeneration"],
                    "operations": [operation],
                    "fieldIds": [field_id],
                    "readPurposes": read_purposes or [],
                }

            ref = "{snapshot[0]['recordRef']}"

            steps = [
                (
                    "inputs",
                    "project_data",
                    {
                        "operation": "inputs",
                        "arguments": {},
                        "variableName": "snapshot",
                    },
                ),
                (
                    "read",
                    "project_data",
                    {
                        "operation": "readRecord",
                        "bindingProjectId": project,
                        "tableGrant": grant("readRecord", read_purposes=["workflow"]),
                        "variableName": "record",
                        "arguments": {
                            "recordRef": ref,
                            "fieldIds": [field_id],
                            "readPurpose": "workflow",
                        },
                    },
                ),
                ("open", "open_page", {"url": url, "openMode": "current_tab"}),
                (
                    "input",
                    "input_text",
                    {
                        "selector": "#field",
                        "text": "{snapshot[0]['values'][0]['value']}",
                        "clearBefore": False,
                    },
                ),
                ("click", "click_element", {"selector": "#button"}),
                (
                    "result",
                    "get_element_info",
                    {
                        "selector": "#result",
                        "attribute": "text",
                        "variableName": "page_result",
                    },
                ),
                (
                    "write",
                    "project_data",
                    {
                        "operation": "updateRecord",
                        "bindingProjectId": project,
                        "tableGrant": grant("updateRecord"),
                        "variableName": "written",
                        "arguments": {
                            "recordRef": ref,
                            "changes": {field_id: "{page_result}"},
                            "expectedContentRevision": "{record['contentRevision']}",
                        },
                    },
                ),
                (
                    "status",
                    "project_data",
                    {
                        "operation": "setRecordStatus",
                        "bindingProjectId": project,
                        "tableGrant": grant("setRecordStatus"),
                        "variableName": "advanced",
                        "arguments": {
                            "recordRef": ref,
                            "statusId": status["statusId"],
                            "expectedStatusRevision": "{record['statusRevision']}",
                            "expectedContentRevisionWhenDerived": "{written['contentRevision']}",
                            "allowedFrom": [None],
                        },
                    },
                ),
            ]
            document = workflow_payload(uid())
            document["content"].update(
                {
                    "schemaVersion": 3,
                    "nodes": [
                        {
                            "id": name,
                            "type": kind,
                            "position": {"x": index * 160, "y": 0},
                            "data": {"moduleType": kind, "config": config},
                        }
                        for index, (name, kind, config) in enumerate(steps)
                    ],
                    "edges": [
                        {
                            "id": str(index),
                            "source": steps[index][0],
                            "target": steps[index + 1][0],
                        }
                        for index in range(len(steps) - 1)
                    ],
                    "variables": [],
                }
            )
            workflow = WorkflowService(SqlAlchemyWorkflowRepository(factory)).create(
                document, uid()
            )
            response = await client.post(
                prefix + "/automations",
                headers={"Idempotency-Key": uid()},
                json={
                    "name": "领取、浏览器处理、写回与状态推进",
                    "description": "",
                    "workflowId": workflow.workflow_id,
                    "inputPlan": {"inputs": [_input(project, table, field, "仓库包")]},
                    "parameterSchema": [],
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
                        "manualDeadlineSeconds": 300,
                    },
                },
            )
            assert response.status_code == 201, response.text
            automation = response.json()
            response = await client.post(
                prefix + f"/automations/{automation['automationId']}/batches",
                headers={"Idempotency-Key": uid()},
                json={
                    "expectedAutomationRevision": automation["managementRevision"],
                    "parameters": {},
                    "maxTasks": 1,
                    "concurrency": 1,
                },
            )
            assert response.status_code == 202, response.text
            batch_id = response.json()["operation"]["result"]["batch"]["batchId"]
            async with asyncio.timeout(90):
                while True:
                    response = await client.get(prefix + f"/batches/{batch_id}")
                    assert response.status_code == 200, response.text
                    detail = response.json()
                    if detail["batch"]["status"] in {
                        "completed",
                        "failed",
                        "stopped",
                        "interrupted",
                    }:
                        break
                    await asyncio.sleep(0.1)
            tasks = (
                await client.get(prefix + "/tasks", params={"batchId": batch_id})
            ).json()["items"]
            assert len(tasks) == 1
            task_url = prefix + f"/tasks/{tasks[0]['taskId']}"
            attempts = (await client.get(task_url + "/node-attempts")).json()["items"]
            assert detail["statusCounts"]["succeeded"] == 1, (detail, attempts)
            assert len(attempts) == len(steps)
            assert all(item["status"] == "succeeded" for item in attempts)
            persisted = (await client.get(task_url)).json()
            snapshot = persisted["inputSnapshot"]["inputs"][0]
            assert snapshot["values"][0]["value"] == original
            ref_value = snapshot["recordRef"]
            with factory() as session:
                row = session.get(
                    DataRecordRow,
                    (
                        ref_value["datasetGeneration"],
                        ref_value["recordKey"]["type"],
                        ref_value["recordKey"]["value"],
                    ),
                )
                assert row.values_json[field_id] == "before" + original
                assert row.content_revision == snapshot["contentRevision"] + 1
                assert row.status_revision == snapshot["statusRevision"] + 1
                assert row.status_id == status["statusId"]
            assert "/fixture" in requests
            async with asyncio.timeout(40):
                while (await client.get(task_url)).json()["cleanup"]["status"] not in {
                    "succeeded",
                    "notRequired",
                }:
                    await asyncio.sleep(0.1)
            assert not app.state.project_workflow_worker_manager.busy()
            assert app.state.project_workflow_dispatcher.blockers() == []
            assert app.state.project_run_scheduler.blockers() == []
            assert not list((workspace / "tmp").glob("**/generation-*"))
            assert not list(
                (workspace / "workspace" / "environments" / "instances").iterdir()
            )
    finally:
        for callback in app.router.on_shutdown:
            result = callback()
            if inspect.isawaitable(result):
                await result
