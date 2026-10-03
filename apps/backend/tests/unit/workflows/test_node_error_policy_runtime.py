"""Remediation M2 R2-08/R2-09/R2-10: node error policies run, and never repeat external actions."""

from collections import defaultdict
from typing import Any

import pytest

from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext


class Probe:
    def __init__(self, failures: dict[str, int] | None = None):
        self.failures = dict(failures or {})
        self.calls: defaultdict[str, int] = defaultdict(int)
        self.trace: list[str] = []


def executor(module_type: str, probe: Probe) -> type[ModuleExecutor]:
    async def execute(self: ModuleExecutor, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        node_id = context.current_node_id or module_type
        probe.calls[node_id] += 1
        probe.trace.append(node_id)
        if probe.failures.get(node_id, 0) > 0:
            probe.failures[node_id] -= 1
            return ModuleResult(False, error=f"{node_id} failed")
        return ModuleResult(True)

    return type(f"{module_type}Probe", (ModuleExecutor,), {
        "__module__": __name__, "module_type": property(lambda self: module_type), "execute": execute,
    })


def run(nodes, edges, failures=None):
    probe = Probe(failures)
    registry = ExecutorRegistry()
    # set_variable is side-effect free; click_element may act outside the run.
    for module_type in ("set_variable", "click_element"):
        registry.register(executor(module_type, probe))
    document = {"id": "d", "name": "d", "variables": [], "nodes": nodes, "edges": edges}
    return probe, WorkflowRuntime(registry).execute(document, ExecutionContext())


def node(node_id, module_type="set_variable", policy=None):
    config: dict[str, Any] = {}
    if policy is not None:
        config["errorPolicy"] = {"version": 2, "backoff": {"kind": "fixed", "initialSeconds": 0, "maxSeconds": 0, "jitter": False},
                                 "retryOn": "any", "gotoNodeId": None, "onExhausted": "stop", "maxRetries": 0, **policy}
    return {"id": node_id, "type": "moduleNode", "data": {"moduleType": module_type, "config": config}}


def edge(source, target):
    return {"id": f"{source}-{target}", "source": source, "target": target}


@pytest.mark.asyncio
async def test_read_only_node_retries_until_it_succeeds():
    probe, execution = run([node("read", policy={"onError": "retry", "maxRetries": 2}), node("next")], [edge("read", "next")], {"read": 2})
    result = await execution
    assert result.success
    assert probe.calls["read"] == 3 and probe.calls["next"] == 1


@pytest.mark.asyncio
async def test_retries_are_bounded_and_then_follow_on_exhausted():
    probe, execution = run([node("read", policy={"onError": "retry", "maxRetries": 1, "onExhausted": "continue"}), node("next")], [edge("read", "next")], {"read": 5})
    result = await execution
    assert result.success, "continue after exhaustion hands the failure to the policy"
    assert probe.calls["read"] == 2 and probe.calls["next"] == 1


@pytest.mark.asyncio
async def test_a_node_that_may_act_outside_the_run_is_never_retried_automatically():
    probe, execution = run([node("submit", "click_element", policy={"onError": "retry", "maxRetries": 3})], [], {"submit": 1})
    result = await execution
    assert not result.success
    assert probe.calls["submit"] == 1


@pytest.mark.asyncio
async def test_continue_skips_the_failure_and_runs_the_successors():
    probe, execution = run([node("read", policy={"onError": "continue"}), node("next")], [edge("read", "next")], {"read": 1})
    result = await execution
    assert result.success and probe.calls["next"] == 1


@pytest.mark.asyncio
async def test_goto_back_over_read_only_nodes_reruns_them():
    nodes = [node("open"), node("read", policy={"onError": "goto", "gotoNodeId": "open", "maxRetries": 1})]
    probe, execution = run(nodes, [edge("open", "read")], {"read": 1})
    result = await execution
    assert result.success
    assert probe.trace == ["open", "read", "open", "read"]


@pytest.mark.asyncio
async def test_goto_back_across_a_side_effect_is_refused():
    nodes = [node("open"), node("submit", "click_element"), node("read", policy={"onError": "goto", "gotoNodeId": "open", "maxRetries": 1})]
    probe, execution = run(nodes, [edge("open", "submit"), edge("submit", "read")], {"read": 1})
    result = await execution
    assert not result.success
    assert probe.calls["submit"] == 1 and probe.calls["open"] == 1


@pytest.mark.asyncio
async def test_old_settings_stay_inert():
    old = {"id": "read", "type": "moduleNode", "data": {"moduleType": "set_variable", "config": {"retryCount": 3}}}
    probe, execution = run([old], [], {"read": 1})
    result = await execution
    assert not result.success and probe.calls["read"] == 1
