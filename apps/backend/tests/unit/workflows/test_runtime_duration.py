from __future__ import annotations

import asyncio
from threading import Event

import pytest

from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_worker import _WorkerDebugController


def node(node_id, module_type):
    return {"id": node_id, "data": {"moduleType": module_type}}


class Sink:
    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(dict(event))

    async def pause(self):
        async with asyncio.timeout(1):
            while True:
                pause = next(
                    (e for e in self.events if e["type"] == "execution:paused"), None
                )
                if pause:
                    return pause
                await asyncio.sleep(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("success", [True, False])
async def test_duration_measures_action_after_real_debug_pause(monkeypatch, success):
    now = [0.0]
    monkeypatch.setattr(
        "autoflow.application.workflows.runtime.perf_counter", lambda: now[0]
    )
    debug = _WorkerDebugController(Event(), step_mode=True, breakpoints=set())
    sink = Sink()

    class Action(ModuleExecutor):
        module_type = "set_variable"

        async def execute(self, _config, _context):
            now[0] += 0.125
            return ModuleResult(
                success=success, error=None if success else "failure", duration=999
            )

    registry = ExecutorRegistry()
    registry.register(Action)
    task = asyncio.create_task(
        WorkflowRuntime(registry).execute(
            {"nodes": [node("action", "set_variable")], "edges": []},
            ExecutionContext(debug=debug, events=sink),
        )
    )
    try:
        pause = await sink.pause()
        now[0] += 100
        assert debug.apply(
            {
                "type": "debug_resume",
                "pauseId": pause["pauseId"],
                "controlRevision": pause["controlRevision"],
            }
        )
        result = await task
        assert result.success is success
        completed = next(
            e for e in sink.events if e["type"] == "execution:node_complete"
        )
        assert completed["duration"] == pytest.approx(125)
        if not success:
            assert result.node_result.duration == pytest.approx(125)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("pause_child", [True, False])
async def test_real_nested_runtime_excludes_its_wait_but_not_independent_branch_pause(
    monkeypatch, pause_child
):
    now = [0.0]
    monkeypatch.setattr(
        "autoflow.application.workflows.runtime.perf_counter", lambda: now[0]
    )
    sink = Sink()
    debug = _WorkerDebugController(
        Event(), step_mode=False, breakpoints={"child" if pause_child else "sibling"}
    )
    child_started = asyncio.Event()
    child_release = asyncio.Event()
    registry = ExecutorRegistry()

    class Child(ModuleExecutor):
        module_type = "set_variable"

        async def execute(self, _config, _context):
            child_started.set()
            await child_release.wait()
            now[0] += 2
            return ModuleResult(success=True)

    class Nested(ModuleExecutor):
        module_type = "run_workflow_file"

        async def execute(self, _config, _context):
            result = await WorkflowRuntime(registry).execute(
                {"nodes": [node("child", "set_variable")], "edges": []},
                ExecutionContext(debug=debug, events=sink),
            )
            return ModuleResult(success=result.success)

    registry.register(Child)
    registry.register(Nested)
    parent = asyncio.create_task(
        WorkflowRuntime(registry).execute(
            {"nodes": [node("parent", "run_workflow_file")], "edges": []},
            ExecutionContext(debug=debug, events=sink),
        )
    )
    sibling = None
    try:
        if not pause_child:
            await asyncio.wait_for(child_started.wait(), 1)
            sibling = asyncio.create_task(
                debug.before_node(
                    ExecutionContext(events=sink), node_id="sibling", label="sibling"
                )
            )
        pause = await sink.pause()
        now[0] += 8
        assert debug.apply(
            {
                "type": "debug_resume",
                "pauseId": pause["pauseId"],
                "controlRevision": pause["controlRevision"],
            }
        )
        child_release.set()
        assert (await parent).success
        if sibling:
            await sibling
        completed = {
            e["nodeId"]: e["duration"]
            for e in sink.events
            if e["type"] == "execution:node_complete"
        }
        assert completed == pytest.approx(
            {
                "child": 2000 if pause_child else 10000,
                "parent": 2000 if pause_child else 10000,
            }
        )
    finally:
        tasks = [parent] + ([sibling] if sibling else [])
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_raised_or_cancelled_action_does_not_fabricate_completion(failure):
    sink = Sink()

    class Action(ModuleExecutor):
        module_type = "set_variable"

        async def execute(self, _config, _context):
            raise failure("aborted")

    registry = ExecutorRegistry()
    registry.register(Action)
    with pytest.raises(failure):
        await WorkflowRuntime(registry).execute(
            {"nodes": [node("action", "set_variable")], "edges": []},
            ExecutionContext(events=sink),
        )
    assert not any(e["type"] == "execution:node_complete" for e in sink.events)


@pytest.mark.asyncio
async def test_worker_non_waiting_nested_call_does_not_deduct_background_pause(
    monkeypatch,
):
    import io

    from autoflow.providers.browser.workflow_worker import (
        _WorkerCommandBus,
        _WorkerNestedWorkflows,
    )

    now = [0.0]
    monkeypatch.setattr(
        "autoflow.application.workflows.runtime.perf_counter", lambda: now[0]
    )
    stopped = Event()
    debug = _WorkerDebugController(stopped, step_mode=False, breakpoints={"background"})

    class BoundSink(Sink):
        def for_context(self, _context):
            return self

    sink = BoundSink()
    registry = ExecutorRegistry()
    context = ExecutionContext(debug=debug, events=sink)
    bus = _WorkerCommandBus(
        asyncio.get_running_loop(),
        stopped,
        io.StringIO(),
        {"runId": "duration", "workflowId": "duration"},
    )
    nested = _WorkerNestedWorkflows(
        {
            "child": {
                "id": "child",
                "name": "child",
                "nodes": [node("background", "set_variable")],
                "edges": [],
            }
        },
        registry=registry,
        parent=context,
        sink=sink,
        command_bus=bus,
    )

    class Background(ModuleExecutor):
        module_type = "set_variable"

        async def execute(self, _config, _context):
            return ModuleResult(success=True)

    class Parent(ModuleExecutor):
        module_type = "run_workflow_file"

        async def execute(self, _config, _context):
            assert (
                await nested.run_workflow("child", variables={}, wait_complete=False)
            ).success
            pause = await sink.pause()
            now[0] += 8  # Parent continues its own work while background is paused.
            assert debug.apply(
                {
                    "type": "debug_resume",
                    "pauseId": pause["pauseId"],
                    "controlRevision": pause["controlRevision"],
                }
            )
            await asyncio.sleep(0)
            now[0] += 2
            return ModuleResult(success=True)

    registry.register(Background)
    registry.register(Parent)
    try:
        assert (
            await WorkflowRuntime(registry).execute(
                {"nodes": [node("parent", "run_workflow_file")], "edges": []}, context
            )
        ).success
        await nested.drain()
        completed = next(
            e
            for e in sink.events
            if e["type"] == "execution:node_complete" and e["nodeId"] == "parent"
        )
        assert completed["duration"] == pytest.approx(10000)
    finally:
        stopped.set()
        debug.close()
        bus.close()
