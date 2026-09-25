"""Real worker pipes and graph runtime with an owned synthetic proxy service."""

import asyncio
from uuid import uuid4

import pytest

from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


class ProxyService:
    def __init__(self):
        self.calls = []
        self.released = []

    async def call(self, owner, payload):
        self.calls.append((owner, payload))
        method = payload["method"]
        if method == "query":
            return {
                "status": "succeeded",
                "proxyId": "p",
                "after": {"exitIp": "8.8.8.8"},
            }
        if method == "prepare":
            return {"proxyId": "p", "current": False, "before": {"exitIp": "8.8.8.8"}}
        if method == "attempt":
            return {
                "status": "succeeded",
                "operationId": "op",
                "requestsSent": 1,
                "after": {"exitIp": "1.1.1.1", "city": "Dallas"},
                "error": None,
            }
        return {}

    def release(self, owner):
        self.released.append(owner)


def document(kind):
    return {
        "nodes": [
            {
                "id": "proxy",
                "type": "moduleNode",
                "data": {
                    "moduleType": kind,
                    "target": "specified",
                    "proxyId": "p",
                    "locationId": "target",
                    "resultVariable": "proxy_result",
                    "maxAttempts": 1,
                },
            }
        ],
        "edges": [],
        "variables": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["proxy_query", "proxy_change_ip", "proxy_change_location"]
)
@pytest.mark.parametrize("host", ["studio", "project"])
async def test_proxy_nodes_over_real_owned_worker_pipes(tmp_path, host, kind):
    service = ProxyService()
    events = []
    run_id = str(uuid4())
    if host == "studio":
        manager = WorkflowWorkerManager(
            tmp_path,
            proxy_service=service,
            on_event=events.append,
        )
        await manager.start(
            run_id,
            "profile",
            None,
            {
                "runId": run_id,
                "workflowId": "flow",
                "profileId": "profile",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "artifacts"),
                "document": document(kind),
            },
        )
        async with asyncio.timeout(15):
            while manager.busy():
                await asyncio.sleep(0.01)
        terminal = [
            e
            for e in events
            if e.get("type") in {"execution:completed", "execution:failed"}
        ]
        assert terminal and terminal[-1]["type"] == "execution:completed", events
        result = next(
            e["data"] for e in events if e.get("type") == "execution:node_complete"
        )
    else:
        manager = ProjectWorkflowWorkerManager(
            tmp_path, proxy_service=service
        )

        async def emit(event):
            events.append(event)

        outcome = await manager.run(
            run_id=run_id,
            execution_generation=3,
            execution_plan={"document": document(kind)},
            parameters={},
            variables={},
            browser={},
            executable=None,
            on_event=emit,
        )
        assert outcome.status == "succeeded", events
        result = next(
            e["payload"]["value"]
            for e in events
            if e.get("kind") == "output" and e["payload"].get("name") == "proxy_result"
        )
    assert result["status"] == "succeeded"
    assert result["requestsSent"] == (0 if kind == "proxy_query" else 1)
    assert all(
        owner == run_id and payload["nodeId"] == "proxy" and payload["executionId"]
        for owner, payload in service.calls
    )
    assert service.released == [run_id]
    await manager.shutdown()


@pytest.mark.asyncio
async def test_concurrent_project_workers_keep_proxy_requests_owned(tmp_path):
    class ConcurrentProxyService(ProxyService):
        def __init__(self):
            super().__init__()
            self.entered = asyncio.Event()

        async def call(self, owner, payload):
            assert payload['method'] == 'query'
            self.calls.append((owner, payload))
            if len(self.calls) == 2:
                self.entered.set()
            await self.entered.wait()
            return {'status': 'succeeded', 'proxyId': owner}

    service = ConcurrentProxyService()
    manager = ProjectWorkflowWorkerManager(tmp_path, proxy_service=service, capacity=2)
    run_ids = [str(uuid4()), str(uuid4())]
    received = {owner: [] for owner in run_ids}

    async def run(owner):
        async def emit(event):
            received[owner].append(event)
        return await manager.run(
            run_id=owner, execution_generation=1,
            execution_plan={'document': document('proxy_query')},
            parameters={}, variables={}, browser={}, executable=None, on_event=emit,
        )

    try:
        async with asyncio.timeout(45):
            outcomes = await asyncio.gather(*(run(owner) for owner in run_ids))
        assert all(outcome.status == 'succeeded' for outcome in outcomes)
        for owner in run_ids:
            output = next(event['payload']['value'] for event in received[owner]
                          if event.get('kind') == 'output' and event['payload'].get('name') == 'proxy_result')
            assert output['proxyId'] == owner
        assert set(service.released) == set(run_ids)
    finally:
        await manager.shutdown()
