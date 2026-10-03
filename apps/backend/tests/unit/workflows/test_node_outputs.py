"""Remediation M2 R2-29 / AC2-17: stable node output references."""

import pytest

from autoflow.application.workflows.config_schema_snapshot import READ_KEYS
from autoflow.domain.workflows.outputs import (
    declared_outputs,
    node_output_names,
    reference_issues,
)
from autoflow.providers.browser.project_graph import ProjectGraphExecutor


def node(identity, kind, **config):
    return {"id": identity, "data": {"moduleType": kind, **config}}


def test_outputs_are_the_variable_fields_the_executor_reads():
    assert [item["key"] for item in declared_outputs("set_variable", READ_KEYS["set_variable"])] == ["variableName"]
    loop = declared_outputs("foreach", READ_KEYS["foreach"])
    assert {item["key"]: item["availability"] for item in loop} == {"itemVariable": "loopBody", "indexVariable": "loopBody"}
    assert all(item["sensitive"] for item in declared_outputs("web_cookie", READ_KEYS["web_cookie"]))


def test_references_must_name_an_existing_output():
    nodes = [node("a", "set_variable", variableName="x"), node("b", "set_variable", variableName="y", variableValue="{node.a.variableName} {node.gone.variableName} {node.a.resultVariable}")]
    assert node_output_names(nodes) == {"a": {"variableName": "x"}, "b": {"variableName": "y"}}
    assert [message for _, message in reference_issues(nodes)] == [
        "引用的节点已删除：{node.gone.variableName}",
        "引用的节点输出没有设置变量名：{node.a.resultVariable}",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("variable", ["first", "renamed_later"])
async def test_a_stable_reference_survives_renaming_the_variable_and_the_node(variable):
    async def emit(*_event):
        return None

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    document = {"nodes": [
        node("source", "set_variable", label="任意名称", variableName=variable, variableValue="hello"),
        node("use", "set_variable", variableName="copy", variableValue="{node.source.variableName}!"),
    ], "edges": [{"id": "e", "source": "source", "target": "use"}]}
    assert (await executor.run({"document": document}))["status"] == "succeeded"
    assert executor.context.variables["copy"] == "hello!"


@pytest.mark.asyncio
async def test_a_reference_to_a_deleted_node_stops_before_running():
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    document = {"nodes": [node("use", "set_variable", variableName="copy", variableValue="{node.gone.variableName}")], "edges": []}
    result = await executor.run({"document": document})
    assert result["status"] == "failed"
    assert result["error"] == {"code": "NODE_OUTPUT_REFERENCE_INVALID", "message": "引用的节点已删除：{node.gone.variableName}", "nodeId": "use"}
