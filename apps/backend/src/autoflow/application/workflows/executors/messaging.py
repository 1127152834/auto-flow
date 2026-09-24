"""Messaging executors migrated from WebRPA@5ccb900e.

Sources: backend/app/executors/advanced.py and notify_apprise.py.
License and adaptation record: LICENSE.WebRPA.
"""

from __future__ import annotations

from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float


async def _call(
    context: ExecutionContext, integration: str, payload: dict[str, Any]
) -> Any:
    if context.external_integrations is None:
        raise RuntimeError("外部服务不可用")
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()
    result = await context.external_integrations.call(integration, payload)
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()
    return result


def _text(config: dict[str, Any], key: str, context: ExecutionContext) -> str:
    value = context.resolve_value(config.get(key, ""))
    return "" if value is None else str(value)


class NotifyTelegramExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "notify_telegram"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        token = _text(config, "botToken", context)
        chat_id = _text(config, "chatId", context)
        message = _text(config, "message", context) or _text(config, "body", context)
        title = _text(config, "title", context)
        if not message:
            return ModuleResult(success=False, error="通知内容不能为空")
        if not token or not chat_id:
            return ModuleResult(success=False, error="服务配置不完整")
        try:
            await _call(
                context,
                "telegram",
                {
                    "botToken": token,
                    "chatId": chat_id,
                    "title": title,
                    "message": message,
                    "timeoutSeconds": to_float(config.get("timeout", 30), 30, context),
                },
            )
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=str(error) or "通知发送失败")
        return ModuleResult(success=True, message="通知发送成功")


class SendEmailExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "send_email"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        sender = _text(config, "senderEmail", context)
        auth_code = _text(config, "authCode", context)
        recipient = _text(config, "recipientEmail", context)
        subject = _text(config, "emailSubject", context)
        content = _text(config, "emailContent", context)
        if not sender:
            return ModuleResult(success=False, error="发件人邮箱不能为空")
        if not auth_code:
            return ModuleResult(success=False, error="授权码不能为空")
        if not recipient:
            return ModuleResult(success=False, error="收件人邮箱不能为空")
        try:
            await _call(
                context,
                "smtp_qq",
                {
                    "senderEmail": sender,
                    "authCode": auth_code,
                    "recipientEmail": recipient,
                    "subject": subject,
                    "content": content,
                    "timeoutSeconds": to_float(config.get("timeout", 30), 30, context),
                },
            )
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=str(error) or "发送邮件失败")
        return ModuleResult(
            success=True,
            message=f"邮件已发送至: {recipient}",
            data={"recipient": recipient, "subject": subject},
        )


MESSAGE_EXECUTORS = (NotifyTelegramExecutor, SendEmailExecutor)
