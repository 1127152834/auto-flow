from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.custom_module import CustomModuleExecutor
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.executors.subflow import SubflowExecutor
from autoflow.application.workflows.executors.workflow_chain import (
    RunWorkflowFileExecutor,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.document import WorkflowDraft
from autoflow.domain.workflows.execution import (
    CustomModuleResult,
    ExecutionContext,
    NestedWorkflowResult,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b3_dependency_harness.py")


def frozen_result(case: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS), case],
        check=True,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        (
            "subflow:missing",
            {
                "success": False,
                "message": "",
                "error": "未选择子流程",
                "data": None,
                "variables": {"kept": 1},
            },
        ),
        (
            "subflow:name",
            {
                "success": True,
                "message": "调用子流程 [登录]",
                "error": None,
                "data": {"subflow_group_id": "", "subflow_name": "登录"},
                "variables": {"kept": 1},
            },
        ),
        (
            "subflow:id",
            {
                "success": True,
                "message": "调用子流程 [group-1]",
                "error": None,
                "data": {"subflow_group_id": "group-1", "subflow_name": ""},
                "variables": {"kept": 1},
            },
        ),
        (
            "subflow:both",
            {
                "success": True,
                "message": "调用子流程 [登录]",
                "error": None,
                "data": {"subflow_group_id": "group-1", "subflow_name": "登录"},
                "variables": {"kept": 1},
            },
        ),
    ],
)
def test_frozen_subflow_executor_marker_contract(
    case: str, expected: dict[str, Any]
) -> None:
    assert frozen_result(case) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "config"),
    [
        ("missing", {}),
        ("name", {"subflowName": "登录"}),
        ("id", {"subflowGroupId": "group-1"}),
        ("both", {"subflowName": "登录", "subflowGroupId": "group-1"}),
    ],
)
async def test_autoflow_subflow_marker_matches_frozen_source(
    case: str, config: dict[str, Any]
) -> None:
    context = ExecutionContext(variables={"kept": 1})
    result = await SubflowExecutor().execute(config, context)

    assert {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
        "variables": context.variables,
    } == frozen_result(f"subflow:{case}")


def test_frozen_custom_module_executor_prepares_runtime_payload() -> None:
    assert frozen_result("custom:ready") == {
        "success": True,
        "message": "自定义模块 '格式化器' 准备执行",
        "error": None,
        "data": {
            "is_custom_module": True,
            "module_id": "ready",
            "module_name": "格式化器",
            "workflow_definition": {"nodes": [{"id": "inner"}], "edges": []},
            "parameter_mappings": {"explicit": "provided", "defaulted": 7},
            "output_mappings": {"answer": "answer"},
        },
        "variables": {"source": "parent"},
    }


@pytest.mark.parametrize(
    ("case", "error"),
    [
        ("custom:missing-id", "未指定自定义模块ID"),
        ("custom:not-found", "自定义模块不存在: not-found"),
        ("custom:empty", "自定义模块内部工作流为空"),
    ],
)
def test_frozen_custom_module_validation(case: str, error: str) -> None:
    result = frozen_result(case)
    assert result == {
        "success": False,
        "message": "",
        "error": error,
        "data": None,
        "variables": {"source": "parent"},
    }


@pytest.mark.asyncio
async def test_autoflow_custom_module_marker_matches_frozen_source() -> None:
    definition = {
        "id": "module-1",
        "display_name": "格式化器",
        "parameters": [
            {"name": "explicit", "default_value": "fallback"},
            {"name": "defaulted", "default_value": 7},
        ],
        "outputs": [{"name": "answer"}],
        "workflow": {"nodes": [{"id": "inner"}], "edges": []},
    }

    class Modules:
        def definition(self, module_id: str) -> Any:
            return definition if module_id == "ready" else None

        async def run_custom_module(self, **_values: Any) -> CustomModuleResult:
            raise AssertionError("marker differential must not run the child graph")

    context = ExecutionContext(
        variables={"source": "parent"}, custom_modules=Modules()
    )
    result = await CustomModuleExecutor().execute(
        {
            "customModuleId": "ready",
            "parameterValues": {"explicit": "provided", "ignored": True},
        },
        context,
    )

    assert {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
        "variables": context.variables,
    } == frozen_result("custom:ready")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "definition", "expected"),
    [
        ({}, None, "未指定自定义模块ID"),
        ({"customModuleId": "not-found"}, None, "自定义模块不存在: not-found"),
        (
            {"customModuleId": "empty"},
            {"workflow": {"nodes": [], "edges": []}},
            "自定义模块内部工作流为空",
        ),
    ],
)
async def test_autoflow_custom_module_validation_matches_frozen_source(
    config: dict[str, Any], definition: Any, expected: str
) -> None:
    class Modules:
        def definition(self, _module_id: str) -> Any:
            return definition

        async def run_custom_module(self, **_values: Any) -> CustomModuleResult:
            raise AssertionError

    result = await CustomModuleExecutor().execute(
        config, ExecutionContext(custom_modules=Modules())
    )
    assert result.success is False
    assert result.error == expected


def test_frozen_workflow_file_sync_variable_and_result_contract() -> None:
    result = frozen_result("workflow:success")
    assert result["success"] is True
    assert result["message"] == "工作流「子工作流」执行完成（2 个模块）"
    assert result["childInputs"] == [{"parent": 1, "child_file": "child.json"}]
    assert result["variables"] == {
        "parent": 3,
        "child_file": "child.json",
        "child": 2,
        "summary": {
            "workflow": "子工作流",
            "file": "child.json",
            "success": True,
            "executed_nodes": 2,
            "failed_nodes": 0,
            "error": None,
        },
    }
    assert [item["event"] for item in result["events"]] == [
        "subflow:started",
        "subflow:completed",
    ]


def test_frozen_workflow_file_string_boole_disable_variable_transfer() -> None:
    result = frozen_result("workflow:no-transfer")
    assert result["success"] is True
    assert result["childInputs"] == [{}]
    assert result["variables"]["parent"] == 1
    assert "child" not in result["variables"]
    assert result["variables"]["summary"]["success"] is True


@pytest.mark.parametrize(
    ("case", "success", "message", "error"),
    [
        (
            "workflow:failure-stop",
            False,
            "",
            "工作流「子工作流」执行失败：child boom",
        ),
        (
            "workflow:failure-continue",
            True,
            "工作流「子工作流」执行失败但已按配置继续：child boom",
            None,
        ),
    ],
)
def test_frozen_workflow_file_stop_on_fail_contract(
    case: str, success: bool, message: str, error: str | None
) -> None:
    result = frozen_result(case)
    assert (result["success"], result["message"], result["error"]) == (
        success,
        message,
        error,
    )
    assert result["variables"]["summary"]["success"] is False


@pytest.mark.parametrize(
    ("case", "fragment"),
    [
        ("workflow:cycle", "检测到工作流循环调用"),
        ("workflow:depth", "工作流嵌套调用层数过深（>16）"),
    ],
)
def test_frozen_workflow_file_recursion_guards(case: str, fragment: str) -> None:
    result = frozen_result(case)
    assert result["success"] is False
    assert fragment in result["error"]
    assert result["childInputs"] == []
    assert result["events"] == []


def test_autoflow_document_storage_roundtrips_b3_frontend_contract() -> None:
    payload = {
        "id": "b3-contract",
        "name": "B3 contract",
        "nodes": [
            {
                "id": "definition",
                "type": "groupNode",
                "position": {"x": 10, "y": 20},
                "width": 480,
                "height": 320,
                "data": {
                    "moduleType": "group",
                    "isSubflow": True,
                    "subflowName": "登录",
                },
            },
            {
                "id": "subflow-call",
                "type": "moduleNode",
                "position": {"x": 600, "y": 20},
                "data": {
                    "moduleType": "subflow",
                    "subflowName": "登录",
                    "subflowGroupId": "definition",
                },
            },
            {
                "id": "workflow-call",
                "type": "moduleNode",
                "position": {"x": 600, "y": 120},
                "data": {
                    "moduleType": "run_workflow_file",
                    "workflowFile": "{{child}}",
                    "waitComplete": True,
                    "passVariables": True,
                    "collectVariables": True,
                    "resultVariable": "childResult",
                    "stopOnFail": False,
                },
            },
            {
                "id": "custom-call",
                "type": "moduleNode",
                "position": {"x": 600, "y": 220},
                "data": {
                    "moduleType": "custom_module",
                    "customModuleId": "formatter",
                    "parameterValues": {"source": "{{input}}"},
                },
            },
        ],
        "edges": [],
        "variables": [],
    }

    draft = WorkflowDraft.from_payload(payload)

    assert draft.to_payload() == payload
    assert draft.layout["nodes"]["definition"] == {
        "position": {"x": 10, "y": 20},
        "width": 480,
        "height": 320,
    }


@pytest.mark.asyncio
async def test_autoflow_run_workflow_file_runtime_integration() -> None:
    class Nested:
        async def run_workflow(
            self,
            reference: str,
            *,
            variables: Any,
            wait_complete: bool,
        ) -> NestedWorkflowResult:
            assert (reference, variables, wait_complete) == (
                "child.json",
                {"parent": 1, "child_file": "child.json"},
                True,
            )
            return NestedWorkflowResult(
                "child.json",
                "子工作流",
                True,
                {"parent": 3, "child_file": "child.json", "child": 2},
                2,
                0,
            )

    context = ExecutionContext(
        variables={"parent": 1, "child_file": "child.json"},
        nested_workflows=Nested(),
    )
    result = await RunWorkflowFileExecutor().execute(
        {"workflowFile": "{child_file}", "resultVariable": "summary"}, context
    )
    source = frozen_result("workflow:success")

    assert result.success == source["success"]
    assert result.message == source["message"]
    assert result.error == source["error"]
    assert result.data == source["data"]
    assert context.variables == source["variables"]


@pytest.mark.asyncio
async def test_autoflow_subflow_runtime_integration() -> None:
    class Canvas:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def run_subflow(
            self, *, group_id: str, name: str
        ) -> NestedWorkflowResult:
            self.calls.append((group_id, name))
            return NestedWorkflowResult(
                "definition", "登录", True, {"inside": 1}, 1, 0
            )

    canvas = Canvas()
    context = ExecutionContext(canvas_subflows=canvas)
    registry = ExecutorRegistry()
    registry.register(SubflowExecutor)
    result = await WorkflowRuntime(registry).execute(
        {
            "nodes": [
                {
                    "id": "call",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "subflow",
                        "config": {
                            "subflowName": "登录",
                            "subflowGroupId": "definition",
                        },
                    },
                }
            ],
            "edges": [],
        },
        context,
    )

    assert result.success is True
    assert result.executed_node_ids == ("call",)
    assert canvas.calls == [("definition", "登录")]


@pytest.mark.asyncio
async def test_autoflow_empty_subflow_preserves_frozen_message() -> None:
    class Canvas:
        async def run_subflow(
            self, *, group_id: str, name: str
        ) -> NestedWorkflowResult:
            return NestedWorkflowResult("definition", "空流程", True, {}, 0, 0)

    events: list[dict[str, Any]] = []

    class Sink:
        async def publish(self, event: dict[str, Any]) -> None:
            events.append(event)

    registry = ExecutorRegistry()
    registry.register(SubflowExecutor)
    result = await WorkflowRuntime(registry).execute(
        {
            "nodes": [
                {
                    "id": "call",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "subflow",
                        "config": {"subflowName": "空流程"},
                    },
                }
            ],
            "edges": [],
        },
        ExecutionContext(canvas_subflows=Canvas(), events=Sink()),
    )

    assert result.success is True
    completed = next(
        event for event in events if event["type"] == "execution:node_complete"
    )
    assert completed["message"] == "子流程 [空流程] 为空"


@pytest.mark.asyncio
async def test_autoflow_custom_module_runtime_integration() -> None:
    definition = {
        "id": "formatter",
        "name": "formatter",
        "display_name": "格式化器",
        "parameters": [
            {"name": "explicit", "default_value": "fallback"},
            {"name": "defaulted", "default_value": 7},
        ],
        "outputs": [{"name": "answer"}],
        "workflow": {"nodes": [{"id": "inner"}], "edges": []},
    }

    class Modules:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any]]] = []

        def definition(self, module_id: str) -> Any:
            return definition if module_id == "formatter" else None

        async def run_custom_module(
            self, *, module_id: str, parameter_values: Any
        ) -> CustomModuleResult:
            self.calls.append((module_id, dict(parameter_values)))
            return CustomModuleResult(
                module_id, "格式化器", True, {"answer": "done"}, 1, 0
            )

    modules = Modules()
    context = ExecutionContext(
        variables={"source": "parent", "keep": 1}, custom_modules=modules
    )
    registry = ExecutorRegistry()
    registry.register(CustomModuleExecutor)
    result = await WorkflowRuntime(registry).execute(
        {
            "nodes": [
                {
                    "id": "custom",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "custom_module",
                        "customModuleId": "formatter",
                        "parameterValues": {"explicit": "{source}"},
                    },
                }
            ],
            "edges": [],
        },
        context,
    )

    assert result.success is True
    assert modules.calls == [
        (
            "formatter",
            {"explicit": "{source}", "defaulted": 7},
        )
    ]
    assert context.variables == {"source": "parent", "keep": 1, "answer": "done"}
