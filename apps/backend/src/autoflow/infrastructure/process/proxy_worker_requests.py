"""Nonblocking, run-scoped proxy RPC on the existing private worker pipe."""

from __future__ import annotations

import asyncio
from typing import Any


class ProxyWorkerRequests:
    def __init__(
        self,
        service,
        owner: str,
        document: dict[str, Any],
        send,
        alive,
        generation: int = 0,
    ):
        self.service, self.owner, self.send, self.alive = service, owner, send, alive
        self.generation = generation
        self.nodes: dict[str, set[str]] = {}
        self.visits: set[tuple[str, str]] = set()
        self.tasks: dict[str, asyncio.Task] = {}
        self.pending_payloads: dict[str, dict] = {}
        self.receipts: dict[str, tuple[dict, dict]] = {}
        self._scan(document)

    def _scan(self, value):
        if isinstance(value, dict):
            for node in value.get("nodes", []):
                if isinstance(node, dict):
                    data = node.get("data", node)
                    kind = data.get("moduleType", node.get("moduleType"))
                    if isinstance(kind, str):
                        self.nodes.setdefault(
                            str(node.get("id", node.get("nodeId"))), set()
                        ).add(kind)
            for child in value.values():
                if isinstance(child, (dict, list)):
                    self._scan(child)
        elif isinstance(value, list):
            for child in value:
                self._scan(child)

    def observe(self, event):
        node = event.get("nodeId")
        visit = event.get("executionId", event.get("nodeVisitId"))
        if not isinstance(node, str) or not isinstance(visit, str):
            return
        if event.get("type") == "execution:node_start" or (
            event.get("kind") == "nodeAttempt"
            and event.get("payload", {}).get("status") == "started"
        ):
            self.visits.add((node, visit))
        elif event.get("type") == "execution:node_complete" or (
            event.get("kind") == "nodeAttempt"
            and event.get("payload", {}).get("status") in {"succeeded", "failed"}
        ):
            self.visits.discard((node, visit))
            for request_id, payload in tuple(self.pending_payloads.items()):
                if (payload.get("nodeId"), payload.get("executionId")) == (node, visit):
                    self.tasks[request_id].cancel()

    def receive(self, message):
        request_id, payload = message.get("requestId"), message.get("payload")
        if (
            message.get("runId") != self.owner
            or not isinstance(request_id, str)
            or not request_id
            or not isinstance(payload, dict)
            or not self.alive()
            or self.generation
            and message.get("executionGeneration") != self.generation
        ):
            raise ValueError("Proxy worker request ownership mismatch")
        node, visit = payload.get("nodeId"), payload.get("executionId")
        kind = {
            "change_ip": "proxy_change_ip",
            "relocate": "proxy_change_location",
            "query": "proxy_query",
        }.get(payload.get("action"))
        if (node, visit) not in self.visits or (
            payload.get("method") != "finish"
            and kind not in self.nodes.get(node, set())
        ):
            raise ValueError("Proxy request does not belong to an executing proxy node")
        if request_id in self.tasks:
            if self.pending_payloads[request_id] != payload:
                raise ValueError("Proxy request id reused with different payload")
            return
        previous = self.receipts.get(request_id)
        if previous is not None and previous[0] != payload:
            raise ValueError("Proxy request id reused with different payload")
        task = asyncio.create_task(self._serve(request_id, payload))
        self.tasks[request_id] = task
        self.pending_payloads[request_id] = dict(payload)
        task.add_done_callback(
            lambda _task: (
                self.tasks.pop(request_id, None),
                self.pending_payloads.pop(request_id, None),
            )
        )

    async def _serve(self, request_id, payload):
        def active():
            return (
                self.alive()
                and (payload.get("nodeId"), payload.get("executionId")) in self.visits
            )

        try:
            receipt = self.receipts.get(request_id)
            if receipt:
                response = receipt[1]
            else:
                value = await self.service.call(
                    self.owner,
                    {**payload, "generation": self.generation, "_alive": active},
                )
                response = {
                    "type": "proxy:result",
                    "runId": self.owner,
                    "requestId": request_id,
                    "value": value,
                }
                if self.generation:
                    response.update(
                        protocolVersion=1, executionGeneration=self.generation
                    )
                self.receipts[request_id] = (dict(payload), response)
            if active():
                await self.send(response)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 -- no provider diagnostics or credentials cross the pipe.
            if active():
                try:
                    await self.send(
                        {
                            "type": "proxy:result",
                            "runId": self.owner,
                            "requestId": request_id,
                            "protocolError": True,
                            **(
                                {
                                    "protocolVersion": 1,
                                    "executionGeneration": self.generation,
                                }
                                if self.generation
                                else {}
                            ),
                        }
                    )
                except Exception:  # noqa: BLE001,S110 -- worker shutdown also cancels its pending futures.
                    pass

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.service.release(self.owner)
