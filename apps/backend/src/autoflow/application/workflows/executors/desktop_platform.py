from __future__ import annotations

from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult


async def _perform(
    context: ExecutionContext, action: str, payload: dict[str, Any]
) -> ModuleResult | None:
    if context.desktop_actions is None:
        return ModuleResult(success=False, error="桌面平台服务不可用")
    result = await context.desktop_actions.perform(action, payload, timeout_seconds=60)
    if not result.success:
        return ModuleResult(success=False, error=result.error or "平台操作失败")
    return None


class SetClipboardExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "set_clipboard"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        content_type = str(context.resolve_value(config.get("contentType", "text")))
        field = "imagePath" if content_type == "image" else "textContent"
        value, sensitive = context.resolve_value_with_sensitivity(config.get(field, ""))
        value = "" if value is None else str(value)
        if not value:
            return ModuleResult(
                success=False,
                error="图片路径不能为空"
                if content_type == "image"
                else "文本内容不能为空",
            )
        if sensitive:
            return ModuleResult(success=False, error="剪贴板内容不能包含凭据或敏感变量")
        action = (
            "clipboard_write_image"
            if content_type == "image"
            else "clipboard_write_text"
        )
        key = "path" if content_type == "image" else "text"
        failure = await _perform(context, action, {key: value})
        if failure:
            return failure
        if content_type == "image":
            return ModuleResult(success=True, message=f"已将图片复制到剪贴板: {value}")
        display = value[:50] + "..." if len(value) > 50 else value
        return ModuleResult(success=True, message=f"已将文本复制到剪贴板: {display}")


class GetClipboardExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "get_clipboard"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        variable_name = str(config.get("variableName") or "")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")
        if context.desktop_actions is None:
            return ModuleResult(success=False, error="桌面平台服务不可用")
        result = await context.desktop_actions.perform(
            "clipboard_read_text", {}, timeout_seconds=60
        )
        if not result.success:
            return ModuleResult(success=False, error=result.error or "获取剪贴板失败")
        value = "" if result.value is None else str(result.value)
        context.mark_sensitive_use()
        context.set_variable(variable_name, value, sensitive=True)
        if not value:
            return ModuleResult(
                success=True,
                message=f"剪贴板为空，已设置变量 {variable_name} 为空字符串",
                data=value,
            )
        display = value[:50] + "..." if len(value) > 50 else value
        return ModuleResult(
            success=True, message=f"已获取剪贴板内容: {display}", data=value
        )


class PlaySoundExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "play_sound"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        try:
            count = int(context.resolve_value(config.get("beepCount", 1)))
            interval = float(context.resolve_value(config.get("beepInterval", 0.3)))
        except (TypeError, ValueError):
            count, interval = 1, 0.3
        if count <= 0:
            return ModuleResult(
                success=True,
                message=f"已播放 {count} 次提示音",
                data={"count": count},
            )
        failure = await _perform(
            context, "beep", {"count": count, "interval": max(0.0, interval)}
        )
        return failure or ModuleResult(
            success=True,
            message=f"已播放 {count} 次提示音",
            data={"count": count},
        )


class SystemNotificationExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "system_notification"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        title, title_sensitive = context.resolve_value_with_sensitivity(
            config.get("notifyTitle", "WebRPA通知")
        )
        message, message_sensitive = context.resolve_value_with_sensitivity(
            config.get("notifyMessage", "")
        )
        title = str(title or "WebRPA通知")
        message = "" if message is None else str(message)
        if not message:
            return ModuleResult(success=False, error="通知消息不能为空")
        if title_sensitive or message_sensitive:
            return ModuleResult(success=False, error="系统通知不能包含凭据或敏感变量")
        try:
            duration = int(context.resolve_value(config.get("duration", 5)))
        except (TypeError, ValueError):
            duration = 5
        if duration <= 0:
            duration = 5
        raw_sound = config.get("playSound", True)
        if isinstance(raw_sound, str):
            raw_sound = context.resolve_value(raw_sound)
        play_sound = raw_sound in (True, "true", "True", "1", 1)
        failure = await _perform(
            context,
            "notification",
            {
                "title": title,
                "message": message,
                "duration": duration,
                "playSound": play_sound,
            },
        )
        return failure or ModuleResult(
            success=True,
            message=f"已显示系统通知: {title}（{duration}秒）",
            data={"title": title, "message": message, "duration": duration},
        )


DESKTOP_PLATFORM_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    SetClipboardExecutor,
    GetClipboardExecutor,
    PlaySoundExecutor,
    SystemNotificationExecutor,
)
