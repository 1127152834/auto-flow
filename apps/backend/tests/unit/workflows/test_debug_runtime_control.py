from __future__ import annotations

import asyncio
import io
from threading import Event
from typing import Any

import pytest
from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_worker import _WorkerCommandBus


class _Sink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def publish(self, event: dict[str, Any]) -> None:
        self.events.append(event)


async def _wait_for_pauses(sink: _Sink, count: int) -> dict[str, Any]:
    async with asyncio.timeout(1):
        while True:
            pauses = [event for event in sink.events if event["type"] == "execution:paused"]
            if len(pauses) >= count:
                return pauses[-1]
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_step_releases_one_dispatch_then_pauses_before_next_node() -> None:
    calls: list[str] = []

    class ProbeExecutor(ModuleExecutor):
        module_type = "set_variable"

        async def execute(
            self, config: dict[str, Any], _context: ExecutionContext
        ) -> ModuleResult:
            calls.append(str(config["name"]))
            return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(ProbeExecutor)
    output = io.StringIO()
    stopped = Event()
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(),
        stopped,
        output,
        {
            "runId": "run-debug",
            "workflowId": "workflow-debug",
            "debug": True,
            "stepMode": True,
        },
    )
    sink = _Sink()
    context = ExecutionContext(events=sink, debug=command_bus.debug)
    document = {
        "nodes": [
            {
                "id": "first",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {"name": "first"}},
            },
            {
                "id": "second",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {"name": "second"}},
            },
        ],
        "edges": [{"id": "edge", "source": "first", "target": "second"}],
    }

    task = asyncio.create_task(WorkflowRuntime(registry).execute(document, context))
    first_pause = await _wait_for_pauses(sink, 1)
    assert first_pause["node_id"] == "first"
    assert calls == []

    command_bus.receive(
        {
            "type": "debug_step",
            "commandId": "step-1",
            "pauseId": first_pause["pauseId"],
            "controlRevision": first_pause["controlRevision"],
        }
    )
    second_pause = await _wait_for_pauses(sink, 2)
    assert second_pause["node_id"] == "second"
    assert calls == ["first"]

    command_bus.receive(
        {
            "type": "debug_resume",
            "commandId": "resume-1",
            "pauseId": second_pause["pauseId"],
            "controlRevision": second_pause["controlRevision"],
        }
    )
    result = await asyncio.wait_for(task, timeout=1)

    assert result.success is True
    assert calls == ["first", "second"]
    assert output.getvalue().count('"type":"execution:command_applied"') == 2


@pytest.mark.asyncio
async def test_stop_while_paused_does_not_start_the_pending_node() -> None:
    calls: list[str] = []

    class ProbeExecutor(ModuleExecutor):
        module_type = "set_variable"

        async def execute(
            self, _config: dict[str, Any], _context: ExecutionContext
        ) -> ModuleResult:
            calls.append("started")
            return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(ProbeExecutor)
    stopped = Event()
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(),
        stopped,
        io.StringIO(),
        {
            "runId": "run-stop",
            "workflowId": "workflow-stop",
            "debug": True,
            "stepMode": True,
        },
    )
    sink = _Sink()
    context = ExecutionContext(events=sink, debug=command_bus.debug)
    document = {
        "nodes": [
            {
                "id": "pending",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {}},
            }
        ],
        "edges": [],
    }
    task = asyncio.create_task(WorkflowRuntime(registry).execute(document, context))
    await _wait_for_pauses(sink, 1)

    stopped.set()
    command_bus.close()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == []


@pytest.mark.asyncio
async def test_variable_batch_rejects_loop_local_without_partial_changes() -> None:
    class ProbeExecutor(ModuleExecutor):
        module_type = "set_variable"

        async def execute(
            self, _config: dict[str, Any], _context: ExecutionContext
        ) -> ModuleResult:
            return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(ProbeExecutor)
    output = io.StringIO()
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(),
        Event(),
        output,
        {
            "runId": "run-loop",
            "workflowId": "workflow-loop",
            "debug": True,
            "stepMode": True,
        },
    )
    sink = _Sink()
    context = ExecutionContext(
        variables={"count": 1, "index": 0},
        loop_stack=[{"index_variable": "index"}],
        events=sink,
        debug=command_bus.debug,
    )
    document = {
        "nodes": [
            {
                "id": "pending",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {}},
            }
        ],
        "edges": [],
    }
    task = asyncio.create_task(WorkflowRuntime(registry).execute(document, context))
    pause = await _wait_for_pauses(sink, 1)

    command_bus.receive(
        {
            "type": "debug_variables",
            "commandId": "variables-1",
            "pauseId": pause["pauseId"],
            "controlRevision": pause["controlRevision"],
            "changes": [
                {"name": "count", "value": 9},
                {"name": "index", "value": 2},
            ],
        }
    )
    async with asyncio.timeout(1):
        while "execution:command_rejected" not in output.getvalue():
            await asyncio.sleep(0)
    assert context.variables == {"count": 1, "index": 0}

    command_bus.receive(
        {
            "type": "debug_resume",
            "commandId": "resume-loop",
            "pauseId": pause["pauseId"],
            "controlRevision": pause["controlRevision"],
        }
    )
    assert (await task).success is True


@pytest.mark.asyncio
async def test_runtime_starts_at_requested_top_level_node() -> None:
    calls: list[str] = []

    class ProbeExecutor(ModuleExecutor):
        module_type = "set_variable"

        async def execute(
            self, config: dict[str, Any], _context: ExecutionContext
        ) -> ModuleResult:
            calls.append(str(config["name"]))
            return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(ProbeExecutor)
    document = {
        "nodes": [
            {
                "id": "first",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {"name": "first"}},
            },
            {
                "id": "second",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {"name": "second"}},
            },
        ],
        "edges": [{"id": "edge", "source": "first", "target": "second"}],
    }

    result = await WorkflowRuntime(registry).execute(
        document, ExecutionContext(), start_node_id="second"
    )

    assert result.success is True
    assert calls == ["second"]


@pytest.mark.asyncio
async def test_run_to_target_executes_real_prefix_and_pauses_once_before_target() -> None:
    calls: list[str] = []

    class ProbeExecutor(ModuleExecutor):
        module_type = "set_variable"

        async def execute(
            self, config: dict[str, Any], _context: ExecutionContext
        ) -> ModuleResult:
            calls.append(str(config["name"]))
            return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(ProbeExecutor)
    output = io.StringIO()
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(),
        Event(),
        output,
        {
            "runId": "run-to-target",
            "workflowId": "workflow-run-to-target",
            "debug": True,
            "runToNodeId": "second",
        },
    )
    sink = _Sink()
    context = ExecutionContext(events=sink, debug=command_bus.debug)
    document = {
        "nodes": [
            {"id": name, "type": "moduleNode", "data": {"moduleType": "set_variable", "config": {"name": name}}}
            for name in ("first", "second", "third")
        ],
        "edges": [
            {"id": "first-second", "source": "first", "target": "second"},
            {"id": "second-third", "source": "second", "target": "third"},
        ],
    }

    task = asyncio.create_task(WorkflowRuntime(registry).execute(document, context))
    pause = await _wait_for_pauses(sink, 1)
    assert pause["node_id"] == "second"
    assert pause["reason"] == "target"
    assert calls == ["first"]

    command_bus.receive(
        {
            "type": "debug_resume",
            "commandId": "resume-target",
            "pauseId": pause["pauseId"],
            "controlRevision": pause["controlRevision"],
        }
    )
    result = await asyncio.wait_for(task, timeout=1)
    assert result.success is True
    assert calls == ["first", "second", "third"]
    assert len([event for event in sink.events if event["type"] == "execution:paused"]) == 1


@pytest.mark.asyncio
async def test_breakpoints_can_be_replaced_while_paused() -> None:
    class ProbeExecutor(ModuleExecutor):
        module_type = "set_variable"

        async def execute(
            self, _config: dict[str, Any], _context: ExecutionContext
        ) -> ModuleResult:
            return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(ProbeExecutor)
    output = io.StringIO()
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(),
        Event(),
        output,
        {
            "runId": "run-breakpoints",
            "workflowId": "workflow-breakpoints",
            "debug": True,
            "breakpoints": ["first"],
        },
    )
    sink = _Sink()
    context = ExecutionContext(events=sink, debug=command_bus.debug)
    document = {
        "nodes": [
            {"id": "first", "type": "moduleNode", "data": {"moduleType": "set_variable", "config": {}}},
            {"id": "second", "type": "moduleNode", "data": {"moduleType": "set_variable", "config": {}}},
        ],
        "edges": [{"id": "edge", "source": "first", "target": "second"}],
    }
    task = asyncio.create_task(WorkflowRuntime(registry).execute(document, context))
    first = await _wait_for_pauses(sink, 1)
    command_bus.receive(
        {
            "type": "debug_breakpoints",
            "commandId": "breakpoints-1",
            "breakpoints": ["second"],
        }
    )
    async with asyncio.timeout(1):
        while "breakpoints-1" not in output.getvalue():
            await asyncio.sleep(0)
    command_bus.receive(
        {
            "type": "debug_resume",
            "commandId": "resume-first",
            "pauseId": first["pauseId"],
            "controlRevision": first["controlRevision"],
        }
    )
    second = await _wait_for_pauses(sink, 2)
    assert second["node_id"] == "second"
    command_bus.receive(
        {
            "type": "debug_resume",
            "commandId": "resume-second",
            "pauseId": second["pauseId"],
            "controlRevision": second["controlRevision"],
        }
    )
    assert (await task).success is True
