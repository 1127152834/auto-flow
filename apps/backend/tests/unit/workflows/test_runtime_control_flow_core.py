from __future__ import annotations

import asyncio
from typing import Any

import pytest

from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext


def _executor(
    module_type: str,
    execute: Any,
) -> type[ModuleExecutor]:
    return type(
        f"{module_type.title()}Executor",
        (ModuleExecutor,),
        {
            "__module__": f"tests.control.{module_type}",
            "module_type": property(lambda self: module_type),
            "execute": execute,
        },
    )


def _node(
    node_id: str, module_type: str, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "moduleNode",
        "data": {"moduleType": module_type, "config": config or {}},
    }


def _edge(
    edge_id: str,
    source: str,
    target: str,
    handle: str | None = None,
) -> dict[str, Any]:
    edge: dict[str, Any] = {"id": edge_id, "source": source, "target": target}
    if handle is not None:
        edge["sourceHandle"] = handle
    return edge


@pytest.mark.asyncio
async def test_condition_executes_only_selected_branch_and_then_join_once() -> None:
    calls: list[str] = []

    async def condition(
        _self: ModuleExecutor, _config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        calls.append("condition")
        return ModuleResult(success=True, branch="true", data=True)

    async def probe(
        _self: ModuleExecutor, config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        calls.append(config["name"])
        return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(_executor("condition", condition))
    registry.register(_executor("set_variable", probe))
    document = {
        "nodes": [
            _node("condition", "condition"),
            _node("yes", "set_variable", {"name": "yes"}),
            _node("no", "set_variable", {"name": "no"}),
            _node("join", "set_variable", {"name": "join"}),
        ],
        "edges": [
            _edge("true", "condition", "yes", "true"),
            _edge("false", "condition", "no", "false"),
            _edge("yes-join", "yes", "join"),
            _edge("no-join", "no", "join"),
        ],
    }

    result = await WorkflowRuntime(registry).execute(document, ExecutionContext())

    assert result.success is True
    assert calls == ["condition", "yes", "join"]
    assert result.executed_node_ids == ("condition", "yes", "join")


@pytest.mark.asyncio
async def test_parallel_fork_runs_concurrently_and_waits_before_join() -> None:
    calls: list[str] = []
    both_started = asyncio.Event()
    started: set[str] = set()

    async def start(
        _self: ModuleExecutor, _config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        calls.append("start")
        return ModuleResult(success=True)

    async def branch(
        _self: ModuleExecutor, config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        name = config["name"]
        calls.append(f"{name}:start")
        started.add(name)
        if started == {"left", "right"}:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.5)
        calls.append(f"{name}:end")
        return ModuleResult(success=True)

    async def join(
        _self: ModuleExecutor, _config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        assert {"left:end", "right:end"}.issubset(calls)
        calls.append("join")
        return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(_executor("set_variable", start))
    registry.register(_executor("string_concat", branch))
    registry.register(_executor("list_length", join))
    document = {
        "nodes": [
            _node("start", "set_variable"),
            _node("left", "string_concat", {"name": "left"}),
            _node("right", "string_concat", {"name": "right"}),
            _node("join", "list_length"),
        ],
        "edges": [
            _edge("left", "start", "left"),
            _edge("right", "start", "right"),
            _edge("left-join", "left", "join"),
            _edge("right-join", "right", "join"),
        ],
    }

    result = await WorkflowRuntime(registry).execute(document, ExecutionContext())

    assert result.success is True
    assert calls[-1] == "join"
    assert result.executed_node_ids.count("join") == 1


@pytest.mark.asyncio
async def test_parallel_root_does_not_inherit_sibling_loop_context() -> None:
    events: list[dict[str, Any]] = []
    loop_started = asyncio.Event()

    class Sink:
        async def publish(self, event: dict[str, Any]) -> None:
            events.append(event)

    async def loop(
        _self: ModuleExecutor, _config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        state = {"type": "count", "count": 1, "current_index": 0}
        context.loop_stack.append(state)
        loop_started.set()
        return ModuleResult(success=True, data=state)

    async def wait_for_loop(
        _self: ModuleExecutor, _config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        await loop_started.wait()
        return ModuleResult(success=True)

    async def success(
        _self: ModuleExecutor, _config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(_executor("loop", loop))
    registry.register(_executor("set_variable", success))
    registry.register(_executor("string_concat", wait_for_loop))
    document = {
        "nodes": [
            _node("loop", "loop"),
            _node("body", "set_variable"),
            _node("parallel", "string_concat"),
            _node("parallel-tail", "set_variable"),
        ],
        "edges": [
            _edge("body", "loop", "body", "loop"),
            _edge("parallel-tail", "parallel", "parallel-tail"),
        ],
    }

    result = await WorkflowRuntime(registry).execute(
        document, ExecutionContext(events=Sink())
    )

    assert result.success is True
    tail_start = next(
        event
        for event in events
        if event["type"] == "execution:node_start"
        and event["nodeId"] == "parallel-tail"
    )
    assert tail_start["executionContext"]["loops"] == []


@pytest.mark.asyncio
async def test_error_edge_handles_failure_without_running_normal_successor() -> None:
    calls: list[str] = []

    async def fail(
        _self: ModuleExecutor, _config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        calls.append("fail")
        return ModuleResult(success=False, error="expected")

    async def probe(
        _self: ModuleExecutor, config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        calls.append(config["name"])
        return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(_executor("assert_checkpoint", fail))
    registry.register(_executor("set_variable", probe))
    document = {
        "nodes": [
            _node("fail", "assert_checkpoint"),
            _node("normal", "set_variable", {"name": "normal"}),
            _node("recover", "set_variable", {"name": "recover"}),
            _node("after", "set_variable", {"name": "after"}),
        ],
        "edges": [
            _edge("normal", "fail", "normal"),
            _edge("error", "fail", "recover", "error"),
            _edge("after", "recover", "after"),
        ],
    }

    result = await WorkflowRuntime(registry).execute(document, ExecutionContext())

    # 冻结版会执行 error 分支完成恢复动作，但失败节点仍计入整次运行结果。
    assert result.success is False
    assert result.failed_node_id == "fail"
    assert calls == ["fail", "recover", "after"]


@pytest.mark.asyncio
async def test_count_loop_repeats_body_and_runs_done_branch_once() -> None:
    calls: list[int] = []
    events: list[dict[str, Any]] = []

    class Sink:
        async def publish(self, event: dict[str, Any]) -> None:
            events.append(event)

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
        calls.append(context.variables["index"])
        return ModuleResult(success=True)

    async def done(
        _self: ModuleExecutor, _config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        context.set_variable("done", True)
        return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(_executor("loop", loop))
    registry.register(_executor("set_variable", body))
    registry.register(_executor("increment_decrement", done))
    document = {
        "nodes": [
            _node("loop", "loop"),
            _node("body", "set_variable"),
            _node("done", "increment_decrement"),
        ],
        "edges": [
            _edge("body", "loop", "body", "loop"),
            _edge("done", "loop", "done", "done"),
        ],
    }
    context = ExecutionContext(events=Sink())

    result = await WorkflowRuntime(registry).execute(document, context)

    assert result.success is True
    assert calls == [0, 1, 2]
    assert context.variables["done"] is True
    assert context.loop_stack == []
    assert result.executed_node_ids == ("loop", "body", "body", "body", "done")
    body_starts = [
        event
        for event in events
        if event["type"] == "execution:node_start" and event["nodeId"] == "body"
    ]
    assert len({event["executionId"] for event in body_starts}) == 3
    assert [event["executionContext"]["loops"] for event in body_starts] == [
        [
            {
                "nodeId": "loop",
                "type": "count",
                "currentIndex": index,
                "iteration": index + 1,
            }
        ]
        for index in range(3)
    ]


@pytest.mark.asyncio
async def test_parallel_nodes_keep_their_event_bound_artifact_writer() -> None:
    writes: list[tuple[str, str]] = []
    both_started = asyncio.Event()
    started: set[str] = set()

    class Writer:
        def __init__(self, node_id: str) -> None:
            self.node_id = node_id

        async def write_bytes(
            self, *, name: str, content: bytes, mime_type: str
        ) -> str:
            del content, mime_type
            writes.append((self.node_id, name))
            return name

    class Sink:
        async def publish(self, event: dict[str, Any]) -> None:
            if event["type"] == "execution:node_start":
                context.artifacts = Writer(event["nodeId"])  # type: ignore[assignment]
                await asyncio.sleep(0)

    async def start(
        _self: ModuleExecutor, _config: dict[str, Any], _context: ExecutionContext
    ) -> ModuleResult:
        return ModuleResult(success=True)

    async def branch(
        _self: ModuleExecutor, config: dict[str, Any], node_context: ExecutionContext
    ) -> ModuleResult:
        name = config["name"]
        started.add(name)
        if started == {"left", "right"}:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.5)
        assert node_context.node_artifacts is not None
        await node_context.node_artifacts.write_bytes(
            name=f"{name}.txt", content=name.encode(), mime_type="text/plain"
        )
        return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(_executor("set_variable", start))
    registry.register(_executor("string_concat", branch))
    document = {
        "nodes": [
            _node("start", "set_variable"),
            _node("left", "string_concat", {"name": "left"}),
            _node("right", "string_concat", {"name": "right"}),
        ],
        "edges": [
            _edge("left", "start", "left"),
            _edge("right", "start", "right"),
        ],
    }
    context = ExecutionContext(events=Sink())

    result = await WorkflowRuntime(registry).execute(document, context)

    assert result.success is True
    assert set(writes) == {("left", "left.txt"), ("right", "right.txt")}
