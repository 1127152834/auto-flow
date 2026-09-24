"""Real project worker protocol; renderer replies are controlled contract data, not UI proof."""
import asyncio
import json
from uuid import uuid4

import pytest

from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
    WorkflowWorkerError,
)


def plan(kind, config):
    return {"document": {"nodes": [
        {"id": "request", "data": {"moduleType": kind, "config": config}},
        {"id": "after", "data": {"moduleType": "print_log", "config": {"logMessage": "{count}:{answer}"}}},
    ], "edges": [{"id": "next", "source": "request", "target": "after"}]}}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,mode,value,expected", [
    ("input_prompt", "integer", "42", 42),
    ("input_prompt", "integer", None, "before"),
    ("js_script", None, 7, 7),
    ("input_prompt", "password", "test-only-private-value", "test-only-private-value"),
])
@pytest.mark.parametrize("nested", [False, True])
async def test_project_worker_reuses_source_interaction_and_ack(tmp_path, kind, mode, value, expected, nested):
    from autoflow.domain.workflows.catalog import runnable_module_types

    assert {"input_prompt", "js_script"} <= runnable_module_types()
    manager = ProjectWorkflowWorkerManager(tmp_path / "worker")
    run_id, command_id = str(uuid4()), str(uuid4())
    events = []
    requested = asyncio.Event()

    async def persist(event):
        events.append(event)
        if event["kind"] == "interaction" and event["payload"]["type"] == f"execution:{kind}":
            requested.set()

    config = ({"variableName": "answer", "inputMode": mode, "timeout": 0}
              if kind == "input_prompt" else
              {"code": "function main(vars){vars.count++;return 7}", "resultVariable": "answer"})
    execution_plan = plan(kind, config)
    if nested:
        execution_plan = {
            "document": {"nodes": [{"id": "call", "data": {"moduleType": "run_workflow_file", "config": {"workflowFile": "child"}}}], "edges": []},
            "workflowDependencies": {"child": {"id": "child", "name": "子流程", **execution_plan["document"]}},
        }
    task = asyncio.create_task(manager.run(
        run_id=run_id, execution_generation=1, execution_plan=execution_plan,
        parameters={}, variables={"answer": "before", "count": 1}, browser={}, executable=None,
        on_event=persist,
    ))
    try:
        await asyncio.wait_for(requested.wait(), 15)
        request = next(e for e in events if e["kind"] == "interaction")["payload"]
        assert not any(e.get("nodeId") == "after" for e in events)
        assert request["nodeId"] == "request" and request["executionId"]
        if nested:
            assert request["executionContext"]["scopes"] == [{"kind": "workflow", "id": "child", "name": "子流程"}]
        payload = {"type": f"{kind}_result", "commandId": command_id, "requestId": request["requestId"]}
        if kind == "input_prompt":
            assert request["inputMode"] == mode
            payload["value"] = value
        else:
            assert request["variables"] == {"answer": "before", "count": 1}
            payload.update(success=True, result=value, variables={"answer": "before", "count": 2})
        for wrong_run, wrong_generation in [(str(uuid4()), 1), (run_id, 2), (run_id, True)]:
            with pytest.raises(WorkflowWorkerError, match="交互请求已结束"):
                await manager.send_command(wrong_run, wrong_generation, payload)
        await manager.send_command(run_id, 1, payload)
        outcome = await asyncio.wait_for(task, 15)
        assert outcome.status == "succeeded" and outcome.cleanup_confirmed
        assert not manager.busy()
        receipts = [e for e in events if e["kind"] == "interaction" and e["payload"]["type"] == "execution:command_applied"]
        assert len(receipts) == 1 and receipts[0]["payload"]["commandId"] == command_id
        closed = [e["payload"] for e in events if e["kind"] == "interaction" and e["payload"]["type"].endswith("_closed")]
        assert len(closed) == 1
        assert closed[0]["status"] == ("cancelled" if value is None else "answered" if kind == "input_prompt" else "completed")
        if mode == "password":
            assert value not in json.dumps(events)
        else:
            assert any(e["kind"] == "log" and e["payload"]["message"] == f"{2 if kind == 'js_script' else 1}:{expected}" for e in events)
        outputs = [e["payload"]["value"] for e in events if e["kind"] == "output" and e["payload"]["name"] == "answer"]
        assert outputs == ([] if mode == "password" else [expected])
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("competing_reply", [False, True])
async def test_stop_cancels_project_prompt_without_starting_next_node(tmp_path, competing_reply):
    manager = ProjectWorkflowWorkerManager(tmp_path / "worker")
    run_id = str(uuid4())
    events = []
    requested = asyncio.Event()

    async def persist(event):
        events.append(event)
        if event["kind"] == "interaction" and event["payload"]["type"] == "execution:input_prompt":
            requested.set()

    task = asyncio.create_task(manager.run(
        run_id=run_id, execution_generation=1,
        execution_plan=plan("input_prompt", {"variableName": "answer", "timeout": 0}),
        parameters={}, variables={}, browser={}, executable=None, on_event=persist,
    ))
    try:
        await asyncio.wait_for(requested.wait(), 15)
        if competing_reply:
            worker = manager._workers.get(run_id)
            assert worker is not None
            request = next(e["payload"] for e in events if e["kind"] == "interaction")
            await worker.write_lock.acquire()
            reply = asyncio.create_task(manager.send_command(run_id, 1, {
                "type": "input_prompt_result", "commandId": str(uuid4()),
                "requestId": request["requestId"], "value": "late",
            }))
            await asyncio.sleep(0)
            stop = asyncio.create_task(manager.stop(run_id))
            await asyncio.sleep(0)
            worker.write_lock.release()
            with pytest.raises(WorkflowWorkerError, match="交互请求已结束"):
                await reply
            await stop
        else:
            await manager.stop(run_id)
        outcome = await asyncio.wait_for(task, 5)
        assert outcome.status == "cancelled" and outcome.cleanup_confirmed
        assert not manager.busy()
        assert not any(e.get("nodeId") == "after" for e in events)
        assert not any(e["kind"] == "output" for e in events)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await manager.shutdown()
