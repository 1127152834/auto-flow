"""Explicit project data commands over the owning production worker pipe."""

from __future__ import annotations

import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.domain.workflows.project_data import PROJECT_DATA_ERRORS

from .base import ModuleExecutor, ModuleResult


def _failure(code: str) -> ModuleResult:
    if code not in PROJECT_DATA_ERRORS:
        code = "PROJECT_DATA_FAILED"
    return ModuleResult(False, error=PROJECT_DATA_ERRORS[code], data={"projectDataError": code})


class ProjectDataExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "project_data"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        if context.project_data is None:
            return _failure("CAPABILITY_MISSING")
        node_id, visit_id = context.proxy_visit.get()
        if node_id is None or visit_id is None:
            return _failure("CAPABILITY_SCOPE_DENIED")
        action = config.get("action", "inputs")
        variable = config.get("resultVariable", "project_result")
        if (
            not isinstance(action, str)
            or not isinstance(variable, str)
            or not variable.strip()
        ):
            return _failure("VALIDATION_ERROR")
        try:
            arguments = context.resolve_value(config.get("arguments", {}))
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(arguments, dict):
                raise TypeError
        except (ValueError, TypeError):
            return _failure("VALIDATION_ERROR")
        # One identity per node visit; transport failure must never retry a write
        # under a fresh identity. The operation query accepts this original ID.
        command_id = str(
            uuid5(NAMESPACE_URL, f"autoflow:project-data:{visit_id}:{node_id}:{action}")
        )
        result = await context.project_data(
            {
                "nodeId": node_id,
                "nodeVisitId": visit_id,
                "attempt": 1,
                "commandId": command_id,
                "capability": f"project.data.{action}",
                "arguments": arguments,
            }
        )
        if isinstance(result.get("error"), dict):
            return _failure(str(result["error"].get("code", "PROJECT_DATA_FAILED")))
        output = {**result, "commandId": command_id}
        context.set_variable(variable, output)
        return ModuleResult(True, data=output)
