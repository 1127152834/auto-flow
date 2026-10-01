"""Remediation M1 R1-05: nested execution follows the right document's error rule."""

from __future__ import annotations

from typing import Any

import pytest

from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.domain.workflows.error_semantics import ERROR_SEMANTICS_V2
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_worker import (
    _WorkerCanvasSubflows,
    _WorkerNestedWorkflows,
)


class Sink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def for_context(self, _context: ExecutionContext) -> Sink:
        return self

    async def publish(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))


def _registry() -> ExecutorRegistry:
    class Probe(ModuleExecutor):
        module_type = "set_variable"

        async def execute(self, config: dict[str, Any], _context: ExecutionContext) -> ModuleResult:
            if config.get("action") == "fail":
                return ModuleResult(success=False, error="probe failure")
            return ModuleResult(success=True)

    class Handler(ModuleExecutor):
        module_type = "string_concat"

        async def execute(self, _config: dict[str, Any], _context: ExecutionContext) -> ModuleResult:
            return ModuleResult(success=True)

    registry = ExecutorRegistry()
    registry.register(Probe)
    registry.register(Handler)
    return registry


def _node(identity: str, kind: str, **config: Any) -> dict[str, Any]:
    return {"id": identity, "type": "moduleNode", "data": {"moduleType": kind, "config": config}}


def _caught_failure(**top_level: Any) -> dict[str, Any]:
    return {
        "id": "child",
        "name": "child",
        "nodes": [_node("fails", "set_variable", action="fail"), _node("handler", "string_concat")],
        "edges": [{"id": "e", "source": "fails", "target": "handler", "sourceHandle": "error"}],
        **top_level,
    }


def _context(semantics: str) -> ExecutionContext:
    context = ExecutionContext()
    context.error_semantics = semantics  # what WorkflowRuntime.execute sets for the running caller
    return context


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("caller", "saved_marker", "expected_success"),
    [
        (ERROR_SEMANTICS_V2, {}, False),  # a saved legacy workflow is not upgraded by its v2 caller
        ("webrpa", {"executionSemantics": ERROR_SEMANTICS_V2}, True),  # a saved v2 workflow keeps its rule
        (ERROR_SEMANTICS_V2, {"executionSemantics": ERROR_SEMANTICS_V2}, True),
        ("webrpa", {}, False),
    ],
)
async def test_saved_workflow_uses_its_own_version_not_the_callers(caller, saved_marker, expected_success):
    context = _context(caller)
    nested = _WorkerNestedWorkflows(
        {"child": _caught_failure(**saved_marker)},
        registry=_registry(),
        parent=context,
        sink=Sink(),
        command_bus=None,
    )
    result = await nested.run_workflow("child", variables={}, wait_complete=True)
    assert result.success is expected_success


def _canvas_document(**top_level: Any) -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "head", "type": "moduleNode", "data": {"moduleType": "subflow_header", "subflowName": "sub"}},
            _node("fails", "set_variable", action="fail"),
            _node("handler", "string_concat"),
        ],
        "edges": [
            {"id": "e1", "source": "head", "target": "fails"},
            {"id": "e2", "source": "fails", "target": "handler", "sourceHandle": "error"},
        ],
        **top_level,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("caller", "document_marker", "expected_success"),
    [
        (ERROR_SEMANTICS_V2, {}, True),  # the subset document lost no rule: the caller's rule applies
        (ERROR_SEMANTICS_V2, {"executionSemantics": ERROR_SEMANTICS_V2}, True),
        ("webrpa", {}, False),
    ],
)
async def test_canvas_subflow_follows_the_calling_document(caller, document_marker, expected_success):
    context = _context(caller)
    canvas = _WorkerCanvasSubflows(
        _canvas_document(**document_marker), registry=_registry(), parent=context, sink=Sink()
    )
    result = await canvas.run_subflow(group_id="head", name="sub", inputs={})
    assert result.success is expected_success
