"""Opt-in real HTTP/SQLite/CloakBrowser batch chain; no Studio or synthetic Run facts."""

import asyncio
import hashlib
import inspect
import io
import shutil
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from openpyxl import load_workbook

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
@pytest.mark.parametrize("scenario", ["success", "stop", "budget", "failure", "web_basic", "page_load", "advanced_browser", "tab_switch", "table_extract", "control_primitives", "network_capture", "firecrawl", "firecrawl_failure", "firecrawl_stop", "element_change", "element_timeout", "element_stop"])
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
        if scenario == "web_basic":
            fixture_dir = Path(__file__).parents[1] / "fixtures"
            first_page = (fixture_dir / "workflow-page.html").resolve().as_uri()
            second_page = (fixture_dir / "workflow-b2-web-actions.html").resolve().as_uri()
            steps = [
                ("open_page", {"url": first_page, "openMode": "current_tab"}),
                ("use_opened_page", {"pageIdentifier": "AutoFlow B1 受控页面", "matchMode": "title"}),
                ("wait_element", {"selector": "#workflow-input", "waitCondition": "visible"}),
                ("hover_element", {"selector": "#workflow-submit", "hoverDuration": 0}),
                ("inject_javascript", {"javascriptCode": "setTimeout(() => alert('AutoFlow dialog'), 100); return document.title", "injectMode": "current", "saveResult": "injected_title"}),
                ("handle_dialog", {"dialogAction": "accept", "saveMessage": "dialog_message"}),
                ("refresh_page", {"waitUntil": "load"}),
                ("open_page", {"url": second_page, "openMode": "current_tab"}),
                ("go_back", {"waitUntil": "load"}),
                ("go_forward", {"waitUntil": "load"}),
                ("go_back", {"waitUntil": "load"}),
                ("switch_iframe", {"locateBy": "selector", "iframeSelector": "#workflow-frame"}),
                ("wait_element", {"selector": "#frame-value", "waitCondition": "visible"}),
                ("switch_to_main", {}),
                ("close_page", {}),
            ]
            document["content"]["nodes"] = [
                {"id": f"web-{index}", "type": module_type, "position": {"x": index * 100, "y": 0}, "data": {"moduleType": module_type, "config": config}}
                for index, (module_type, config) in enumerate(steps)
            ]
            document["content"]["edges"] = [
                {"id": f"web-edge-{index}", "source": f"web-{index}", "target": f"web-{index + 1}"}
                for index in range(len(steps) - 1)
            ]
            document["content"]["variables"] = []
        elif scenario == "page_load":
            steps = [
                ("open_page", {"url": url, "openMode": "current_tab"}),
                ("wait_page_load", {"waitUntil": "load", "timeout": 5}),
                ("page_load_complete", {"checkState": "domcontentloaded", "saveToVariable": "page_ready"}),
            ]
            document["content"]["nodes"] = [
                {"id": f"load-{index}", "type": module_type, "position": {"x": index * 100, "y": 0}, "data": {"moduleType": module_type, "config": config}}
                for index, (module_type, config) in enumerate(steps)
            ]
            document["content"]["edges"] = [
                {"id": f"load-edge-{index}", "source": f"load-{index}", "target": f"load-{index + 1}"}
                for index in range(len(steps) - 1)
            ]
            document["content"]["variables"] = []
        elif scenario == "tab_switch":
            fixture_dir = Path(__file__).parents[1] / "fixtures"
            first_page = (fixture_dir / "workflow-page.html").resolve().as_uri()
            second_page = (fixture_dir / "workflow-b2-web-actions.html").resolve().as_uri()
            steps = [
                ("open_page", {"url": first_page, "openMode": "current_tab"}),
                ("open_page", {"url": second_page, "openMode": "new_tab"}),
                ("switch_tab", {"switchMode": "title", "tabTitle": "AutoFlow B1 受控页面", "matchMode": "exact", "saveIndexVariable": "first_index", "saveTitleVariable": "first_title", "saveUrlVariable": "first_url"}),
                ("get_element_info", {"selector": "#workflow-submit", "attribute": "text", "variableName": "first_button"}),
                ("switch_tab", {"switchMode": "last", "saveIndexVariable": "last_index", "saveTitleVariable": "last_title", "saveUrlVariable": "last_url"}),
                ("get_element_info", {"selector": "#child-a", "attribute": "text", "variableName": "last_child"}),
            ]
            document["content"]["nodes"] = [
                {"id": f"tab-{index}", "type": module_type, "position": {"x": index * 100, "y": 0}, "data": {"moduleType": module_type, "config": config}}
                for index, (module_type, config) in enumerate(steps)
            ]
            document["content"]["edges"] = [
                {"id": f"tab-edge-{index}", "source": f"tab-{index}", "target": f"tab-{index + 1}"}
                for index in range(len(steps) - 1)
            ]
            document["content"]["variables"] = []
        elif scenario == "table_extract":
            fixture = (Path(__file__).parents[1] / "fixtures" / "workflow-b2-remaining-browser.html").resolve().as_uri()
            steps = [
                ("open_page", {"url": fixture, "openMode": "current_tab"}),
                ("extract_table_data", {"tableSelector": "#orders-table", "variableName": "orders", "exportToExcel": True, "excelPath": "reports/orders.xlsx"}),
            ]
            document["content"]["nodes"] = [
                {"id": f"table-{index}", "type": module_type, "position": {"x": index * 100, "y": 0}, "data": {"moduleType": module_type, "config": config}}
                for index, (module_type, config) in enumerate(steps)
            ]
            document["content"]["edges"] = [
                {"id": "table-edge", "source": "table-0", "target": "table-1"}
            ]
            document["content"]["variables"] = []
        elif scenario == "control_primitives":
            fixture = (Path(__file__).parents[1] / "fixtures" / "workflow-page.html").resolve().as_uri()
            steps = [
                ("open_page", {"url": fixture, "openMode": "current_tab"}),
                ("wait", {"waitType": "selector", "selector": "#workflow-submit"}),
                ("assert_checkpoint", {"checkType": "element", "selector": "#workflow-submit", "elementCheck": "visible", "variableName": "checked"}),
                ("stop_workflow", {"stopReason": "业务结束"}),
                ("get_element_info", {"selector": "#workflow-submit", "attribute": "text", "variableName": "must_not_run"}),
            ]
            document["content"]["nodes"] = [
                {"id": f"control-{index}", "type": module_type, "position": {"x": index * 100, "y": 0}, "data": {"moduleType": module_type, "config": config}}
                for index, (module_type, config) in enumerate(steps)
            ]
            document["content"]["edges"] = [
                {"id": f"control-edge-{index}", "source": f"control-{index}", "target": f"control-{index + 1}"}
                for index in range(len(steps) - 1)
            ]
            document["content"]["variables"] = []
        elif scenario.startswith("element_"):
            fixture = tmp_path / "project-elements.html"
            fixture.write_text('<!doctype html><style>div{min-height:30px}</style><div id="list"></div><div id="flag"></div><div id="text">旧内容</div>', encoding="utf-8")
            steps = [("open_page", {"url": fixture.as_uri(), "openMode": "current_tab"})]
            for kind, selector, change in [
                ("childList", "#list", "const p=document.createElement('p'); p.id='added'; p.textContent='新增内容'; document.querySelector('#list').appendChild(p)"),
                ("attributes", "#flag", "document.querySelector('#flag').setAttribute('data-count', String(++window.count))"),
                ("characterData", "#text", "document.querySelector('#text').firstChild.data='新内容'+(++window.count)"),
            ]:
                steps.extend([
                    ("inject_javascript", {"javascriptCode": "clearInterval(window.timer); window.count=0; window.timer=setInterval(()=>{"+change+"},300); return true", "injectMode": "current"}),
                    ("element_change_trigger", {"selector": selector, "observeType": kind, "timeout": 5,
                     "saveNewElementSelector": kind+"_selector", "saveChangeInfo": kind+"_info"}),
                ])
            if scenario != "element_change":
                steps = [steps[0], ("element_change_trigger", {"selector": "#list", "timeout": 1 if scenario == "element_timeout" else 0})]
            document["content"]["nodes"] = [
                {"id": f"mutation-{index}", "type": module_type, "position": {"x": index*100, "y": 0}, "data": {"moduleType": module_type, "config": config}}
                for index, (module_type, config) in enumerate(steps)
            ]
            document["content"]["edges"] = [
                {"id": f"mutation-edge-{index}", "source": f"mutation-{index}", "target": f"mutation-{index+1}"}
                for index in range(len(steps)-1)
            ]
            document["content"]["variables"] = []
        elif scenario.startswith("firecrawl"):
            crawl_url = url.replace("/fixture", "/crawl/start")
            steps = [
                ("firecrawl_scrape", {"url": crawl_url, "variableName": "scraped", "formats": ["markdown", "html", "screenshot"], "onlyMainContent": True}),
                ("firecrawl_map", {"url": crawl_url, "variableName": "links", "search": "/crawl/", "ignoreSitemap": False, "limit": 10}),
                ("firecrawl_crawl", {"url": crawl_url, "variableName": "pages", "maxDepth": 1, "limit": 2, "formats": ["text"], "onlyMainContent": True, "ignoreSitemap": True}),
            ]
            if scenario == "firecrawl_failure":
                steps[0][1]["url"] = crawl_url.replace('/start', '/unavailable')
            elif scenario == "firecrawl_stop":
                steps[0][1].update(waitFor="#never-present", timeout=60000)
            document["content"]["nodes"] = [
                {"id": f"crawl-{index}", "type": module_type, "position": {"x": index * 100, "y": 0}, "data": {"moduleType": module_type, "config": config}}
                for index, (module_type, config) in enumerate(steps)
            ]
            document["content"]["edges"] = [
                {"id": f"crawl-edge-{index}", "source": f"crawl-{index}", "target": f"crawl-{index + 1}"}
                for index in range(len(steps) - 1)
            ]
            document["content"]["variables"] = []
        elif scenario == "network_capture":
            network_url = url.replace("/fixture", "/network-monitor")
            steps = [
                ("open_page", {"url": network_url, "openMode": "current_tab"}),
                ("network_monitor_start", {"monitorId": "orders", "filterType": "api", "urlPattern": "/api/"}),
                ("click_element", {"selector": "#request-orders"}),
                ("network_monitor_wait", {"monitorId": "orders", "urlPattern": "/api/orders", "timeout": 5, "captureMode": "first", "variableName": "first_request"}),
                ("network_monitor_stop", {"monitorId": "orders", "variableName": "all_requests"}),
                ("network_capture", {"captureMode": "browser", "captureDuration": 4, "searchKeyword": "/api/orders", "variableName": "captured_urls"}),
            ]
            document["content"]["nodes"] = [
                {"id": f"network-{index}", "type": module_type, "position": {"x": index * 100, "y": 0}, "data": {"moduleType": module_type, "config": config}}
                for index, (module_type, config) in enumerate(steps)
            ]
            document["content"]["edges"] = [
                {"id": f"network-edge-{index}", "source": f"network-{index}", "target": f"network-{index + 1}"}
                for index in range(len(steps) - 1)
            ]
            document["content"]["variables"] = []
        elif scenario == "advanced_browser":
            upload = tmp_path / "project-upload.txt"
            upload.write_text("AutoFlow 上传", encoding="utf-8")
            fixture = (Path(__file__).parents[1] / "fixtures" / "workflow-b2-web-actions.html").resolve().as_uri()
            steps = [
                ("open_page", {"url": fixture, "openMode": "current_tab"}),
                ("select_dropdown", {"selector": "#choice", "selectBy": "value", "value": "second"}),
                ("set_checkbox", {"selector": "#enabled", "checked": True}),
                ("drag_element", {"sourceSelector": "#drag-source", "targetSelector": "#drag-target"}),
                ("scroll_page", {"direction": "down", "distance": 300, "scrollMode": "wheel"}),
                ("upload_file", {"selector": "#upload", "filePath": str(upload)}),
                ("download_file", {"downloadMode": "click", "triggerSelector": "#download-link", "variableName": "downloaded_file"}),
                ("save_image", {"selector": "#fixture-image", "savePath": "fixture-image.png", "variableName": "saved_image"}),
                ("get_child_elements", {"parentSelector": "#children", "variableName": "children"}),
                ("get_sibling_elements", {"elementSelector": "#sibling-target", "siblingType": "all", "variableName": "siblings"}),
                ("element_exists", {"selector": "#bottom-marker"}),
                ("element_visible", {"selector": "#enabled"}),
                ("page_load_complete", {"checkState": "domcontentloaded", "saveToVariable": "page_ready"}),
            ]
            document["content"]["nodes"] = [
                {"id": f"advanced-{index}", "type": module_type, "position": {"x": index * 100, "y": 0}, "data": {"moduleType": module_type, "config": config}}
                for index, (module_type, config) in enumerate(steps)
            ]
            document["content"]["edges"] = [
                {"id": f"advanced-edge-{index}", "source": f"advanced-{index}", "target": f"advanced-{index + 1}"}
                for index in range(len(steps) - 1)
            ]
            for index in (10, 11):
                document["content"]["edges"][index]["sourceHandle"] = "true"
                document["content"]["edges"].append({
                    "id": f"advanced-false-{index}", "source": f"advanced-{index}",
                    "sourceHandle": "false", "target": f"advanced-{index + 1}",
                })
            document["content"]["variables"] = []
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
            if scenario in {"web_basic", "advanced_browser", "tab_switch", "table_extract", "control_primitives", "network_capture", "firecrawl", "element_change"}:
                project = created.json()
                defaulted = await client.patch(
                    prefix,
                    headers={"Idempotency-Key": str(uuid4())},
                    json={
                        "expectedManagementRevision": project["managementRevision"],
                        "defaultResources": {**project["defaultResources"], "profileId": profile.id},
                    },
                )
                assert defaulted.status_code == 200, defaulted.text
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
                    **({} if scenario in {"web_basic", "advanced_browser", "tab_switch", "table_extract", "control_primitives", "network_capture", "firecrawl", "element_change"} else {"profileId": profile.id}),
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
                element_waiting = False
                if scenario == "element_stop" and detail["batch"]["status"] == "running":
                    current_tasks = (await client.get(prefix + "/tasks", params={"batchId": batch_id})).json()["items"]
                    for current_task in current_tasks:
                        current_attempts = (await client.get(prefix + f"/tasks/{current_task['taskId']}/node-attempts")).json()["items"]
                        element_waiting |= any(item["nodeId"] == "mutation-1" and item["status"] == "running" for item in current_attempts)
                if (scenario == "stop" or element_waiting or (scenario == "firecrawl_stop" and "/crawl/start" in requests)) and detail["batch"]["status"] == "running":
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
            if scenario == "element_change":
                assert detail["statusCounts"]["succeeded"] == 2, detail
                for task in tasks:
                    task_path = prefix + f"/tasks/{task['taskId']}"
                    outputs = (await client.get(task_path + "/outputs")).json()
                    values = {item["name"]: item["value"] for item in outputs["items"]}
                    assert set(values) == {"childList_selector", "childList_info", "attributes_info", "characterData_info"}
                    assert values["childList_selector"] == "#added"
                    assert values["childList_info"]["addedCount"] == 1
                    assert values["childList_info"]["newElementText"] == "新增内容"
                    assert values["attributes_info"]["changes"][0]["attributeName"] == "data-count"
                    assert values["characterData_info"]["changes"][0]["newValue"].startswith("新内容")
                    attempts = (await client.get(task_path + "/node-attempts")).json()
                    assert attempts["total"] == len(steps)
            elif scenario == "firecrawl":
                assert detail["statusCounts"]["succeeded"] == 2, detail
                for task in tasks:
                    task_path = prefix + f"/tasks/{task['taskId']}"
                    attempts = await client.get(task_path + "/node-attempts")
                    outputs = await client.get(task_path + "/outputs")
                    assert attempts.json()["total"] == 3
                    assert {item["status"] for item in attempts.json()["items"]} == {"succeeded"}
                    values = {item["name"]: item["value"] for item in outputs.json()["items"]}
                    assert set(values) == {"scraped", "links", "pages"}
                    assert "项目采集正文" in values["scraped"]["markdown"]
                    assert "must-not-be-extracted" not in values["scraped"]["html"]
                    assert "不属于正文的导航" not in values["scraped"]["html"]
                    assert values["links"] == [crawl_url.replace('/start', '/child'), crawl_url.replace('/start', '/from-map')]
                    assert [item["url"] for item in values["pages"]] == [crawl_url, crawl_url.replace('/start', '/child')]
                    artifact_path = task_path + "/artifacts"
                    artifacts = (await client.get(artifact_path)).json()
                    assert artifacts["total"] == 1
                    artifact = artifacts["items"][0]
                    screenshot = await client.get(artifact_path + f"/{artifact['artifactId']}/content")
                    assert screenshot.status_code == 200 and screenshot.content.startswith(b"\x89PNG\r\n\x1a\n")
                    assert hashlib.sha256(screenshot.content).hexdigest() == artifact["sha256"]
                assert '/sitemap.xml' in requests and '/crawl/child' in requests
            elif scenario == "network_capture":
                assert detail["statusCounts"]["succeeded"] == 2 and len([path for path in requests if path.startswith('/api/orders')]) >= 4
                for task in tasks:
                    task_path = prefix + f"/tasks/{task['taskId']}"
                    attempts = await client.get(task_path + "/node-attempts", params={"pageSize": 100})
                    outputs = await client.get(task_path + "/outputs")
                    assert attempts.status_code == outputs.status_code == 200
                    assert attempts.json()["total"] == len(steps)
                    values = {item["name"]: item["value"] for item in outputs.json()["items"]}
                    assert set(values) == {"first_request", "all_requests", "captured_urls"}
                    assert values["first_request"]["method"] == "GET"
                    assert values["first_request"]["headers"]["authorization"] == "[已隐藏]"
                    assert len(values["all_requests"]) == 1
                    assert len(values["captured_urls"]) == 1
                    assert "/api/orders" in values["captured_urls"][0]
                    assert "fixture-secret" not in str(values)
            elif scenario == "control_primitives":
                assert detail["statusCounts"]["succeeded"] == 2
                for task in tasks:
                    task_path = prefix + f"/tasks/{task['taskId']}"
                    attempts = await client.get(task_path + "/node-attempts")
                    outputs = await client.get(task_path + "/outputs")
                    assert attempts.status_code == outputs.status_code == 200
                    assert attempts.json()["total"] == 4
                    assert {item["status"] for item in attempts.json()["items"]} == {"succeeded"}
                    assert {item["name"]: item["value"] for item in outputs.json()["items"]} == {"checked": True}
            elif scenario == "web_basic":
                assert detail["statusCounts"]["succeeded"] == 2
                for task in tasks:
                    task_path = prefix + f"/tasks/{task['taskId']}"
                    attempts = await client.get(task_path + "/node-attempts", params={"pageSize": 100})
                    outputs = await client.get(task_path + "/outputs")
                    assert attempts.status_code == outputs.status_code == 200
                    assert attempts.json()["total"] == 15
                    assert {item["status"] for item in attempts.json()["items"]} == {"succeeded"}
                    assert {item["name"]: item["value"] for item in outputs.json()["items"]} == {
                        "injected_title": "AutoFlow B1 受控页面",
                        "dialog_message": "AutoFlow dialog",
                    }
                assert not app.state.project_workflow_worker_manager.busy()
            elif scenario == "tab_switch":
                assert detail["statusCounts"]["succeeded"] == 2
                for task in tasks:
                    task_path = prefix + f"/tasks/{task['taskId']}"
                    attempts = await client.get(task_path + "/node-attempts")
                    outputs = await client.get(task_path + "/outputs")
                    assert attempts.status_code == outputs.status_code == 200
                    assert attempts.json()["total"] == len(steps)
                    assert {item["status"] for item in attempts.json()["items"]} == {"succeeded"}
                    values = {item["name"]: item["value"] for item in outputs.json()["items"]}
                    assert values["first_title"] == "AutoFlow B1 受控页面"
                    assert values["last_title"] == "AutoFlow B2 网页动作受控页面"
                    assert values["first_url"] == first_page
                    assert values["last_url"] == second_page
                    assert values["first_index"] == 0
                    assert values["last_index"] == 1
                    assert values["first_button"] == "确认"
                    assert values["last_child"]
            elif scenario == "advanced_browser":
                assert detail["statusCounts"]["succeeded"] == 2
                for task in tasks:
                    task_path = prefix + f"/tasks/{task['taskId']}"
                    attempts = await client.get(task_path + "/node-attempts", params={"pageSize": 100})
                    outputs = await client.get(task_path + "/outputs")
                    artifacts = await client.get(task_path + "/artifacts")
                    assert attempts.status_code == outputs.status_code == artifacts.status_code == 200
                    assert attempts.json()["total"] == len(steps)
                    assert {item["status"] for item in attempts.json()["items"]} == {"succeeded"}
                    output_values = {item["name"]: item["value"] for item in outputs.json()["items"]}
                    assert output_values["children"] == ["#child-a", "#child-b"]
                    assert output_values["siblings"] == ["#sibling-a", "#sibling-b"]
                    assert {item["kind"] for item in artifacts.json()["items"]} == {"file", "image"}
                    assert artifacts.json()["total"] == 2
                    for item in artifacts.json()["items"]:
                        content = await client.get(task_path + f"/artifacts/{item['artifactId']}/content")
                        assert content.status_code == 200
                        if item["kind"] == "file":
                            assert content.content == "AutoFlow 下载".encode()
                            assert item["fileName"] == "fixture-download.txt"
                        else:
                            assert content.content.startswith(b"\x89PNG")
                            assert item["fileName"] == "fixture-image.png"
            elif scenario == "table_extract":
                assert detail["statusCounts"]["succeeded"] == 2
                for task in tasks:
                    task_path = prefix + f"/tasks/{task['taskId']}"
                    outputs = await client.get(task_path + "/outputs")
                    artifacts = await client.get(task_path + "/artifacts")
                    assert outputs.status_code == artifacts.status_code == 200
                    assert {item["name"]: item["value"] for item in outputs.json()["items"]} == {
                        "orders": [["订单", "金额"], ["A-001", "88"], ["A-002", "99"]],
                    }
                    assert artifacts.json()["total"] == 1
                    item = artifacts.json()["items"][0]
                    assert item["kind"] == "file" and item["fileName"].endswith(".xlsx")
                    content = await client.get(task_path + f"/artifacts/{item['artifactId']}/content")
                    assert content.status_code == 200
                    target = workspace / "workspace" / "runs" / task["runId"] / "generation-1" / "outputs" / "reports" / "orders.xlsx"
                    assert target.read_bytes() == content.content
                    assert hashlib.sha256(content.content).hexdigest() == item["sha256"]
                    workbook = load_workbook(io.BytesIO(content.content), read_only=True)
                    try:
                        assert list(workbook.active.values) == [
                            ("订单", "金额"), ("A-001", "88"), ("A-002", "99"),
                        ]
                    finally:
                        workbook.close()
            elif scenario == "page_load":
                assert detail["statusCounts"]["succeeded"] == 2 and len(requests) >= 2
                for task in tasks:
                    task_path = prefix + f"/tasks/{task['taskId']}"
                    attempts = await client.get(task_path + "/node-attempts")
                    outputs = await client.get(task_path + "/outputs")
                    assert attempts.status_code == outputs.status_code == 200
                    assert attempts.json()["total"] == 3
                    assert {item["status"] for item in attempts.json()["items"]} == {"succeeded"}
                    assert [(item["name"], item["value"]) for item in outputs.json()["items"]] == [("page_ready", True)]
            elif scenario == "success":
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
            elif scenario in {"stop", "firecrawl_stop", "element_stop"}:
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
            if scenario in {"firecrawl_failure", "firecrawl_stop"}:
                expected_request = "/crawl/unavailable" if scenario == "firecrawl_failure" else "/crawl/start"
                assert expected_request in requests
                assert "/crawl/child" not in requests
                for task in tasks:
                    outputs = await client.get(prefix + f"/tasks/{task['taskId']}/outputs")
                    assert outputs.json()["items"] == []
            if scenario in {"element_timeout", "element_stop"}:
                for task in tasks:
                    outputs = await client.get(prefix + f"/tasks/{task['taskId']}/outputs")
                    assert outputs.json()["items"] == []
            assert not app.state.project_workflow_worker_manager.busy()
            assert app.state.project_workflow_dispatcher.blockers() == []
            assert app.state.project_run_scheduler.blockers() == []
            assert (workspace / "tmp").is_dir()
            assert not list((workspace / "tmp").glob("**/generation-*"))
    finally:
        for callback in app.router.on_shutdown:
            result = callback()
            if inspect.isawaitable(result):
                await result
