"""Remediation M3 R3-04 / AC3-08: process-event batches never cost a state fact or a replay gate.

Each scenario runs the real worker process and kills it at one point of the exchange: a batch
before it is committed, a batch committed but not yet ACKed, the replay gate of a node that may
act outside the run, and the terminal flush. At most the last non-authoritative batch may be
lost; state events before it are complete and no event is committed twice.
"""

from __future__ import annotations

import itertools
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4

import pytest

from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.process import project_workflow_worker as manager_module
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)


class _Server:
    def __init__(self) -> None:
        hits = self.hits = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                hits.append(self.path)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')

            def log_message(self, *_args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/act"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _plan(url: str) -> dict[str, Any]:
    nodes = [{"id": f"s{index}", "data": {"moduleType": "set_variable", "variableName": f"v{index}", "variableValue": str(index)}} for index in range(10)]
    nodes.append({"id": "act", "data": {"moduleType": "api_request", "requestUrl": url, "requestMethod": "GET", "variableName": "response"}})
    nodes.append({"id": "after", "data": {"moduleType": "set_variable", "variableName": "done", "variableValue": "yes"}})
    edges = [{"id": f"e{index}", "source": a["id"], "target": b["id"]} for index, (a, b) in enumerate(itertools.pairwise(nodes))]
    content = {"nodes": nodes, "edges": edges, "variables": []}
    return {
        "orderedNodeIds": [node["id"] for node in nodes],
        "nodes": [{"nodeId": node["id"], "moduleType": node["data"]["moduleType"], "data": node["data"]} for node in nodes],
        "document": content,
    }


async def _run(tmp_path, url: str, kill_when, *, version: int = 2) -> tuple[list[dict[str, Any]], Any]:
    manager_module.WORKER_PROTOCOL_VERSION = version
    manager = ProjectWorkflowWorkerManager(tmp_path / "worker", start_timeout=30)
    run_id = str(uuid4())
    committed: list[dict[str, Any]] = []
    batches = []

    def kill() -> None:
        manager._workers[run_id].process.kill()

    async def on_event(event: dict[str, Any]) -> None:
        if kill_when("event", [event], before_commit=True):
            kill()
            raise WorkflowRuntimeError("TEST_KILLED", "killed before commit")
        committed.append(event)
        if kill_when("event", [event], before_commit=False):
            kill()

    async def on_events(events: list[dict[str, Any]]) -> None:
        batches.append(events)
        if kill_when("batch", events, before_commit=True):
            kill()
            raise WorkflowRuntimeError("TEST_KILLED", "killed before commit")
        committed.extend(events)
        if kill_when("batch", events, before_commit=False):
            kill()

    try:
        outcome = await manager.run(
            run_id=run_id, execution_generation=1, execution_plan=_plan(url), parameters={}, variables={},
            browser={}, executable=None, on_event=on_event, on_events=on_events,
        )
    except Exception as error:  # noqa: BLE001 -- a killed worker surfaces as a lost run
        outcome = error
    finally:
        manager_module.WORKER_PROTOCOL_VERSION = 2
        await manager.shutdown()
    return committed, outcome


def _started(event: dict[str, Any], node_id: str) -> bool:
    return event["kind"] == "nodeAttempt" and event["nodeId"] == node_id and event["payload"].get("status") == "started"


@pytest.fixture
def server():
    value = _Server()
    yield value
    value.close()


@pytest.mark.asyncio
async def test_v1_and_v2_commit_the_same_facts_in_the_same_order(tmp_path, server):
    never = lambda *_args, **_kwargs: False
    v1, outcome_v1 = await _run(tmp_path / "v1", server.url, never, version=1)
    v2, outcome_v2 = await _run(tmp_path / "v2", server.url, never, version=2)
    assert outcome_v1.status == outcome_v2.status == "succeeded"
    shape = lambda events: [(e["kind"], e["nodeId"], e["payload"].get("status")) for e in events]
    assert shape(v1) == shape(v2)
    assert len(server.hits) == 2


@pytest.mark.asyncio
async def test_the_replay_gate_of_an_external_action_flushes_everything_before_it(tmp_path, server):
    """Killed after committing the gate and before its ACK: the action never runs, nothing earlier is lost."""
    committed, _outcome = await _run(tmp_path, server.url, lambda kind, events, before_commit: not before_commit and any(_started(e, "act") for e in events))
    assert server.hits == []
    assert _started(committed[-1], "act")
    assert {e["nodeId"] for e in committed if e["kind"] == "nodeAttempt" and e["payload"].get("status") == "succeeded"} == {f"s{i}" for i in range(10)}


@pytest.mark.asyncio
@pytest.mark.parametrize("before_commit", [True, False])
async def test_a_killed_batch_is_all_or_nothing_and_never_doubled(tmp_path, server, before_commit):
    batches = []

    def kill_at_first_batch(kind, _events, before_commit: bool) -> bool:
        if kind != "batch":
            return False
        if before_commit:
            batches.append(1)
        return len(batches) == 1 and before_commit is kill_before_commit

    kill_before_commit = before_commit
    committed, _outcome = await _run(tmp_path, server.url, kill_at_first_batch)
    ids = [event["eventId"] for event in committed]
    assert len(ids) == len(set(ids))
    assert server.hits == []  # the gate after the lost batch is never reached
    if before_commit:
        assert committed == []
    else:
        assert committed and all(e["nodeId"].startswith("s") for e in committed)


@pytest.mark.asyncio
async def test_the_terminal_flush_can_only_lose_the_last_process_batch(tmp_path, server):
    def at_terminal(kind, events, before_commit: bool) -> bool:
        return kind == "batch" and before_commit and any(e["nodeId"] == "after" for e in events)

    committed, _outcome = await _run(tmp_path, server.url, at_terminal)
    assert len(server.hits) == 1
    act = [e["payload"].get("status") for e in committed if e["kind"] == "nodeAttempt" and e["nodeId"] == "act"]
    assert act == ["started", "succeeded"]  # state facts of the external action are complete
    assert not any(e["nodeId"] == "after" for e in committed)  # only the last process batch is lost
