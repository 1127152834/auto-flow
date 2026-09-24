"""Allure executors migrated from WebRPA@5ccb900e.

Source: backend/app/executors/allure.py. License: LICENSE.WebRPA.
Report output and auto-open use AutoFlow's artifact and Studio platform boundaries.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .allure_report_builder import build_report
from .base import ModuleExecutor, ModuleResult

_ALLURE_SUITE_STORE: dict[str, dict[str, Any]] = {}


def _suite(context: ExecutionContext) -> tuple[str, dict[str, Any]] | None:
    suite_id = context.get_variable("allure_suite_id")
    if not isinstance(suite_id, str) or suite_id not in _ALLURE_SUITE_STORE:
        return None
    return suite_id, _ALLURE_SUITE_STORE[suite_id]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sensitive_failure(context: ExecutionContext) -> ModuleResult | None:
    if context.node_uses_sensitive_values:
        return ModuleResult(success=False, error="Allure报告内容不能包含凭据或敏感变量")
    return None


class AllureInitExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "allure_init"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        suite_name = (
            config.get("testSuite") or config.get("suiteName") or "默认测试套件"
        )
        suite_id = str(uuid.uuid4())
        _ALLURE_SUITE_STORE[suite_id] = {
            "suite_name": suite_name,
            "results": [],
            "current_test": None,
        }
        context.set_variable("allure_suite_id", suite_id)
        return ModuleResult(
            success=True,
            message=f"已初始化Allure测试套件: {suite_name}",
            data={"suite_id": suite_id},
        )


class AllureStartTestExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "allure_start_test"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        found = _suite(context)
        if found is None:
            return ModuleResult(
                success=False,
                error="未找到初始化的Allure测试套件，请先调用Allure初始化模块",
            )
        _, suite = found
        test_name = context.resolve_value(
            config.get("name") or config.get("testName") or "未命名测试用例"
        )
        description = context.resolve_value(config.get("description", ""))
        severity = context.resolve_value(config.get("severity", "normal"))
        test_id = context.resolve_value(config.get("testId", ""))
        if failure := _sensitive_failure(context):
            return failure
        if suite["current_test"]:
            if not suite["current_test"].get("stop"):
                suite["current_test"]["stop"] = _now_ms()
                suite["current_test"]["status"] = "broken"
                suite["current_test"]["statusDetails"] = {"message": "被新测试强制中断"}
            suite["results"].append(suite["current_test"])
        suite["current_test"] = {
            "uuid": str(uuid.uuid4()),
            "name": test_name,
            "description": description,
            "start": _now_ms(),
            "status": "unknown",
            "labels": [
                {"name": "suite", "value": suite["suite_name"]},
                {"name": "severity", "value": severity},
                {
                    "name": "testId",
                    "value": test_id or f"TEST-{len(suite['results']) + 1}",
                },
            ],
            "steps": [],
            "attachments": [],
        }
        return ModuleResult(success=True, message=f"已开始测试用例: {test_name}")


class AllureAddStepExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "allure_add_step"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        found = _suite(context)
        if found is None:
            return ModuleResult(success=False, error="未找到初始化的Allure测试套件")
        current_test = found[1]["current_test"]
        if not current_test:
            return ModuleResult(success=False, error="当前没有正在运行的测试用例")
        step_name = context.resolve_value(
            config.get("name") or config.get("stepName") or "测试步骤"
        )
        status = context.resolve_value(config.get("status", "passed"))
        description = context.resolve_value(config.get("description", ""))
        if failure := _sensitive_failure(context):
            return failure
        stamp = _now_ms()
        current_test["steps"].append(
            {
                "name": step_name,
                "status": status,
                "description": description,
                "start": stamp,
                "stop": stamp,
                "steps": [],
                "attachments": [],
            }
        )
        return ModuleResult(success=True, message=f"已添加步骤: {step_name}")


class AllureAddAttachmentExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "allure_add_attachment"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        found = _suite(context)
        if found is None:
            return ModuleResult(
                success=False,
                error="未找到初始化的Allure测试套件，请先调用Allure初始化模块",
            )
        current_test = found[1].get("current_test")
        if not current_test:
            return ModuleResult(
                success=False,
                error="当前没有正在运行的测试用例，请先调用「开始测试用例」",
            )
        file_path = (
            str(
                context.resolve_value(
                    config.get("filePath")
                    or config.get("path")
                    or config.get("file")
                    or ""
                )
            )
            .strip()
            .strip('"')
        )
        name = str(context.resolve_value(config.get("name") or "")).strip()
        if failure := _sensitive_failure(context):
            return failure
        if not file_path:
            return ModuleResult(success=False, error="未指定附件文件路径")
        if not os.path.isfile(file_path):
            return ModuleResult(success=False, error=f"附件文件不存在：{file_path}")
        name = name or os.path.basename(file_path)
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".txt": "text/plain",
            ".log": "text/plain",
            ".json": "text/plain",
            ".csv": "text/plain",
            ".xml": "text/plain",
            ".md": "text/plain",
            ".html": "text/html",
            ".htm": "text/html",
        }.get(os.path.splitext(file_path)[1].lower(), "text/plain")
        current_test.setdefault("attachments", []).append(
            {"name": name, "source": file_path, "type": mime}
        )
        return ModuleResult(success=True, message=f"已添加附件：{name}")


class AllureStopTestExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "allure_stop_test"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        found = _suite(context)
        if found is None:
            return ModuleResult(success=False, error="未找到初始化的Allure测试套件")
        suite = found[1]
        current_test = suite["current_test"]
        if not current_test:
            return ModuleResult(success=False, error="当前没有正在运行的测试用例")
        status = context.resolve_value(config.get("status", "passed"))
        fail_msg = context.resolve_value(
            config.get("message") or config.get("failMsg") or ""
        )
        if failure := _sensitive_failure(context):
            return failure
        current_test["stop"] = _now_ms()
        current_test["status"] = status
        if fail_msg:
            current_test["statusDetails"] = {"message": fail_msg}
        suite["results"].append(current_test)
        suite["current_test"] = None
        return ModuleResult(success=True, message=f"已结束测试用例，状态: {status}")


class AllureGenerateReportExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "allure_generate_report"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        found = _suite(context)
        if found is None:
            return ModuleResult(success=False, error="未找到初始化的Allure测试套件")
        suite_id, suite = found
        if suite["current_test"]:
            suite["current_test"]["stop"] = _now_ms()
            if suite["current_test"]["status"] == "unknown":
                suite["current_test"]["status"] = "broken"
            suite["results"].append(suite["current_test"])
            suite["current_test"] = None
        results = list(suite["results"])
        suite_name = suite["suite_name"]
        del _ALLURE_SUITE_STORE[suite_id]
        context.set_variable("allure_suite_id", None)
        writer = context.node_artifacts
        if writer is None:
            return ModuleResult(success=False, error="生成报告失败: 运行产物服务不可用")
        report_dir = str(config.get("reportDir") or "allure_reports")
        report_path = str(
            Path(report_dir)
            / f"report_{context.clock.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
        try:
            html = await asyncio.to_thread(
                build_report, results, str(suite_name), Path(report_dir)
            )
            actual_path = await writer.write_binary_output(
                output_path=report_path,
                content=html.encode("utf-8"),
                mime_type="text/html",
            )
            open_error = None
            if config.get("autoOpen", False):
                if context.desktop_actions is None:
                    open_error = "桌面平台服务不可用"
                else:
                    opened = await context.desktop_actions.perform(
                        "open_path", {"path": actual_path}, timeout_seconds=60
                    )
                    if not opened.success:
                        open_error = opened.error or "打开报告失败"
            data = {"report_path": actual_path}
            if open_error:
                data["auto_open_error"] = open_error
            return ModuleResult(
                success=True,
                message=f"已生成Allure测试报告: {actual_path}",
                data=data,
            )
        except Exception as error:  # noqa: BLE001 - artifact errors are node errors.
            return ModuleResult(success=False, error=f"生成报告失败: {error}")


ALLURE_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    AllureInitExecutor,
    AllureStartTestExecutor,
    AllureAddStepExecutor,
    AllureAddAttachmentExecutor,
    AllureStopTestExecutor,
    AllureGenerateReportExecutor,
)
