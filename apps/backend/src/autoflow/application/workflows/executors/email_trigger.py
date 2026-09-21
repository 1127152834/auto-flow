"""Email trigger migrated from WebRPA@5ccb900e.

Source: backend/app/executors/trigger.py#EmailTriggerExecutor and
backend/app/services/trigger_manager.py#TriggerManager._email_monitor_loop.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_int


class EmailTriggerExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "email_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        server = context.resolve_value(config.get("emailServer", ""))
        port = to_int(config.get("emailPort", 993), 993, context)
        account = context.resolve_value(config.get("emailAccount", ""))
        password = context.resolve_value(config.get("emailPassword", ""))
        from_filter = context.resolve_value(config.get("fromFilter", ""))
        subject_filter = context.resolve_value(config.get("subjectFilter", ""))
        timeout = to_int(config.get("timeout", 0), 0, context)
        check_interval = to_int(config.get("checkInterval", 30), 30, context)
        variable_name = str(config.get("saveToVariable", "email_data"))
        if not all((server, account, password)):
            return ModuleResult(success=False, error="邮件服务器、账号和密码不能为空")
        if context.external_integrations is None:
            return ModuleResult(success=False, error="邮件服务不可用")

        await _progress(context, "📧 邮件监控已启动")
        if not context.node_uses_sensitive_values:
            await _progress(context, f"📍 邮件服务器: {server}:{port}")
            await _progress(context, f"👤 监控账号: {account}")
            if from_filter:
                await _progress(context, f"🔍 发件人过滤: {from_filter}")
            if subject_filter:
                await _progress(context, f"🔍 主题过滤: {subject_filter}")

        wait = _wait_for_email(
            context,
            {
                "server": str(server),
                "port": port,
                "account": str(account),
                "password": str(password),
                "fromFilter": str(from_filter),
                "subjectFilter": str(subject_filter),
                "timeoutSeconds": max(0.1, min(30, timeout or 30)),
            },
            check_interval,
        )
        try:
            email_data = (
                await asyncio.wait_for(wait, timeout) if timeout > 0 else await wait
            )
        except TimeoutError:
            return ModuleResult(success=False, error=f"邮件监控等待超时（{timeout}秒）")
        context.set_variable(variable_name, email_data)
        return ModuleResult(
            success=True,
            message=f"收到新邮件: {email_data.get('subject', '无主题')}",
            data=email_data,
        )


async def _wait_for_email(
    context: ExecutionContext,
    payload: dict[str, Any],
    check_interval: int,
) -> dict[str, Any]:
    assert context.external_integrations is not None
    while True:
        if context.cancellation is not None:
            context.cancellation.raise_if_cancelled()
        try:
            matches = await context.external_integrations.call("imap_unseen", payload)
            if isinstance(matches, list) and matches:
                last = matches[-1]
                if isinstance(last, Mapping):
                    return dict(last)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - source keeps polling after IMAP failures.
            pass
        await asyncio.sleep(max(0, check_interval))


async def _progress(context: ExecutionContext, message: str) -> None:
    context.log_records.append(
        {
            "timestamp": context.clock.now().isoformat(),
            "level": "info",
            "message": message,
            "duration": 0,
            "nodeId": context.current_node_id or "",
        }
    )
    await context.send_progress(message)


EMAIL_TRIGGER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (EmailTriggerExecutor,)
