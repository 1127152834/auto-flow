"""Remediation M1 R1-05: a failure caught by an error branch is not the run's failure (v2 only)."""

from __future__ import annotations

from typing import Any

import pytest

from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.error_semantics import (
    ERROR_SEMANTICS_V2,
    ERROR_SEMANTICS_WEBRPA,
    document_error_semantics,
)
from autoflow.domain.workflows.execution import ExecutionContext


def _executor(module_type: str, execute: Any) -> type[ModuleExecutor]:
    return type(
        f"{module_type.title().replace('_', '')}ProbeExecutor",
        (ModuleExecutor,),
        {
            "__module__": f"tests.handled.{module_type}",
            "module_type": property(lambda self: module_type),
            "execute": execute,
        },
    )


def _node(node_id: str, module_type: str, **config: Any) -> dict[str, Any]:
    return {"id": node_id, "type": "moduleNode", "data": {"moduleType": module_type, "config": config}}


def _edge(source: str, target: str, handle: str | None = None) -> dict[str, Any]:
    edge: dict[str, Any] = {"id": f"{source}-{target}-{handle or 'plain'}", "source": source, "target": target}
    if handle is not None:
        edge["sourceHandle"] = handle
    return edge


def _runtime(trace: list[str]) -> WorkflowRuntime:
    async def probe(_self: ModuleExecutor, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        trace.append(context.current_node_id or "?")
        if config.get("action") == "fail":
            return ModuleResult(success=False, error="probe failure")
        return ModuleResult(success=True)

    async def loop(_self: ModuleExecutor, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        trace.append(context.current_node_id or "?")
        state = {"type": "count", "count": int(config["count"]), "current_index": 0, "index_variable": "index"}
        context.loop_stack.append(state)
        context.set_variable("index", 0)
        return ModuleResult(success=True, data=state)

    registry = ExecutorRegistry()
    registry.register(_executor("set_variable", probe))
    registry.register(_executor("string_concat", probe))
    registry.register(_executor("loop", loop))
    return WorkflowRuntime(registry)


def _caught_failure(**top_level: Any) -> dict[str, Any]:
    return {
        "nodes": [_node("fails", "set_variable", action="fail"), _node("handler", "string_concat")],
        "edges": [_edge("fails", "handler", "error")],
        **top_level,
    }


@pytest.mark.asyncio
async def test_v2_failure_caught_by_an_error_branch_is_handled_not_failed() -> None:
    trace: list[str] = []
    result = await _runtime(trace).execute(
        _caught_failure(executionSemantics=ERROR_SEMANTICS_V2), ExecutionContext()
    )
    assert trace == ["fails", "handler"]
    assert result.success is True
    assert result.failed_node_id is None
    assert result.node_result is None
    assert result.handled_failure_node_ids == ("fails",)


@pytest.mark.asyncio
@pytest.mark.parametrize("marker", [{}, {"executionSemantics": "webrpa"}, {"executionSemantics": "future-v9"}, {"executionSemantics": None}])
async def test_legacy_or_unknown_semantics_still_fail_after_the_error_branch(marker: dict[str, Any]) -> None:
    trace: list[str] = []
    result = await _runtime(trace).execute(_caught_failure(**marker), ExecutionContext())
    assert trace == ["fails", "handler"]
    assert result.success is False
    assert result.failed_node_id == "fails"
    assert result.handled_failure_node_ids == ()


@pytest.mark.asyncio
async def test_v2_failure_without_an_error_branch_still_fails() -> None:
    trace: list[str] = []
    document = {"nodes": [_node("fails", "set_variable", action="fail")], "edges": [], "executionSemantics": ERROR_SEMANTICS_V2}
    result = await _runtime(trace).execute(document, ExecutionContext())
    assert result.success is False
    assert result.failed_node_id == "fails"
    assert result.handled_failure_node_ids == ()


@pytest.mark.asyncio
async def test_v2_failure_inside_the_error_handler_fails_the_run() -> None:
    trace: list[str] = []
    document = {
        "nodes": [_node("fails", "set_variable", action="fail"), _node("handler", "string_concat", action="fail")],
        "edges": [_edge("fails", "handler", "error")],
        "executionSemantics": ERROR_SEMANTICS_V2,
    }
    result = await _runtime(trace).execute(document, ExecutionContext())
    assert trace == ["fails", "handler"]
    assert result.success is False
    assert result.failed_node_id == "handler"
    assert result.handled_failure_node_ids == ("fails",)


@pytest.mark.asyncio
async def test_v2_handled_failures_in_a_loop_are_listed_once() -> None:
    trace: list[str] = []
    document = {
        "nodes": [
            _node("loop", "loop", count=3),
            _node("fails", "set_variable", action="fail"),
            _node("handler", "string_concat"),
        ],
        "edges": [_edge("loop", "fails", "loop"), _edge("fails", "handler", "error")],
        "executionSemantics": ERROR_SEMANTICS_V2,
    }
    result = await _runtime(trace).execute(document, ExecutionContext())
    assert trace.count("fails") == 3
    assert result.success is True
    assert result.handled_failure_node_ids == ("fails",)


def _fork(branch_a_fails: bool, handled: bool, **top_level: Any) -> dict[str, Any]:
    nodes = [
        _node("start", "set_variable", parallel={"joinNodeId": "join", "outputs": {}}),
        _node("a", "string_concat", **({"action": "fail"} if branch_a_fails else {})),
        _node("b", "string_concat"),
        _node("join", "set_variable"),
    ]
    edges = [_edge("start", "a"), _edge("start", "b"), _edge("b", "join"), _edge("a", "join")]
    if handled:
        nodes.append(_node("a-handler", "string_concat"))
        edges += [_edge("a", "a-handler", "error"), _edge("a-handler", "join")]
    return {"nodes": nodes, "edges": edges, **top_level}


@pytest.mark.asyncio
async def test_v2_structured_fork_branch_inherits_semantics_and_reports_handled_ids() -> None:
    trace: list[str] = []
    result = await _runtime(trace).execute(
        _fork(True, True, executionSemantics=ERROR_SEMANTICS_V2), ExecutionContext()
    )
    assert result.success is True
    assert "join" in trace
    assert result.handled_failure_node_ids == ("a",)


@pytest.mark.asyncio
async def test_legacy_structured_fork_still_fails_after_a_branch_error_handler() -> None:
    trace: list[str] = []
    result = await _runtime(trace).execute(_fork(True, True), ExecutionContext())
    assert result.success is False
    assert "join" not in trace


@pytest.mark.asyncio
async def test_v2_fork_branch_failure_without_handler_fails_the_whole_run() -> None:
    trace: list[str] = []
    result = await _runtime(trace).execute(
        _fork(True, False, executionSemantics=ERROR_SEMANTICS_V2), ExecutionContext()
    )
    assert result.success is False
    assert result.handled_failure_node_ids == ()


@pytest.mark.asyncio
async def test_explicit_semantics_overrides_the_document_marker() -> None:
    trace: list[str] = []
    result = await _runtime(trace).execute(
        _caught_failure(executionSemantics=ERROR_SEMANTICS_V2),
        ExecutionContext(),
        error_semantics=ERROR_SEMANTICS_WEBRPA,
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_a_reused_context_does_not_leak_semantics_between_runs() -> None:
    context = ExecutionContext()
    first = await _runtime([]).execute(_caught_failure(executionSemantics=ERROR_SEMANTICS_V2), context)
    second = await _runtime([]).execute(_caught_failure(), context)
    assert first.success is True
    assert second.success is False


def test_document_error_semantics_only_accepts_the_exact_v2_marker() -> None:
    assert document_error_semantics({"executionSemantics": "autoflow-v2"}) == ERROR_SEMANTICS_V2
    for value in (None, "", "webrpa", "AUTOFLOW-V2", 2, ["autoflow-v2"]):
        assert document_error_semantics({"executionSemantics": value}) == ERROR_SEMANTICS_WEBRPA
    assert document_error_semantics({}) == ERROR_SEMANTICS_WEBRPA
    assert document_error_semantics("not a mapping") == ERROR_SEMANTICS_WEBRPA  # type: ignore[arg-type]
