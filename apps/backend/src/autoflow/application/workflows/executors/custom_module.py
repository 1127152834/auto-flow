from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult


class CustomModuleExecutor(ModuleExecutor):
    label = "自定义模块"
    requires_browser = False

    @property
    def module_type(self) -> str:
        return "custom_module"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        module_id = config.get("customModuleId")
        if not isinstance(module_id, str) or not module_id:
            return ModuleResult(success=False, error="未指定自定义模块ID")
        definition = (
            context.custom_modules.definition(module_id)
            if context.custom_modules is not None
            else None
        )
        if definition is None:
            return ModuleResult(
                success=False, error=f"自定义模块不存在: {module_id}"
            )
        workflow = definition.get("workflow")
        if not isinstance(workflow, Mapping):
            return ModuleResult(success=False, error="自定义模块内部工作流为空")
        nodes = workflow.get("nodes", [])
        if not isinstance(nodes, list) or not nodes:
            return ModuleResult(success=False, error="自定义模块内部工作流为空")
        workflow_definition = copy.deepcopy(dict(workflow))
        raw_values = config.get("parameterValues", {})
        user_values = raw_values if isinstance(raw_values, Mapping) else {}
        parameter_mappings: dict[str, Any] = {}
        parameters = definition.get("parameters", [])
        if isinstance(parameters, list):
            for parameter in parameters:
                if not isinstance(parameter, Mapping):
                    continue
                name = parameter.get("name")
                if not isinstance(name, str) or not name:
                    continue
                parameter_mappings[name] = copy.deepcopy(
                    user_values[name]
                    if name in user_values
                    else parameter.get("default_value", "")
                )
        output_mappings: dict[str, str] = {}
        outputs = definition.get("outputs", [])
        if isinstance(outputs, list):
            for output in outputs:
                if not isinstance(output, Mapping):
                    continue
                name = output.get("name")
                if isinstance(name, str) and name:
                    output_mappings[name] = name
        display_name = str(
            definition.get("display_name") or definition.get("name") or module_id
        )
        return ModuleResult(
            success=True,
            message=f"自定义模块 '{display_name}' 准备执行",
            data={
                "is_custom_module": True,
                "module_id": module_id,
                "module_name": display_name,
                "workflow_definition": workflow_definition,
                "parameter_mappings": parameter_mappings,
                "output_mappings": output_mappings,
            },
        )
