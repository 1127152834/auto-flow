from __future__ import annotations

from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult


class RunWorkflowFileExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "run_workflow_file"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        reference = context.resolve_value(
            config.get("workflowFile", "") or config.get("workflow", "")
        )
        if not reference:
            return ModuleResult(
                success=False, error="未指定要运行的工作流（workflowFile 为空）"
            )
        if context.nested_workflows is None:
            return ModuleResult(success=False, error="子工作流运行服务不可用")
        wait_complete = _boolean(config.get("waitComplete", True))
        pass_variables = _boolean(config.get("passVariables", True))
        collect_variables = _boolean(config.get("collectVariables", True))
        stop_on_fail = _boolean(config.get("stopOnFail", True))
        result_variable = str(config.get("resultVariable") or "").strip()
        try:
            result = await context.nested_workflows.run_workflow(
                str(reference),
                variables=dict(context.variables) if pass_variables else {},
                wait_complete=wait_complete,
            )
        except Exception as error:  # noqa: BLE001 -- source returns node failure.
            return ModuleResult(
                success=False,
                error=f"运行工作流「{reference}」异常：{error}",
            )
        if not wait_complete:
            return ModuleResult(
                success=True,
                message=f"已异步发起工作流「{result.name}」（不等待其完成）",
                data={"workflow": result.name, "waited": False},
            )
        if collect_variables:
            for name, value in result.variables.items():
                context.set_variable(name, value)
        summary = {
            "workflow": result.name,
            "file": result.reference,
            "success": result.success,
            "executed_nodes": result.executed_nodes,
            "failed_nodes": result.failed_nodes,
            "error": result.error,
        }
        if result_variable:
            context.set_variable(result_variable, summary)
        if result.success:
            return ModuleResult(
                success=True,
                message=f"工作流「{result.name}」执行完成（{result.executed_nodes} 个模块）",
                data=summary,
            )
        child_error = result.error or "子工作流执行失败"
        if stop_on_fail:
            return ModuleResult(
                success=False,
                error=f"工作流「{result.name}」执行失败：{child_error}",
                data=summary,
            )
        return ModuleResult(
            success=True,
            message=f"工作流「{result.name}」执行失败但已按配置继续：{child_error}",
            data=summary,
        )


def _boolean(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", ""}
    return bool(value)
