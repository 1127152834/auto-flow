"""Remediation M3 R3-06: pooled workers serve consecutive runs and are never reused unsafely."""

from __future__ import annotations

import asyncio
import itertools
from typing import Any
from uuid import uuid4

import pytest

from autoflow.infrastructure.process import project_workflow_worker as manager_module
from autoflow.infrastructure.process.project_workflow_worker import ProjectWorkflowWorkerManager


def _plan(count: int = 3, *, wait: str | None = None) -> dict[str, Any]:
    nodes = [{"id": f"s{index}", "data": {"moduleType": "set_variable", "variableName": f"v{index}", "variableValue": str(index)}} for index in range(count)]
    if wait:
        nodes.append({"id": "wait", "data": {"moduleType": "wait", "waitType": "time", "duration": wait}})
    edges = [{"id": f"e{index}", "source": a["id"], "target": b["id"]} for index, (a, b) in enumerate(itertools.pairwise(nodes))]
    content = {"nodes": nodes, "edges": edges, "variables": []}
    return {
        "orderedNodeIds": [node["id"] for node in nodes],
        "nodes": [{"nodeId": node["id"], "moduleType": node["data"]["moduleType"], "data": node["data"]} for node in nodes],
        "document": content,
    }


async def _run(manager, key, plan=None, run_id=None):
    events: list[dict[str, Any]] = []

    async def on_event(event):
        events.append(event)

    async def on_events(batch):
        events.extend(batch)

    outcome = await manager.run(
        run_id=run_id or str(uuid4()), execution_generation=1, execution_plan=plan or _plan(), parameters={}, variables={},
        browser={}, executable=None, on_event=on_event, on_events=on_events, session_key=key,
    )
    return outcome, events


def _idle_pids(manager) -> list[int]:
    return [worker.process.pid for items in manager._idle.values() for worker in items]


@pytest.mark.asyncio
async def test_consecutive_runs_share_one_process_and_keep_their_own_events(tmp_path):
    manager = ProjectWorkflowWorkerManager(tmp_path / "worker", start_timeout=30, capacity=2)
    try:
        first, events = await _run(manager, "a")
        assert first.status == "succeeded" and first.reusable
        (pid,) = _idle_pids(manager)
        second, second_events = await _run(manager, "a")
        assert second.status == "succeeded"
        assert _idle_pids(manager) == [pid]
        assert {event["runId"] for event in events}.isdisjoint({event["runId"] for event in second_events})
        assert manager._idle["a"][0].runs == 2
    finally:
        await manager.shutdown()
    assert _idle_pids(manager) == []


@pytest.mark.asyncio
async def test_another_identity_takes_the_idle_slot_instead_of_waiting(tmp_path):
    manager = ProjectWorkflowWorkerManager(tmp_path / "worker", start_timeout=30, capacity=1)
    try:
        await _run(manager, "a")
        (old,) = _idle_pids(manager)
        outcome, _events = await _run(manager, "b")
        assert outcome.status == "succeeded"
        assert list(manager._idle) == ["a", "b"] and manager._idle["a"] == []
        assert _idle_pids(manager) != [old]
        outcome, _events = await _run(manager, None)  # an unpooled run also gets the slot
        assert outcome.status == "succeeded" and _idle_pids(manager) == []
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_a_stopped_run_never_returns_its_process_to_the_pool(tmp_path):
    manager = ProjectWorkflowWorkerManager(tmp_path / "worker", start_timeout=30, capacity=1)
    run_id = str(uuid4())
    try:
        running = asyncio.create_task(_run(manager, "a", _plan(1, wait="30"), run_id))
        while not (run_id in manager._workers and manager._workers[run_id].ready):
            await asyncio.sleep(0.05)
        await manager.stop(run_id)
        outcome, _events = await running
        assert outcome.status == "cancelled"
        assert _idle_pids(manager) == [] and manager._workers == {}
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_a_worker_retires_after_its_run_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(manager_module, "POOL_MAX_RUNS", 2)
    manager = ProjectWorkflowWorkerManager(tmp_path / "worker", start_timeout=30, capacity=1)
    try:
        await _run(manager, "a")
        (pid,) = _idle_pids(manager)
        worker = manager._idle["a"][0]
        outcome, _events = await _run(manager, "a")
        assert outcome.status == "succeeded"
        assert _idle_pids(manager) == [] and worker.process.returncode == 0
        await _run(manager, "a")
        assert _idle_pids(manager) != [pid]
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_a_revoked_run_kills_its_pooled_process(tmp_path):
    manager = ProjectWorkflowWorkerManager(tmp_path / "worker", start_timeout=30, capacity=1)
    run_id = str(uuid4())
    try:
        await _run(manager, "a")
        (pid,) = _idle_pids(manager)
        running = asyncio.create_task(_run(manager, "a", _plan(1, wait="30"), run_id))
        while not (run_id in manager._workers and manager._workers[run_id].ready):
            await asyncio.sleep(0.05)
        process = manager._workers[run_id].process
        assert process.pid == pid  # the revoked run was on the reused process
        await manager.force_stop(run_id)
        await asyncio.gather(running, return_exceptions=True)
        assert process.returncode is not None
        assert _idle_pids(manager) == [] and manager._workers == {}
    finally:
        await manager.shutdown()
