"""Accept a durable End intent before stopping the shared Runtime."""

import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.domain.workflows.project_end import validate_project_end

from .base import ModuleExecutor, ModuleResult


class ProjectEndExecutor(ModuleExecutor):
    def requires_browser_for(self, config: dict[str, Any]) -> bool:
        return config.get("retainEnvironment") is True

    @property
    def module_type(self) -> str:
        return "project_end"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        if context.project_data is None:
            return ModuleResult(False, error="项目 End 必须从项目任务执行")
        node_id, visit_id = context.proxy_visit.get()
        if node_id is None or visit_id is None:
            return ModuleResult(False, error="项目 End 缺少节点访问身份")
        try:
            validate_project_end(config)
            targets = context.resolve_value(config.get("recordTargets", []))
            if isinstance(targets, str):
                targets = json.loads(targets)
            if not isinstance(targets, list) or len(targets) > 100:
                raise ValueError("End 记录目标必须是最多100项的列表")
        except (ValueError, TypeError) as error:
            return ModuleResult(False, error=str(error))
        result = await context.project_data(
            {
                "nodeId": node_id,
                "nodeVisitId": visit_id,
                "attempt": 1,
                "commandId": str(
                    uuid5(NAMESPACE_URL, f"autoflow:project-end:{visit_id}:{node_id}")
                ),
                "capability": "project.end",
                "arguments": {"recordTargets": targets},
            }
        )
        if isinstance(result.get("error"), dict):
            return ModuleResult(False, error=result["error"]["message"])
        context.project_end.accepted = True
        return ModuleResult(True, data=result)
