"""Opt-in production worker login → data write/status → End → fresh-run reuse."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest

from autoflow.application.environments.service import EnvironmentService
from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_runs.end import ProjectRunEnd
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.projects.service import ProjectService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore
from autoflow.infrastructure.process.project_test_browser_worker import (
    browser_worker_payload,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from autoflow.providers.browser.environment_browser import EnvironmentBrowserLauncher
from tests.integration.test_project_run_data_start import _setup, uid
from tests.integration.test_project_worker_capabilities import save_data_workflow


@pytest.mark.asyncio
@pytest.mark.parametrize("close_receipt,control_flow", [("confirmed", kind) for kind in ("linear", "loop", "workflow", "module", "canvas")] + [("unknown", "linear")])
async def test_real_login_retained_and_reused_by_next_production_run(
    tmp_path, valid_profile_values, close_receipt, control_flow, monkeypatch
):
    configured = os.environ.get("AUTOFLOW_TEST_CLOAKBROWSER")
    if not configured:
        pytest.skip("AUTOFLOW_TEST_CLOAKBROWSER must identify a real installed kernel")
    executable = Path(configured).resolve(strict=True)
    observations = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            signed_in = "session=pm9-local-login" in self.headers.get("Cookie", "")
            observations.append({"path": self.path, "signedIn": signed_in})
            self.send_response(200)
            if self.path == "/login":
                self.send_header(
                    "Set-Cookie",
                    "session=pm9-local-login; Path=/; Max-Age=3600; HttpOnly; SameSite=Lax",
                )
                signed_in = True
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                (
                    '<body><div id="state">'
                    + ("signed-in" if signed_in else "signed-out")
                    + "</div></body>"
                ).encode()
            )

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    factory, project, automation, coordinator = _setup(
        tmp_path,
        resolve_status_input_ids=lambda a: [
            i["inputId"] for i in a.input_plan["inputs"]
        ],
    )
    store = EnvironmentStore(tmp_path / "environments")
    launcher = EnvironmentBrowserLauncher(None, list, store)
    environments = EnvironmentService(
        ProjectService(SqlAlchemyProjects(factory)),
        SqlAlchemyEnvironments(factory),
        store,
        closer=launcher.closer,
    )
    ends = ProjectRunEnd(factory, environments)
    worker = ProjectWorkflowWorkerManager(
        tmp_path / "worker",
        project_data=ProjectDataCapabilityService(
            SqlAlchemyProjectDataCapabilities(factory), project_end=ends
        ),
    )
    if frozen_worker := os.environ.get("AUTOFLOW_TEST_PROJECT_WORKER"):
        worker._command = (str(Path(frozen_worker).resolve(strict=True)), "--project-workflow-worker")
    original_run = worker.run
    original_force = worker.force_stop
    if close_receipt == "unknown":
        from autoflow.infrastructure.process.workflow_worker import WorkerOutcome

        async def unconfirmed(**kwargs):
            outcome = await original_run(**kwargs)
            assert outcome.cleanup_confirmed
            return WorkerOutcome(outcome.status, outcome.error, False)

        async def reject_cleanup(_run_id):
            raise RuntimeError(
                "injected lost browser close receipt after actual worker cleanup"
            )

        monkeypatch.setattr(worker, "run", unconfirmed)
        monkeypatch.setattr(worker, "force_stop", reject_cleanup)
    now = datetime.now(UTC)
    profile = Profile(
        uid(),
        ProfileSpec.from_values({**valid_profile_values, "headless": True}),
        31415,
        now,
        now,
    )
    leases = []

    class Resources:
        async def acquire(self, _request, run_request_id):
            instance = environments.environments.active_instance_for_run_request(
                run_request_id
            )
            browser = browser_worker_payload(run_request_id, profile, None, None)
            browser["headless"] = True
            browser["userDataDir"] = str(
                environments.instance_path(instance.instance_id)
            )
            lease = SimpleNamespace(
                browser=browser, executable=executable, released=False
            )

            def release():
                lease.released = True

            lease.release = release
            leases.append(lease)
            return lease

    async def recover(_run):
        raise AssertionError("positive chain must not need unknown ownership recovery")

    dispatcher = WorkflowRunDispatcher(
        factory, worker, Resources(), QuiesceGate(), recover, project_end=ends
    )
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    report = {"workspace": str(tmp_path), "kernel": str(executable), "worker": os.environ.get("AUTOFLOW_TEST_PROJECT_WORKER", "source"), "controlFlow": control_flow, "runs": []}
    try:
        save_data_workflow(factory, automation)
        document = documents.get(automation.workflow_id).to_payload()
        source = automation.input_plan["inputs"][0]
        catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
        status = catalog.create_status(
            project,
            source["tableId"],
            uid(),
            {
                "name": "已登录",
                "color": "#8f4b2b",
                "order": 1,
                "expectedTableRevision": 2,
            },
        )[0]["status"]

        def node(node_id, kind, config, x=1000):
            return {
                "id": node_id,
                "type": kind,
                "position": {"x": x, "y": 0},
                "data": {"moduleType": kind, "config": config},
            }

        original = document["nodes"]
        ref = "{snapshot['inputs'][0]['recordRef']}"
        arguments = json.dumps(
            {
                "recordRef": ref,
                "statusId": status["statusId"],
                "expectedStatusRevision": 1,
            }
        ).replace(json.dumps(ref), ref)
        document["nodes"] = [
            node("login", "open_page", {"url": base + "/login", "timeout": 15}),
            *original,
            node(
                "status",
                "project_data",
                {
                    "action": "status",
                    "resultVariable": "status_result",
                    "binding": {
                        "tableId": source["tableId"],
                        "datasetGeneration": source["datasetGeneration"],
                        "fieldIds": [],
                    },
                    "arguments": arguments,
                },
            ),
            node(
                "end",
                "project_end",
                {"retainEnvironment": True, "name": "PM9 actual login"},
            ),
        ]

        def chain(doc):
            doc["edges"] = [
                {"id": f"{left['id']}-{right['id']}", "source": left["id"], "target": right["id"]}
                for i, (left, right) in enumerate(
                    zip(doc["nodes"], doc["nodes"][1:], strict=False)
                )
            ]

        chain(document)
        if control_flow != "linear":
            from copy import deepcopy

            end_node = document["nodes"].pop()
            document["edges"].pop()
            before = node("before-end", "open_page", {"url": base + "/before-end", "timeout": 15})
            forbidden = node("forbidden-inner", "open_page", {"url": base + "/forbidden-inner", "timeout": 15})
            after = node("forbidden-parent", "open_page", {"url": base + "/forbidden-parent", "timeout": 15})
            child = deepcopy(document)
            child.update(id=uid(), name="End child", projectId=project, nodes=[before, end_node, forbidden], variables=[])
            chain(child)
            if control_flow == "workflow":
                saved_child = documents.create(child, client_request_id=uid())
                call = node("call", "run_workflow_file", {"workflowFile": saved_child.id})
            elif control_flow == "module":
                from autoflow.application.workflows.modules import CustomModuleService
                from autoflow.application.workflows.runtime import (
                    WorkflowRuntimeService,
                )
                from autoflow.infrastructure.database.workflow_modules import (
                    SqlAlchemyWorkflowModules,
                )
                from autoflow.infrastructure.database.workflows import (
                    SqlAlchemyWorkflowRepository,
                )

                modules = CustomModuleService(SqlAlchemyWorkflowModules(factory))
                module = modules.create({"name": "end_child", "display_name": "End child", "parameters": [], "outputs": [], "workflow": child}, client_request_id=uid())
                coordinator._core = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory), modules=modules)
                call = node("call", "custom_module", {"customModuleId": module.id})
            elif control_flow == "canvas":
                call = node("call", "subflow", {"subflowGroupId": "header"})
            else:
                call = node("call", "loop", {"loopCount": 3})
            document["nodes"].extend([call, after])
            chain(document)
            if control_flow in {"loop", "canvas"}:
                document["nodes"].extend(child["nodes"])
                document["edges"].extend(child["edges"])
                if control_flow == "loop":
                    document["edges"][-3]["sourceHandle"] = "done"
                    document["edges"].append({"id": "body", "source": "call", "target": "before-end", "sourceHandle": "loop"})
                else:
                    for member in child["nodes"]:
                        member["position"] = {"x": 2100, "y": 20}
                    document["nodes"].append({"id": "header", "type": "group", "position": {"x": 2000, "y": 0}, "data": {"moduleType": "group", "isSubflow": True, "width": 800, "height": 600}})
        documents.update(
            automation.workflow_id,
            document,
            expected_revision=2,
            client_request_id=uid(),
        )
        saved = None
        for number in (1, 2):
            batch = coordinator.start(
                project,
                automation.automation_id,
                uid(),
                {
                    "expectedAutomationRevision": automation.management_revision,
                    "parameters": {},
                    "maxTasks": 1,
                    "concurrency": 1,
                },
            )[0]
            assert (
                ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id)
                == "ready"
            )
            task = coordinator.list_tasks(project, batch.batch_id)[0]
            policy = (
                {"source": "newFromProfile", "profileId": profile.id}
                if saved is None
                else {
                    "source": "fixedEnvironment",
                    "environmentId": saved["environmentId"],
                }
            )
            instance = environments.reserve(
                project,
                environments.resolve(project, policy),
                task_id=task.task_id,
                run_id=task.run_id,
                holder_kind="task",
                holder_id=task.task_id,
            )
            environments.environments.set_instance_state(instance.instance_id, "active")
            run = dispatcher.query_run(task.run_id)
            await dispatcher.dispatch(
                run.run_id,
                expected_status_revision=run.status_revision,
                execution_generation=run.execution_generation,
            )
            async with asyncio.timeout(90):
                await dispatcher.wait_idle()
            with factory() as session:
                events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(
                    run.run_id, after_sequence=0, limit=200
                )
            final = dispatcher.query_run(run.run_id)
            if number == 1 and control_flow != "linear":
                assert not any(o["path"].startswith("/forbidden") for o in observations), observations
                assert sum(o["path"] == "/before-end" for o in observations) == 1, observations
                assert not any((e.node_id or "").startswith("forbidden") for e in events), [(e.node_id, e.payload) for e in events]
            if close_receipt == "unknown":
                assert final.status == "reconciling" and not leases[-1].released
                assert ends.operation(run.run_id)[0].result is None
                assert environments.environments.list(project)[1] == 0
                report["runs"].append(
                    {
                        "runId": run.run_id,
                        "taskId": task.task_id,
                        "status": final.status,
                        "published": False,
                        "leaseHeld": True,
                    }
                )
                report["requests"] = observations
                report["verified"] = True
                break
            assert final.status == "succeeded", [(e.kind, e.payload) for e in events]
            outcome = ends.operation(run.run_id)[0].result
            assert outcome["complete"] and not worker.busy() and leases[-1].released
            report["runs"].append(
                {
                    "runId": run.run_id,
                    "taskId": task.task_id,
                    "status": final.status,
                    "end": outcome,
                }
            )
            if number == 1:
                saved = outcome["saved"]
                assert outcome["targets"]
                assert any(
                    e.node_id == "status" and e.payload.get("status") == "succeeded"
                    for e in events
                )
                await ProjectBatchScheduler(
                    factory, dispatcher, QuiesceGate(), environments
                ).tick()
                document["nodes"] = [
                    node(
                        "reuse", "open_page", {"url": base + "/status", "timeout": 15}
                    ),
                    node(
                        "read-session",
                        "get_element_info",
                        {
                            "selector": "#state",
                            "attribute": "text",
                            "variableName": "session_state",
                            "timeout": 5,
                        },
                    ),
                    node("end", "project_end", {"retainEnvironment": False}),
                ]
                chain(document)
                documents.update(
                    automation.workflow_id,
                    document,
                    expected_revision=3,
                    client_request_id=uid(),
                )
            else:
                assert any(
                    e.kind == "output"
                    and e.payload.get("name") == "session_state"
                    and e.payload.get("value") == "signed-in"
                    for e in events
                )
        if close_receipt == "confirmed":
            assert any(o["path"] == "/status" and o["signedIn"] for o in observations)
        report["requests"] = observations
        report["verified"] = True
    finally:
        monkeypatch.setattr(worker, "force_stop", original_force)
        dispatcher._owner_cleanup_unknown = (
            False  # real worker.run already confirmed cleanup before fault injection
        )
        await dispatcher.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(3)
        factory.dispose()
        (tmp_path / "pm9-end-real-evidence.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str)
        )
