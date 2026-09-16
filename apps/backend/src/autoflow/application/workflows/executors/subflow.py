from __future__ import annotations

from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult


class SubflowExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "subflow"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        del context
        name = str(config.get("subflowName") or "")
        group_id = str(config.get("subflowGroupId") or "")
        if not name and not group_id:
            return ModuleResult(success=False, error="未选择子流程")
        return ModuleResult(
            success=True,
            message=f"调用子流程 [{name or group_id}]",
            data={"subflow_group_id": group_id, "subflow_name": name},
        )
