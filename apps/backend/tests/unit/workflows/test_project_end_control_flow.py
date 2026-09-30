"""Actual graph/nesting implementations; only host acceptance is substituted."""
import pytest

from autoflow.providers.browser.project_graph import ProjectGraphExecutor


def node(identity, kind, config=None):
    return {"id": identity, "type": "moduleNode", "data": {"moduleType": kind, "config": config or {}}}


def edge(source, target, handle=None):
    return {"id": f"{source}-{target}", "source": source, "target": target, **({"sourceHandle": handle} if handle else {})}


def end_plan(kind, end_type="project_end"):
    ending = node("end", end_type, {"retainEnvironment": False})
    after = node("after", "set_variable", {"variableName": "forbidden", "variableValue": "yes"})
    body = node("body", "set_variable", {"variableName": "visited", "variableValue": "yes"})
    inner = {"id": "child", "name": "child", "nodes": [body, ending, after], "edges": [edge("body", "end"), edge("end", "after")]}
    if kind == "loop":
        return {"document": {"nodes": [node("loop", "loop", {"loopCount": 3}), body, ending, after], "edges": [edge("loop", "body", "loop"), edge("body", "end"), edge("loop", "after", "done")]}}
    if kind == "workflow":
        return {"document": {"nodes": [node("call", "run_workflow_file", {"workflowFile": "child"}), after], "edges": [edge("call", "after")]}, "workflowDependencies": {"child": inner}}
    if kind == "module":
        return {"document": {"nodes": [node("call", "custom_module", {"customModuleId": "child"}), after], "edges": [edge("call", "after")]}, "customModuleDependencies": {"child": {"name": "child", "workflow": inner}}}
    return {"document": {"nodes": [node("header", "subflow_header"), body, ending, node("inner-after", "set_variable", {"variableName": "forbidden", "variableValue": "yes"}), node("call", "subflow", {"subflowGroupId": "header"}), after], "edges": [edge("header", "body"), edge("body", "end"), edge("end", "inner-after"), edge("call", "after")]}}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["loop", "workflow", "module", "canvas"])
async def test_project_end_stops_entire_run(kind):
    visits = []
    async def emit(event, identity, _visit, _payload):
        if event == "nodeAttempt" and _payload.get("status") == "started":
            visits.append(identity)
    async def accept(_node_id, _visit, _operation, _arguments):
        return {"result": {"endOperationId": "accepted"}}
    graph = ProjectGraphExecutor(None, {}, emit, lambda: False, capability=accept)
    result = await graph.run(end_plan(kind))
    assert result["status"] == "succeeded", result
    assert visits.count("end") == 1, visits
    assert visits.count("body") == 1, visits
    assert "after" not in visits and "inner-after" not in visits, visits


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["workflow", "module", "canvas"])
async def test_ordinary_stop_stays_local_to_nested_workflow(kind):
    visits = []
    async def emit(event, identity, _visit, _payload):
        if event == "nodeAttempt" and _payload.get("status") == "started":
            visits.append(identity)
    graph = ProjectGraphExecutor(None, {}, emit, lambda: False)
    assert (await graph.run(end_plan(kind, "stop_workflow")))["status"] == "succeeded"
    assert visits.count("after") == 1
