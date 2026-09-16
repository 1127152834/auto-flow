from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.workflow_chain import (
    RunWorkflowFileExecutor,
)
from autoflow.domain.workflows.document import WorkflowDraft
from autoflow.domain.workflows.execution import (
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


@pytest.mark.skip(
    reason=(
        "待 runtime 提供同画布子图解析/执行入口；名称优先、ID回退，分组几何与"
        "subflow_header 可达图、32层递归和错误分支必须由完整图运行器实现"
    )
)
def test_autoflow_subflow_runtime_integration() -> None:
    """不能由独立 executor 或简化顺序执行器代替完整子图运行。"""


@pytest.mark.skip(
    reason=(
        "待 CustomModuleRepository 与 runtime 隔离作用域入口；需要传入参数解析、"
        "仅声明输出回收、16层递归保护、取消传播及原执行图/变量恢复"
    )
)
def test_autoflow_custom_module_runtime_integration() -> None:
    """自定义模块真实执行属于 runtime 与定义仓储的联合能力。"""
