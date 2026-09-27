import asyncio

import pytest

from autoflow.infrastructure.process.proxy_worker_requests import ProxyWorkerRequests


@pytest.mark.asyncio
async def test_owned_requests_are_nonblocking_deduplicated_and_generation_bound():
    ready, release = asyncio.Event(), asyncio.Event()
    sent = []

    class Service:
        calls = 0
        released = False

        async def call(self, owner, payload):
            self.calls += 1
            ready.set()
            await release.wait()
            return {"status": "succeeded"}

        def release(self, owner):
            self.released = True

    async def send(message):
        sent.append(message)

    service = Service()
    broker = ProxyWorkerRequests(
        service,
        "run",
        {"nodes": [{"id": "n", "data": {"moduleType": "proxy_query"}}]},
        send,
        lambda: True,
        2,
    )
    broker.observe(
        {
            "kind": "nodeAttempt",
            "nodeId": "n",
            "nodeVisitId": "visit",
            "payload": {"status": "started"},
        }
    )
    message = {
        "runId": "run",
        "executionGeneration": 2,
        "requestId": "req",
        "payload": {
            "nodeId": "n",
            "executionId": "visit",
            "method": "query",
            "action": "query",
        },
    }
    broker.receive(message)
    await ready.wait()
    broker.receive(message)
    assert service.calls == 1 and not sent
    with pytest.raises(ValueError):
        broker.receive({**message, "executionGeneration": 1})
    with pytest.raises(ValueError):
        broker.receive(
            {**message, "payload": {**message["payload"], "operationId": "different"}}
        )
    release.set()
    await asyncio.gather(*list(broker.tasks.values()))
    broker.receive(message)
    await asyncio.gather(*list(broker.tasks.values()))
    assert len(sent) == 2 and service.calls == 1
    assert sent[0]["executionGeneration"] == 2
    await broker.close()
    assert service.released


@pytest.mark.asyncio
async def test_completed_visit_revokes_permission_and_cancels_pending_request():
    entered = asyncio.Event()
    captured = []

    class Service:
        async def call(self, owner, payload):
            captured.append(payload["_alive"])
            entered.set()
            await asyncio.Event().wait()

        def release(self, owner):
            pass

    async def send(message):
        pytest.fail("completed visit must not receive a late result")

    broker = ProxyWorkerRequests(
        Service(),
        "run",
        {"nodes": [{"id": "n", "data": {"moduleType": "proxy_query"}}]},
        send,
        lambda: True,
    )
    broker.observe({"type": "execution:node_start", "nodeId": "n", "executionId": "v"})
    broker.receive(
        {
            "runId": "run",
            "requestId": "r",
            "payload": {
                "nodeId": "n",
                "executionId": "v",
                "method": "query",
                "action": "query",
            },
        }
    )
    await entered.wait()
    assert captured[0]() is True
    tasks = list(broker.tasks.values())
    broker.observe(
        {"type": "execution:node_complete", "nodeId": "n", "executionId": "v"}
    )
    assert captured[0]() is False
    await asyncio.gather(*tasks, return_exceptions=True)
    assert all(task.cancelled() for task in tasks)
    await broker.close()
