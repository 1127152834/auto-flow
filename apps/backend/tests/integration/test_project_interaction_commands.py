"""SQLite command contract, controlled worker transport; not Electron acceptance."""

import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from autoflow.application.project_runs.interactions import ProjectRunInteractions
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_run_dispatch import services


def prepare(tmp_path, kind="input_prompt"):
    factory, coordinator, project, batch, *_ = services(tmp_path)
    task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
    with factory() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.status = "running"
        session.commit()
    sent = []

    async def send(run_id, generation, command):
        sent.append((run_id, generation, command))

    service = ProjectRunInteractions(factory, send)
    request_id = str(uuid4())
    event = {
        "runId": task.run_id,
        "executionGeneration": 0,
        "kind": "interaction",
        "payload": {
            "type": f"execution:{kind}",
            "requestId": request_id,
            "defaultValue": "private-default",
            "code": "private-code",
        },
    }
    service.observe(event)
    return factory, project.project_id, task, service, request_id, event, sent


@pytest.mark.asyncio
async def test_durable_receipt_only_applied_after_worker_confirmation(tmp_path):
    factory, project, task, service, request, event, sent = prepare(tmp_path)
    command = str(uuid4())
    data = {"requestId": request, "value": "private-response"}
    first = await service.submit(
        project, task.task_id, command, 0, "input_prompt_result", data
    )
    assert first["status"] == "accepted"
    assert (
        await service.submit(
            project, task.task_id, command, 0, "input_prompt_result", data
        )
    ) == first
    assert len(sent) == 1
    assert "private-default" not in json.dumps(service.public_event(event))
    assert (
        service.request(project, task.task_id, request)["defaultValue"]
        == "private-default"
    )
    with factory() as session:
        row = session.get(ProjectOperationRow, command)
        assert "private-response" not in json.dumps(
            {"resource": row.resource, "result": row.result}
        )
        service.confirm(
            session,
            {
                **event,
                "payload": {
                    "type": "execution:command_applied",
                    "commandId": command,
                    "requestId": request,
                },
            },
        )
        session.commit()
    assert service.command(project, task.task_id, command)["status"] == "applied"
    restarted = ProjectRunInteractions(factory, service._send)
    assert restarted.command(project, task.task_id, command)["status"] == "applied"
    with pytest.raises(ProjectRunError, match="不同请求"):
        await service.submit(
            project,
            task.task_id,
            command,
            0,
            "input_prompt_result",
            {**data, "value": "different"},
        )
    factory.dispose()


@pytest.mark.asyncio
async def test_scope_generation_duplicate_reply_and_stop_are_fenced(tmp_path):
    factory, project, task, service, request, _, sent = prepare(tmp_path)
    data = {"requestId": request, "value": "answer"}
    with pytest.raises(ProjectRunError):
        service.request(str(uuid4()), task.task_id, request)
    with pytest.raises(ProjectRunError):
        await service.submit(
            project, task.task_id, str(uuid4()), 1, "input_prompt_result", data
        )
    await service.submit(
        project, task.task_id, str(uuid4()), 0, "input_prompt_result", data
    )
    with pytest.raises(ProjectRunError):
        await service.submit(
            project, task.task_id, str(uuid4()), 0, "input_prompt_result", data
        )
    with factory() as session:
        session.get(WorkflowRunRow, task.run_id).status = "stopping"
        session.commit()
    assert service.request(project, task.task_id, request)["status"] == "cancelled"
    assert len(sent) == 1
    factory.dispose()


@pytest.mark.asyncio
async def test_script_claim_survives_reconnect_and_rejects_other_client(tmp_path):
    factory, project, task, service, request, _, sent = prepare(tmp_path, "js_script")
    claim = str(uuid4())
    data = {"requestId": request, "claimId": claim}
    await service.submit(
        project, task.task_id, str(uuid4()), 0, "js_script_claim", data
    )
    assert service.request(project, task.task_id, request)["claimId"] == claim
    with pytest.raises(ProjectRunError):
        await service.submit(
            project,
            task.task_id,
            str(uuid4()),
            0,
            "js_script_claim",
            {**data, "claimId": str(uuid4())},
        )
    result = {**data, "success": True, "result": 7, "variables": {"x": 7}}
    await service.submit(
        project, task.task_id, str(uuid4()), 0, "js_script_result", result
    )
    assert len(sent) == 1 and sent[0][2]["result"] == 7
    with factory() as session:
        rows = session.scalars(
            select(ProjectOperationRow).where(
                ProjectOperationRow.kind == "workflowInteraction"
            )
        ).all()
        assert len(rows) == 2
    factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["input_prompt", "js_script"])
async def test_http_to_real_worker_confirmed_in_same_event_transaction(tmp_path, kind):
    """Real subprocess + SQLite + TCP/SSE; renderer payload is controlled, not UI proof."""
    import asyncio
    import socket
    from types import SimpleNamespace

    import uvicorn
    from fastapi import FastAPI
    from httpx import AsyncClient

    from autoflow.adapters.http.errors import install_error_handlers
    from autoflow.adapters.http.project_run_events import project_run_events_router
    from autoflow.adapters.http.project_run_interactions import (
        project_run_interactions_router,
    )
    from autoflow.adapters.http.project_schemas import ProjectOperationView
    from autoflow.adapters.http.projects import _op
    from autoflow.application.project_runs.events import ProjectRunEvents
    from autoflow.application.settings.runtime import QuiesceGate
    from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
    from autoflow.infrastructure.database.projects import SqlAlchemyProjects
    from autoflow.infrastructure.process.project_workflow_worker import (
        ProjectWorkflowWorkerManager,
    )
    from tests.fixtures.workflow_runs import SyntheticResources
    from tests.integration.test_project_interactive_worker import plan

    factory, project, task, _, _, _, _ = prepare(tmp_path, kind)
    with factory() as session:
        session.get(WorkflowRunRow, task.run_id).execution_generation = 1
        session.commit()
    manager = ProjectWorkflowWorkerManager(tmp_path / "worker")
    gate = QuiesceGate()

    async def cleanup(_):
        pass

    dispatcher = WorkflowRunDispatcher(
        factory, manager, SyntheticResources(), gate, cleanup
    )
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(project_run_interactions_router(dispatcher.interactions, gate))
    app.include_router(project_run_events_router(ProjectRunEvents(factory)))
    run = dispatcher.query_run(task.run_id)
    content = SimpleNamespace(execution_plan={"orderedNodeIds": ["request", "after"]})
    ready = asyncio.Event()
    request = {}

    async def persist(event):
        await dispatcher._commit_event(run, content, event)
        if (
            event["kind"] == "interaction"
            and event["payload"]["type"] == f"execution:{kind}"
        ):
            request.update(event["payload"])
            ready.set()

    config = (
        {
            "variableName": "answer",
            "inputMode": "password",
            "defaultValue": "private-default",
        }
        if kind == "input_prompt"
        else {"code": "function main(vars) { return 7 }", "resultVariable": "answer"}
    )
    execution = asyncio.create_task(
        manager.run(
            run_id=task.run_id,
            execution_generation=1,
            execution_plan=plan(kind, config),
            parameters={},
            variables={"count": 1},
            browser={},
            executable=None,
            on_event=persist,
        )
    )
    base = f"/api/v1/projects/{project}/tasks/{task.task_id}"
    # Same loopback Uvicorn setup as the existing Studio log delivery contract.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                await asyncio.sleep(.01)
        waiting = asyncio.create_task(ready.wait())
        done, _ = await asyncio.wait(
            {waiting, execution}, timeout=15, return_when=asyncio.FIRST_COMPLETED
        )
        if execution in done:
            waiting.cancel()
            await execution
            pytest.fail("worker ended before requesting input")
        if waiting not in done:
            waiting.cancel()
            pytest.fail("worker did not request input")
        async with AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False
        ) as client:
            page = await client.get(f"{base}/events")
            assert page.status_code == 200
            assert (
                "private-default" not in page.text and "function main" not in page.text
            )
            view = await client.get(
                f"{base}/interactions/requests/{request['requestId']}"
            )
            assert (
                view.status_code == 200 and view.headers["cache-control"] == "no-store"
            )
            wrong_project = base.replace(project, str(uuid4()))
            assert (
                await client.get(
                    f"{wrong_project}/interactions/requests/{request['requestId']}"
                )
            ).status_code == 404
            command_id = str(uuid4())
            data = {"requestId": request["requestId"], "value": "private-response"}
            if kind == "js_script":
                claim = {"requestId": request["requestId"], "claimId": str(uuid4())}
                response = await client.post(
                    f"{base}/interactions/commands",
                    json={
                        "commandId": str(uuid4()),
                        "executionGeneration": 1,
                        "event": "js_script_claim",
                        "data": claim,
                    },
                )
                assert (
                    response.status_code == 202
                    and response.json()["status"] == "applied"
                )
                data = {
                    **claim,
                    "success": True,
                    "result": 7,
                    "variables": {"count": 2},
                }
            body = {
                "commandId": command_id,
                "executionGeneration": 1,
                "event": f"{kind}_result",
                "data": data,
            }
            response = await client.post(f"{base}/interactions/commands", json=body)
            assert response.status_code == 202
            outcome = await asyncio.wait_for(execution, 15)
            assert outcome.status == "succeeded" and outcome.cleanup_confirmed
            receipt = await client.get(f"{base}/interactions/commands/{command_id}")
            assert receipt.json()["status"] == "applied"
            assert (
                await client.post(f"{base}/interactions/commands", json=body)
            ).json() == receipt.json()
            page = await client.get(f"{base}/events")
            assert page.status_code == 200
            assert (
                "private-response" not in page.text
                and "private-default" not in page.text
            )
            assert (
                sum(
                    e["payload"].get("commandId") == command_id
                    for e in page.json()["items"]
                )
                == 1
            )
            assert (
                await client.get(f"{base}/interactions/requests/{request['requestId']}")
            ).status_code == 410
            persisted = page.json()["items"]

            async def frames(after):
                received = []
                async with client.stream("GET", f"{base}/events/stream", headers={"Last-Event-ID": str(after)}) as response:
                    assert response.status_code == 200
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            received.append(json.loads(line[6:]))
                            if received[-1]["sequence"] == persisted[-1]["sequence"]:
                                break
                return received

            streamed = await frames(0)
            resumed = await frames(streamed[0]["sequence"])
            assert streamed == persisted and resumed == persisted[1:]
            assert "private-response" not in json.dumps(streamed)
            assert "private-default" not in json.dumps(streamed)
            operation = SqlAlchemyProjects(factory).get_operation(
                operation_id=command_id, project_id=project
            )
            ProjectOperationView.model_validate(_op(operation))
    finally:
        if not execution.done():
            execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
        await manager.shutdown()
        server.should_exit = True
        await asyncio.wait_for(serving, 5)
        sock.close()
        factory.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event,data",
    [
        ("input_prompt_result", {"value": 3}),
        ("input_prompt_result", {"value": "ok", "extra": True}),
        ("js_script_claim", {"claimId": ""}),
        ("js_script_result", {"claimId": "c", "success": True, "variables": []}),
        ("js_script_result", {"claimId": "c", "success": False, "error": ""}),
        (
            "js_script_result",
            {"claimId": "c", "success": True, "variables": {"x": float("nan")}},
        ),
        ("unknown", {}),
    ],
)
async def test_invalid_command_cannot_reserve_or_send(tmp_path, event, data):
    factory, project, task, service, request, _, sent = prepare(tmp_path)
    with pytest.raises(ProjectRunError) as error:
        await service.submit(
            project,
            task.task_id,
            str(uuid4()),
            0,
            event,
            {"requestId": request, **data},
        )
    assert error.value.status == 422
    assert not sent
    assert service.request(project, task.task_id, request)["status"] == "pending"
    factory.dispose()


@pytest.mark.asyncio
async def test_lost_send_is_never_replayed_and_terminal_settles_receipt(tmp_path):
    factory, project, task, service, request, _, sent = prepare(tmp_path)

    async def lost(*args):
        sent.append(args)
        raise RuntimeError("connection lost")

    service._send = lost
    command = str(uuid4())
    data = {"requestId": request, "value": "answer"}
    with pytest.raises(RuntimeError):
        await service.submit(
            project, task.task_id, command, 0, "input_prompt_result", data
        )
    assert (
        await service.submit(
            project, task.task_id, command, 0, "input_prompt_result", data
        )
    )["status"] == "accepted"
    assert len(sent) == 1
    from autoflow.infrastructure.database.workflow_runtime import (
        SqlAlchemyWorkflowRuntimeRepository,
    )

    with factory() as session:
        row = session.get(WorkflowRunRow, task.run_id)
        row.status = "interrupted"
        session.flush()
        run = SqlAlchemyWorkflowRuntimeRepository(session).get_run(run_id=task.run_id)
        service.finish(session, run)
        session.commit()
    assert service.command(project, task.task_id, command)["status"] == "unconfirmed"
    with factory() as session:
        assert session.get(ProjectOperationRow, command).status == "failed"
    service.forget_run(task.run_id)
    assert not service._requests
    factory.dispose()


@pytest.mark.asyncio
async def test_replayed_persisted_request_cannot_reopen_closed_interaction(tmp_path):
    from datetime import UTC, datetime
    from types import SimpleNamespace

    factory, coordinator, project, batch, _, core, _, _ = services(tmp_path)
    task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
    with factory() as session:
        session.get(WorkflowRunRow, task.run_id).status = "running"
        session.commit()
    run = core.query_run(task.run_id)
    request_id = str(uuid4())
    event = {
        "eventId": str(uuid4()),
        "runId": task.run_id,
        "executionGeneration": 0,
        "kind": "interaction",
        "nodeId": None,
        "nodeVisitId": None,
        "attempt": None,
        "occurredAt": datetime.now(UTC).isoformat(),
        "payload": {"type": "execution:input_prompt", "requestId": request_id},
    }
    content = SimpleNamespace(execution_plan={})
    await core._commit_event(run, content, event)
    await core._commit_event(
        run,
        content,
        {
            **event,
            "eventId": str(uuid4()),
            "payload": {
                "type": "execution:input_prompt_closed",
                "requestId": request_id,
                "status": "cancelled",
            },
        },
    )
    await core._commit_event(run, content, event)
    with pytest.raises(ProjectRunError) as error:
        core.interactions.request(project.project_id, task.task_id, request_id)
    assert error.value.status == 410
    factory.dispose()


def test_discovery_only_exposes_live_request_identity(tmp_path):
    factory, project, task, service, request, _, _ = prepare(tmp_path)
    items = service.pending()
    assert items == [{"projectId": project, "taskId": task.task_id, "runId": task.run_id, "executionGeneration": 0, "requestId": request, "type": "execution:input_prompt", "status": "pending"}]
    assert "private" not in json.dumps(items)
    with factory() as session:
        session.get(WorkflowRunRow, task.run_id).status = "stopping"
        session.commit()
    assert service.pending() == []
    factory.dispose()
