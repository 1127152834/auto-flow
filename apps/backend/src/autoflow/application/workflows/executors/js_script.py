"""Browser JavaScript executor migrated from WebRPA@5ccb900e.

Source: backend/app/executors/basic.py#JsScriptExecutor. License: LICENSE.WebRPA.
"""

from __future__ import annotations

import copy

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult


class JsScriptExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "js_script"

    async def execute(
        self, config: dict, context: ExecutionContext
    ) -> ModuleResult:
        value, sensitive_code = context.resolve_value_with_sensitivity(
            config.get("code", "")
        )
        code = "" if value is None else str(value)
        if not code:
            return ModuleResult(success=False, error="JavaScript代码不能为空")
        if sensitive_code:
            return ModuleResult(
                success=False, error="JavaScript代码不能包含凭据或敏感变量"
            )
        if context.browser_scripts is None:
            return ModuleResult(success=False, error="JavaScript执行服务不可用")
        try:
            outcome = await context.browser_scripts.request_script(
                code,
                {
                    name: copy.deepcopy(variable)
                    for name, variable in context.variables.items()
                    if name not in context.sensitive_variables
                },
                timeout_seconds=30,
            )
        except Exception as error:  # noqa: BLE001 - transport errors become node errors.
            return ModuleResult(success=False, error=f"JS脚本执行异常: {error}")
        if not outcome.success:
            return ModuleResult(
                success=False,
                error=f"JS脚本执行失败: {outcome.error or '未知错误'}",
            )
        if outcome.variables is not None:
            for name in tuple(context.variables):
                if (
                    name not in context.sensitive_variables
                    and name in outcome.variables
                    and context.variables[name] != outcome.variables[name]
                ):
                    context.set_variable(name, copy.deepcopy(outcome.variables[name]))
        result_variable = str(config.get("resultVariable") or "")
        if result_variable:
            context.set_variable(result_variable, copy.deepcopy(outcome.result))
        summary = str(outcome.result)
        if len(summary) > 100:
            summary = summary[:100] + "..."
        return ModuleResult(
            success=True,
            message=f"JS脚本执行成功，返回值: {summary}",
            data={"result": outcome.result},
        )
