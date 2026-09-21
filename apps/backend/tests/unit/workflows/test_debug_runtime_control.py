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
            pauses = [
                event for event in sink.events if event["type"] == "execution:paused"
            ]
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
async def test_run_to_target_executes_real_prefix_and_pauses_once_before_target() -> (
    None
):
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
            {
                "id": name,
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {"name": name}},
            }
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
    assert (
        len([event for event in sink.events if event["type"] == "execution:paused"])
        == 1
    )


@pytest.mark.asyncio
async def test_run_to_target_follows_the_selected_condition_branch() -> None:
    calls: list[str] = []

    async def condition(
        _self: ModuleExecutor, _config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        calls.append("condition")
        return ModuleResult(success=True, branch="true")

    async def probe(
        _self: ModuleExecutor, config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        calls.append(str(config["name"]))
        return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(
        type(
            "ConditionExecutor",
            (ModuleExecutor,),
            {"module_type": property(lambda _self: "condition"), "execute": condition},
        )
    )
    registry.register(
        type(
            "ProbeExecutor",
            (ModuleExecutor,),
            {"module_type": property(lambda _self: "set_variable"), "execute": probe},
        )
    )
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(),
        Event(),
        io.StringIO(),
        {
            "runId": "run-condition-target",
            "workflowId": "workflow-condition-target",
            "debug": True,
            "runToNodeId": "selected",
        },
    )
    sink = _Sink()
    document = {
        "nodes": [
            {
                "id": "condition",
                "type": "moduleNode",
                "data": {"moduleType": "condition", "config": {}},
            },
            {
                "id": "selected",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {"name": "selected"}},
            },
            {
                "id": "skipped",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {"name": "skipped"}},
            },
            {
                "id": "join",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {"name": "join"}},
            },
        ],
        "edges": [
            {
                "id": "true",
                "source": "condition",
                "target": "selected",
                "sourceHandle": "true",
            },
            {
                "id": "false",
                "source": "condition",
                "target": "skipped",
                "sourceHandle": "false",
            },
            {"id": "selected-join", "source": "selected", "target": "join"},
            {"id": "skipped-join", "source": "skipped", "target": "join"},
        ],
    }
    task = asyncio.create_task(
        WorkflowRuntime(registry).execute(
            document, ExecutionContext(events=sink, debug=command_bus.debug)
        )
    )

    pause = await _wait_for_pauses(sink, 1)
    assert pause["node_id"] == "selected"
    assert calls == ["condition"]
    command_bus.receive(
        {
            "type": "debug_resume",
            "commandId": "resume-condition-target",
            "pauseId": pause["pauseId"],
            "controlRevision": pause["controlRevision"],
        }
    )

    assert (await asyncio.wait_for(task, timeout=1)).success is True
    assert calls == ["condition", "selected", "join"]


@pytest.mark.asyncio
async def test_run_to_loop_body_pauses_only_on_the_first_iteration() -> None:
    calls: list[int] = []

    async def loop(
        _self: ModuleExecutor, _config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        state = {
            "type": "count",
            "count": 3,
            "current_index": 0,
            "index_variable": "index",
        }
        context.loop_stack.append(state)
        context.set_variable("index", 0)
        return ModuleResult(success=True, data=state)

    async def body(
        _self: ModuleExecutor, _config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        calls.append(int(context.variables["index"]))
        return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(
        type(
            "LoopExecutor",
            (ModuleExecutor,),
            {"module_type": property(lambda _self: "loop"), "execute": loop},
        )
    )
    registry.register(
        type(
            "BodyExecutor",
            (ModuleExecutor,),
            {"module_type": property(lambda _self: "set_variable"), "execute": body},
        )
    )
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(),
        Event(),
        io.StringIO(),
        {
            "runId": "run-loop-target",
            "workflowId": "workflow-loop-target",
            "debug": True,
            "runToNodeId": "body",
        },
    )
    sink = _Sink()
    document = {
        "nodes": [
            {
                "id": "loop",
                "type": "moduleNode",
                "data": {"moduleType": "loop", "config": {}},
            },
            {
                "id": "body",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {}},
            },
        ],
        "edges": [
            {"id": "body", "source": "loop", "target": "body", "sourceHandle": "loop"}
        ],
    }
    task = asyncio.create_task(
        WorkflowRuntime(registry).execute(
            document, ExecutionContext(events=sink, debug=command_bus.debug)
        )
    )

    pause = await _wait_for_pauses(sink, 1)
    assert pause["node_id"] == "body"
    assert pause["variables"]["index"] == 0
    assert pause["variableMeta"]["index"] == {"scope": "loop", "readOnly": True}
    assert pause["executionContext"] == {
        "scopes": [],
        "loops": [
            {
                "nodeId": "loop",
                "type": "count",
                "currentIndex": 0,
                "iteration": 1,
            }
        ],
    }
    command_bus.receive(
        {
            "type": "debug_resume",
            "commandId": "resume-loop-target",
            "pauseId": pause["pauseId"],
            "controlRevision": pause["controlRevision"],
        }
    )

    assert (await asyncio.wait_for(task, timeout=1)).success is True
    assert calls == [0, 1, 2]
    assert (
        len([event for event in sink.events if event["type"] == "execution:paused"])
        == 1
    )


@pytest.mark.asyncio
async def test_parallel_branch_cannot_dispatch_more_nodes_while_target_is_paused() -> (
    None
):
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
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(),
        Event(),
        io.StringIO(),
        {
            "runId": "run-parallel-target",
            "workflowId": "workflow-parallel-target",
            "debug": True,
            "runToNodeId": "left",
        },
    )
    sink = _Sink()
    document = {
        "nodes": [
            {
                "id": name,
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {"name": name}},
            }
            for name in ("start", "left", "right", "right-tail")
        ],
        "edges": [
            {"id": "left", "source": "start", "target": "left"},
            {"id": "right", "source": "start", "target": "right"},
            {"id": "right-tail", "source": "right", "target": "right-tail"},
        ],
    }
    task = asyncio.create_task(
        WorkflowRuntime(registry).execute(
            document, ExecutionContext(events=sink, debug=command_bus.debug)
        )
    )

    pause = await _wait_for_pauses(sink, 1)
    await asyncio.sleep(0)
    assert pause["node_id"] == "left"
    assert calls == ["start"]
    command_bus.receive(
        {
            "type": "debug_resume",
            "commandId": "resume-parallel-target",
            "pauseId": pause["pauseId"],
            "controlRevision": pause["controlRevision"],
        }
    )

    assert (await asyncio.wait_for(task, timeout=1)).success is True
    assert set(calls) == {"start", "left", "right", "right-tail"}


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
            {
                "id": "first",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {}},
            },
            {
                "id": "second",
                "type": "moduleNode",
                "data": {"moduleType": "set_variable", "config": {}},
            },
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
