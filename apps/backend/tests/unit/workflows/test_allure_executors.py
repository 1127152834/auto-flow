from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import DesktopActionResult, ExecutionContext


class Artifacts:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.writes: list[dict[str, Any]] = []

    async def write_binary_output(self, **kwargs: Any) -> str:
        self.writes.append(kwargs)
        target = self.root / Path(kwargs["output_path"]).name
        target.write_bytes(kwargs["content"])
        return str(target)


class DesktopActions:
    def __init__(self) -> None:
        self.requests: list[tuple[str, Mapping[str, Any], float]] = []

    async def perform(
        self,
        action: str,
        payload: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> DesktopActionResult:
        self.requests.append((action, payload, timeout_seconds))
        return DesktopActionResult(True)


@pytest.mark.asyncio
async def test_allure_lifecycle_generates_registered_html_and_opens_it(
    tmp_path: Path,
) -> None:
    registry = build_production_executor_registry()
    artifacts = Artifacts(tmp_path)
    desktop = DesktopActions()
    context = ExecutionContext(
        variables={"case": "登录流程"},
        artifacts=artifacts,
        desktop_actions=desktop,
    )
    attachment = tmp_path / "detail.txt"
    attachment.write_text("附件正文", encoding="utf-8")

    assert (
        await registry.get("allure_init").execute({"testSuite": "回归"}, context)
    ).success
    assert (
        await registry.get("allure_start_test").execute(
            {"name": "{case}", "severity": "critical", "testId": "TC-1"},
            context,
        )
    ).success
    assert (
        await registry.get("allure_add_step").execute(
            {"name": "打开首页", "status": "passed"}, context
        )
    ).success
    assert (
        await registry.get("allure_add_attachment").execute(
            {"filePath": str(attachment), "name": "详情"}, context
        )
    ).success
    assert (
        await registry.get("allure_stop_test").execute(
            {"status": "failed", "message": "预期失败"}, context
        )
    ).success
    generated = await registry.get("allure_generate_report").execute(
        {"reportDir": "reports", "autoOpen": True}, context
    )

    assert generated.success is True
    assert context.variables["allure_suite_id"] is None
    assert len(artifacts.writes) == 1
    html = artifacts.writes[0]["content"].decode("utf-8")
    assert all(
        value in html
        for value in ("回归", "登录流程", "打开首页", "附件正文", "预期失败")
    )
    assert desktop.requests == [
        ("open_path", {"path": generated.data["report_path"]}, 60)
    ]


@pytest.mark.asyncio
async def test_allure_sequence_errors_and_auto_closes_unfinished_test(
    tmp_path: Path,
) -> None:
    registry = build_production_executor_registry()
    context = ExecutionContext(artifacts=Artifacts(tmp_path))

    missing = await registry.get("allure_start_test").execute({}, context)
    assert missing.error == "未找到初始化的Allure测试套件，请先调用Allure初始化模块"
    await registry.get("allure_init").execute({}, context)
    no_test = await registry.get("allure_add_step").execute({}, context)
    assert no_test.error == "当前没有正在运行的测试用例"
    await registry.get("allure_start_test").execute({}, context)
    generated = await registry.get("allure_generate_report").execute({}, context)
    assert generated.success is True
    assert '"status": "broken"' in context.artifacts.writes[0]["content"].decode(
        "utf-8"
    )


@pytest.mark.asyncio
async def test_allure_rejects_sensitive_report_content() -> None:
    registry = build_production_executor_registry()
    context = ExecutionContext(
        variables={"secret": "private"}, sensitive_variables={"secret"}
    )
    await registry.get("allure_init").execute({}, context)

    result = await registry.get("allure_start_test").execute(
        {"name": "{secret}"}, context
    )

    assert result.error == "Allure报告内容不能包含凭据或敏感变量"
