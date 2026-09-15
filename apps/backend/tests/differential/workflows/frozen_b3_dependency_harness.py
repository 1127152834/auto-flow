from __future__ import annotations

import asyncio
import io
import json
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import app.executors.custom_module as custom_module_source
import app.executors.workflow_chain as workflow_chain_source
from app.executors.base import ExecutionContext
from app.executors.custom_module import CustomModuleExecutor
from app.executors.subflow import SubflowExecutor
from app.executors.workflow_chain import RunWorkflowFileExecutor


def result_payload(result: Any, context: ExecutionContext) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
        "variables": context.variables,
    }


async def subflow_case(case: str) -> dict[str, Any]:
    configs = {
        "missing": {},
        "name": {"subflowName": "登录"},
        "id": {"subflowGroupId": "group-1"},
        "both": {"subflowName": "登录", "subflowGroupId": "group-1"},
    }
    context = ExecutionContext(variables={"kept": 1})
    result = await SubflowExecutor().execute(configs[case], context)
    return result_payload(result, context)


async def custom_module_case(case: str) -> dict[str, Any]:
    context = ExecutionContext(variables={"source": "parent"})
    definitions = {
        "ready": {
            "id": "module-1",
            "display_name": "格式化器",
            "parameters": [
                {"name": "explicit", "default_value": "fallback"},
                {"name": "defaulted", "default_value": 7},
            ],
            "outputs": [{"name": "answer"}],
            "workflow": {"nodes": [{"id": "inner"}], "edges": []},
        },
        "empty": {
            "id": "module-empty",
            "display_name": "空模块",
            "parameters": [],
            "outputs": [],
            "workflow": {"nodes": [], "edges": []},
        },
    }

    if case == "missing-id":
        config: dict[str, Any] = {}
    elif case == "not-found":
        config = {"customModuleId": "not-found"}

        def missing(_module_id: str) -> dict[str, Any]:
            raise FileNotFoundError("自定义模块不存在: not-found")

        custom_module_source.load_custom_module_definition = missing
    else:
        config = {
            "customModuleId": case,
            "parameterValues": {"explicit": "provided", "ignored": True},
        }
        custom_module_source.load_custom_module_definition = lambda module_id: (
            definitions[module_id]
        )

    result = await CustomModuleExecutor().execute(config, context)
    return result_payload(result, context)


async def workflow_file_case(case: str) -> dict[str, Any]:
    emitted: list[dict[str, Any]] = []
    child_inputs: list[dict[str, Any]] = []

    async def emit(event: str, payload: dict[str, Any]) -> None:
        emitted.append({"event": event, "payload": payload})

    workflow_chain_source._emit_subflow = emit

    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "child.json"
        target.write_text(
            json.dumps(
                {
                    "id": "child-id",
                    "name": "子工作流",
                    "nodes": [
                        {
                            "id": "inner",
                            "type": "moduleNode",
                            "position": {"x": 1, "y": 2},
                            "data": {"moduleType": "set_variable", "label": "赋值"},
                        }
                    ],
                    "edges": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        workflow_chain_source._resolve_workflow_path = lambda _filename: target

        class Status:
            value = "failed" if case.startswith("failure") else "completed"

        class ExecutionResult:
            status = Status()
            failed_nodes = 1 if case.startswith("failure") else 0
            error_message = "child boom" if case.startswith("failure") else None

        class WorkflowExecutor:
            executed_nodes = 2
            failed_nodes = 1 if case.startswith("failure") else 0
            _first_error_message = None

            def __init__(self, **kwargs: Any) -> None:
                self.workflow = kwargs["workflow"]
                self.context = ExecutionContext()
                self.on_log = None

            async def execute(self) -> ExecutionResult:
                child_inputs.append(dict(self.context.variables))
                self.context.set_variable("parent", 3)
                self.context.set_variable("child", 2)
                return ExecutionResult()

        fake_service = types.ModuleType("app.services.workflow_executor")
        fake_service.WorkflowExecutor = WorkflowExecutor
        sys.modules["app.services.workflow_executor"] = fake_service

        context = ExecutionContext(variables={"parent": 1})
        config: dict[str, Any] = {
            "workflowFile": "{{child_file}}",
            "resultVariable": "summary",
        }
        context.set_variable("child_file", "child.json")

        if case == "no-transfer":
            config.update({"passVariables": "false", "collectVariables": "0"})
        elif case == "failure-continue":
            config["stopOnFail"] = "no"
        elif case == "failure-stop":
            config["stopOnFail"] = True
        elif case == "cycle":
            context._workflow_chain_stack = [str(target.resolve()).lower()]
        elif case == "depth":
            context._workflow_chain_stack = [
                f"/tmp/{index}.json" for index in range(16)
            ]

        result = await RunWorkflowFileExecutor().execute(config, context)
        normalized_emitted = [
            {
                "event": item["event"],
                "success": item["payload"].get("success"),
                "status": item["payload"].get("status"),
                "name": item["payload"].get("name"),
            }
            for item in emitted
        ]
        return {
            **result_payload(result, context),
            "childInputs": child_inputs,
            "events": normalized_emitted,
        }


async def run(case: str) -> dict[str, Any]:
    family, name = case.split(":", 1)
    if family == "subflow":
        return await subflow_case(name)
    if family == "custom":
        return await custom_module_case(name)
    if family == "workflow":
        return await workflow_file_case(name)
    raise ValueError(case)


if __name__ == "__main__":
    captured = io.StringIO()
    with redirect_stdout(captured):
        output = asyncio.run(run(sys.argv[1]))
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
