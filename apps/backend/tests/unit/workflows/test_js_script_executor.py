from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext, JsScriptResult


class ScriptGateway:
    def __init__(self, result: JsScriptResult) -> None:
        self.result = result
        self.requests: list[tuple[str, Mapping[str, Any], float]] = []

    async def request_script(
        self,
        code: str,
        variables: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> JsScriptResult:
        self.requests.append((code, variables, timeout_seconds))
        return self.result


@pytest.mark.asyncio
async def test_js_script_updates_existing_variables_and_stores_result() -> None:
    gateway = ScriptGateway(
        JsScriptResult(
            success=True,
            result={"value": 2},
            variables={"count": 2, "notDeclared": 99},
        )
    )
    context = ExecutionContext(
        variables={"count": 1}, browser_scripts=gateway
    )
    executor = build_production_executor_registry().get("js_script")

    result = await executor.execute(
        {
            "code": "function main(vars){vars.count++;return vars.count}",
            "resultVariable": "answer",
        },
        context,
    )

    assert result.success is True
    assert result.data == {"result": {"value": 2}}
    assert context.variables == {"count": 2, "answer": {"value": 2}}
    assert gateway.requests == [
        (
            "function main(vars){vars.count++;return vars.count}",
            {"count": 1},
            30,
        )
    ]


@pytest.mark.asyncio
async def test_js_script_preserves_variables_when_frontend_reports_failure() -> None:
    context = ExecutionContext(
        variables={"count": 1},
        browser_scripts=ScriptGateway(JsScriptResult(False, error="脚本错误")),
    )
    executor = build_production_executor_registry().get("js_script")

    result = await executor.execute({"code": "throw Error('x')"}, context)

    assert result.success is False
    assert result.error == "JS脚本执行失败: 脚本错误"
    assert context.variables == {"count": 1}


@pytest.mark.asyncio
async def test_js_script_requires_code_and_transport() -> None:
    executor = build_production_executor_registry().get("js_script")

    assert (await executor.execute({"code": ""}, ExecutionContext())).error == "JavaScript代码不能为空"
    assert (
        await executor.execute({"code": "return 1"}, ExecutionContext())
    ).error == "JavaScript执行服务不可用"


@pytest.mark.asyncio
async def test_js_script_never_sends_sensitive_values_to_renderer() -> None:
    gateway = ScriptGateway(JsScriptResult(True, variables={"safe": 2}))
    context = ExecutionContext(
        variables={"safe": 1, "secret": "credential"},
        sensitive_variables={"secret"},
        browser_scripts=gateway,
    )
    executor = build_production_executor_registry().get("js_script")

    result = await executor.execute({"code": "return vars.safe"}, context)

    assert result.success is True
    assert gateway.requests[0][1] == {"safe": 1}
    assert context.variables["secret"] == "credential"
