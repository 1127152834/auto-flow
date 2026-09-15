from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import autoflow.application.workflows.runtime as runtime_module
from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_REPOSITORY = REPOSITORY_ROOT / "reference" / "WebRPA"
FROZEN_EXECUTOR = FROZEN_REPOSITORY / "backend/app/services/workflow_executor.py"
FROZEN_PARSER = FROZEN_REPOSITORY / "backend/app/services/workflow_parser.py"
FROZEN_COMMIT = "5ccb900e8dcf1530aae66f676d87593c416c7ebb"


@dataclass(slots=True)
class ControlContext(ExecutionContext):
    should_break: bool = False
    should_continue: bool = False


@dataclass(slots=True)
class ProbeState:
    trace: list[str] = field(default_factory=list)
    blocking_started: asyncio.Event = field(default_factory=asyncio.Event)


class Cancellation:
    cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError


def node(node_id: str, module_type: str, **config: Any) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "moduleNode",
        "data": {"moduleType": module_type, "config": config},
    }


def edge(source: str, target: str, source_handle: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "id": f"edge-{source}-{target}-{source_handle or 'plain'}",
        "source": source,
        "target": target,
    }
    if source_handle is not None:
        value["sourceHandle"] = source_handle
    return value


def document(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "id": "b3-control-flow",
        "name": "B3 control flow contract",
        "nodes": nodes,
        "edges": edges,
        "variables": [],
    }


def executor_type(module_type: str, state: ProbeState) -> type[ModuleExecutor]:
    async def execute(
        self: ModuleExecutor, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        state.trace.append(context.current_node_id or module_type)
        action = config.get("action", "success")
        if action == "branch":
            return ModuleResult(success=True, branch=str(config["branch"]))
        if action == "fail":
            return ModuleResult(success=False, error="probe failure")
        if action == "block":
            state.blocking_started.set()
            await asyncio.Event().wait()
        if module_type == "loop":
            loop_state: dict[str, Any] = {
                "type": "count",
                "count": int(config["count"]),
                "current_index": 0,
                "index_variable": str(config.get("indexVariable", "index")),
            }
            context.loop_stack.append(loop_state)
            context.set_variable(loop_state["index_variable"], 0)
            return ModuleResult(success=True, data=loop_state)
        if module_type == "break_loop":
            if not context.loop_stack:
                return ModuleResult(success=False, error="当前不在循环中")
            assert isinstance(context, ControlContext)
            context.should_break = True
        if module_type == "continue_loop":
            if not context.loop_stack:
                return ModuleResult(success=False, error="当前不在循环中")
            assert isinstance(context, ControlContext)
            context.should_continue = True
        return ModuleResult(success=True)

    return type(
        f"{module_type.title().replace('_', '')}ProbeExecutor",
        (ModuleExecutor,),
        {
            "__module__": __name__,
            "module_type": property(lambda self: module_type),
            "execute": execute,
        },
    )


def runtime_with_probes() -> tuple[WorkflowRuntime, ProbeState]:
    state = ProbeState()
    registry = ExecutorRegistry()
    for module_type in (
        "set_variable",
        "condition",
        "loop",
        "break_loop",
        "continue_loop",
    ):
        registry.register(executor_type(module_type, state))
    return WorkflowRuntime(registry), state


@pytest.mark.asyncio
@pytest.mark.parametrize("branch", ["true", "false"])
async def test_condition_dispatches_only_the_selected_frozen_branch(
    branch: str,
) -> None:
    runtime, state = runtime_with_probes()
    result = await runtime.execute(
        document(
            [
                node("condition", "condition", action="branch", branch=branch),
                node("yes", "set_variable"),
                node("no", "set_variable"),
            ],
            [
                edge("condition", "yes", "true"),
                edge("condition", "no", "false"),
            ],
        ),
        ControlContext(),
    )

    assert result.success is True
    assert state.trace == ["condition", "yes" if branch == "true" else "no"]


@pytest.mark.asyncio
async def test_failure_dispatches_error_edge_before_runtime_reports_failure() -> None:
    runtime, state = runtime_with_probes()
    result = await runtime.execute(
        document(
            [
                node("fails", "set_variable", action="fail"),
                node("handler", "set_variable"),
            ],
            [edge("fails", "handler", "error")],
        ),
        ControlContext(),
    )

    assert state.trace == ["fails", "handler"]
    assert result.success is False
    assert result.failed_node_id == "fails"


@pytest.mark.asyncio
async def test_diamond_join_executes_once_after_both_predecessors() -> None:
    runtime, state = runtime_with_probes()
    result = await runtime.execute(
        document(
            [
                node("start", "set_variable"),
                node("left", "set_variable"),
                node("right", "set_variable"),
                node("join", "set_variable"),
            ],
            [
                edge("start", "left"),
                edge("start", "right"),
                edge("left", "join"),
                edge("right", "join"),
            ],
        ),
        ControlContext(),
    )

    assert result.success is True
    assert state.trace == ["start", "left", "right", "join"]
    assert state.trace.count("join") == 1


@pytest.mark.asyncio
async def test_count_loop_reschedules_body_and_then_dispatches_done_branch() -> None:
    runtime, state = runtime_with_probes()
    result = await runtime.execute(
        document(
            [
                node("loop", "loop", count=3),
                node("body", "set_variable"),
                node("done", "set_variable"),
            ],
            [edge("loop", "body", "loop"), edge("loop", "done", "done")],
        ),
        ControlContext(),
    )

    assert result.success is True
    assert state.trace == ["loop", "body", "body", "body", "done"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("control_type", "expected_trace"),
    [
        (
            "break_loop",
            ["outer", "inner", "control", "tail", "inner", "control", "tail", "done"],
        ),
        (
            "continue_loop",
            [
                "outer",
                "inner",
                "control",
                "control",
                "tail",
                "inner",
                "control",
                "control",
                "tail",
                "done",
            ],
        ),
    ],
)
async def test_break_and_continue_target_the_nearest_nested_loop(
    control_type: str, expected_trace: list[str]
) -> None:
    runtime, state = runtime_with_probes()
    result = await runtime.execute(
        document(
            [
                node("outer", "loop", count=2, indexVariable="outer_index"),
                node("inner", "loop", count=2, indexVariable="inner_index"),
                node("control", control_type),
                node("skipped", "set_variable"),
                node("tail", "set_variable"),
                node("done", "set_variable"),
            ],
            [
                edge("outer", "inner", "loop"),
                edge("outer", "done", "done"),
                edge("inner", "control", "loop"),
                edge("inner", "tail", "done"),
                edge("control", "skipped"),
            ],
        ),
        ControlContext(),
    )

    assert result.success is True
    assert state.trace == expected_trace
    assert "skipped" not in state.trace


@pytest.mark.asyncio
async def test_cancellation_interrupts_active_dispatch_and_blocks_successors() -> None:
    runtime, state = runtime_with_probes()
    cancellation = Cancellation()
    execution = asyncio.create_task(
        runtime.execute(
            document(
                [
                    node("blocking", "set_variable", action="block"),
                    node("after", "set_variable"),
                ],
                [edge("blocking", "after")],
            ),
            ControlContext(cancellation=cancellation),
        )
    )
    await asyncio.wait_for(state.blocking_started.wait(), timeout=1)

    cancellation.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(execution, timeout=1)
    assert state.trace == ["blocking"]


@pytest.mark.asyncio
async def test_total_dispatch_limit_stops_a_branch_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch_limit = 6
    monkeypatch.setattr(
        runtime_module, "MAX_NODE_DISPATCHES", dispatch_limit, raising=False
    )
    runtime, state = runtime_with_probes()
    result = await runtime.execute(
        document(
            [
                node("entry", "set_variable"),
                node("spin", "condition", action="branch", branch="true"),
            ],
            [edge("entry", "spin"), edge("spin", "spin", "true")],
        ),
        ControlContext(),
    )

    assert result.success is False
    assert len(state.trace) <= dispatch_limit
    assert state.trace.count("spin") >= 2
    assert result.node_result is not None
    assert "调度" in (result.node_result.error or "")
    assert "上限" in (result.node_result.error or "")


def test_contract_is_pinned_to_the_declared_frozen_control_flow_sources() -> None:
    actual_commit = subprocess.run(
        ["git", "-C", str(FROZEN_REPOSITORY), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    executor_source = FROZEN_EXECUTOR.read_text(encoding="utf-8")
    parser_source = FROZEN_PARSER.read_text(encoding="utf-8")

    assert actual_commit == FROZEN_COMMIT
    for marker in (
        "if result and result.branch:",
        "error_nodes = self.graph.get_error_nodes(node_id)",
        "prev_nodes = self.graph.get_join_prev_nodes(next_id)",
        "await self._handle_loop(node, body_nodes, done_nodes)",
        "if self.context.should_break:",
        "if self.context.should_continue:",
    ):
        assert marker in executor_source
    assert "if edge.sourceHandle == 'error':" in parser_source
    assert "graph.condition_branches" in parser_source
    assert "graph.loop_branches" in parser_source
