"""Opt-in real HTTP/SQLite/CloakBrowser batch chain; no Studio or synthetic Run facts."""

import asyncio
import shutil
from uuid import uuid4

import httpx
import pytest

from autoflow.application.workflows.service import WorkflowService
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.profiles.models import ProfileSpec
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_workflow_real_cloakbrowser import (
    real_cloak_page as cloak_fixture,
)

real_cloak_page = cloak_fixture


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["success", "stop", "budget", "failure"])
async def test_real_project_batch_http(
    tmp_path, valid_profile_values, real_cloak_page, scenario
):
    executable, url, requests = real_cloak_page
    source = next(
        parent for parent in executable.parents if parent.name.startswith("chromium-")
    )
    workspace = tmp_path / "pm3-real-batch-workspace"
    await asyncio.to_thread(
        shutil.copytree,
        source,
        workspace / "data" / "kernels" / source.name,
        symlinks=True,
    )
    settings = Settings(
        data_dir=str(workspace),
        instance_id="pm3-batch-real",
        instance_token="isolated-test-token",
    )
    app = create_app(settings)
    try:
        # Fixture preparation only. Project, automation and batch are created through real HTTP.
        profile = app.state.profile_service.create(
            ProfileSpec.from_values(
                {
                    **valid_profile_values,
                    "headless": True,
                    "browser_version": source.name.removeprefix("chromium-"),
                }
            )
        )
        parameter_id = str(uuid4())
        document = workflow_payload(str(uuid4()))
        nodes = document["content"]["nodes"]
        nodes[0]["data"]["url"] = url
        nodes[1]["data"].update(
            selector="#field", text="{" + parameter_id + "}", clearBefore=False
        )
        nodes[2]["data"]["selector"] = "#button"
        if scenario == "failure":
            nodes[2]["data"].update(selector="#missing-button", timeout=1)
        nodes[3]["data"].update(selector="#button", attribute="data-clicked")
        nodes.append(
            {
                "id": "read-input",
                "type": "get_element_info",
                "position": {"x": 100, "y": 560},
                "data": {
                    "moduleType": "get_element_info",
                    "selector": "#field",
                    "attribute": "value",
                    "variableName": "实际输入",
                },
            }
        )
        document["content"]["edges"].append(
            {"id": "edge-input-read", "source": "read", "target": "read-input"}
        )
        service = WorkflowService(
            SqlAlchemyWorkflowRepository(app.state.session_factory)
        )
        workflow = service.create(document, str(uuid4()))
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"x-autoflow-token": settings.instance_token},
        ) as client:
            created = await client.post(
                "/api/v1/projects",
                headers={"Idempotency-Key": str(uuid4())},
                json={"name": "真实批次验收", "description": ""},
            )
            assert created.status_code == 201, created.text
            project_id = created.json()["projectId"]
            prefix = f"/api/v1/projects/{project_id}"
            response = await client.post(
                prefix + "/automations",
                headers={"Idempotency-Key": str(uuid4())},
                json={
                    "name": "真实浏览器批次",
                    "description": "",
                    "workflowId": workflow.workflow_id,
                    "inputPlan": {"inputs": []},
                    "parameterSchema": [
                        {
                            "parameterId": parameter_id,
                            "name": "追加文本",
                            "type": "string",
                            "required": True,
                        }
                    ],
                    "environmentPolicy": {
                        "source": "newFromProfile",
                        "profileId": profile.id,
                        "proxyOverride": {"mode": "none"},
                        "modelProviderId": None,
                    },
                    "runPolicy": {
                        "maxTasks": 2,
                        "concurrency": 1,
                        "maxLiveInstances": 1,
                        "continueAfterFailure": False,
                        "automaticExecutionTimeoutSeconds": 0.1
                        if scenario == "budget"
                        else 60,
                        "manualDeadlineSeconds": 300,
                    },
                },
            )
            assert response.status_code == 201, response.text
            automation = response.json()
            validation = await client.get(prefix + f"/automations/{automation['automationId']}/validation")
            assert validation.status_code == 200, validation.text
            assert validation.json()["runnable"] is True, validation.json()
            key = str(uuid4())
            payload = {
                "expectedAutomationRevision": automation["managementRevision"],
                "parameters": {parameter_id: "-真实参数"},
                "maxTasks": 2,
                "concurrency": 1,
            }
            response = await client.post(
                prefix + f"/automations/{automation['automationId']}/batches",
                headers={"Idempotency-Key": key},
                json=payload,
            )
            assert response.status_code == 202, response.text
            accepted = response.json()["operation"]
            batch_id = accepted["result"]["batch"]["batchId"]
            found_operation = await client.get(prefix+f"/operations/by-idempotency-key/{key}")
            assert found_operation.status_code == 200, found_operation.text
            assert found_operation.json()["operationId"] == accepted["operationId"]
            for _ in range(300):
                response = await client.get(prefix + f"/batches/{batch_id}")
                assert response.status_code == 200, response.text
                detail = response.json()
                if scenario == "stop" and detail["batch"]["status"] == "running":
                    stopped = await client.post(
                        prefix + f"/batches/{batch_id}/stop",
                        headers={"Idempotency-Key": str(uuid4())},
                        json={
                            "expectedStatusRevision": detail["batch"]["statusRevision"],
                            "reason": "真实浏览器停止验收",
                        },
                    )
                    assert stopped.status_code == 202, stopped.text
                    scenario_stopped = True
                if detail["batch"]["status"] in {
                    "completed",
                    "failed",
                    "stopped",
                    "interrupted",
                }:
                    break
                await asyncio.sleep(0.2)
            else:
                pytest.fail(f"Batch did not complete: {detail}")
            tasks = (
                await client.get(prefix + "/tasks", params={"batchId": batch_id})
            ).json()["items"]
            assert len(tasks) == 2
            for task in tasks:
                viewed = await client.get(prefix + f"/tasks/{task['taskId']}")
                assert viewed.status_code == 200, viewed.text
                assert viewed.json()["inputSnapshot"]["parameters"] == {
                    parameter_id: "-真实参数"
                }
                assert (
                    "frozenConfiguration" not in viewed.json()["run"]["resourceRequest"]
                )
            replay = await client.post(
                prefix + f"/automations/{automation['automationId']}/batches",
                headers={"Idempotency-Key": key},
                json=payload,
            )
            assert replay.status_code == 202 and replay.json()["operation"] == accepted
            if scenario == "success":
                assert detail["statusCounts"]["succeeded"] == 2 and requests, {
                    "batch": detail,
                    "tasks": [(await client.get(prefix + f"/tasks/{task['taskId']}")).json() for task in tasks],
                }
                for task in tasks:
                    task_path = prefix+f"/tasks/{task['taskId']}"
                    logs = await client.get(task_path+"/logs")
                    attempts = await client.get(task_path+"/node-attempts")
                    outputs = await client.get(task_path+"/outputs")
                    assert logs.status_code == attempts.status_code == outputs.status_code == 200
                    assert len(logs.json()["items"]) == 10
                    assert attempts.json()["total"] == 5
                    assert {item["status"] for item in attempts.json()["items"]} == {"succeeded"}
                    assert [item["value"] for item in outputs.json()["items"]] == ["yes", "before-真实参数"]
                    with app.state.session_factory() as session:
                        events = SqlAlchemyWorkflowRuntimeRepository(
                            session
                        ).list_events(task["runId"], after_sequence=0, limit=200)
                    assert [
                        event.payload["value"]
                        for event in events
                        if event.kind == "output"
                    ] == ["yes", "before-真实参数"]
                    assert [event.sequence for event in events] == list(
                        range(1, len(events) + 1)
                    )
            elif scenario == "stop":
                assert scenario_stopped and detail["batch"]["status"] == "stopped"
                assert detail["statusCounts"]["cancelled"] == 2
            elif scenario == "budget":
                assert detail["statusCounts"]["timed_out"] == 1
                assert detail["statusCounts"]["cancelled"] == 1
            else:
                assert detail["statusCounts"]["failed"] == 1
                assert detail["statusCounts"]["cancelled"] == 1
                failed_task = next(task for task in tasks if task["status"] == "failed")
                artifact_path = prefix + f"/tasks/{failed_task['taskId']}/artifacts"
                artifacts = await client.get(artifact_path)
                assert artifacts.status_code == 200, artifacts.text
                assert artifacts.json()["total"] == 1
                artifact = artifacts.json()["items"][0]
                assert artifact["availability"] == "available"
                screenshot = await client.get(artifact_path + f"/{artifact['artifactId']}/content")
                assert screenshot.status_code == 200
                assert screenshot.headers["content-type"] == "image/png"
                assert screenshot.content.startswith(b"\x89PNG\r\n\x1a\n")
            assert not app.state.project_workflow_worker_manager.busy()
            assert app.state.project_workflow_dispatcher.blockers() == []
            assert app.state.project_run_scheduler.blockers() == []
            assert (workspace / "tmp").is_dir()
            assert not list((workspace / "tmp").glob("**/generation-*"))
    finally:
        await app.router.on_shutdown[-1]()
