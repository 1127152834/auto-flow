"""Text-to-speech executor migrated from WebRPA@5ccb900e.

Source: backend/app/executors/basic.py#TextToSpeechExecutor. License: LICENSE.WebRPA.
"""

from __future__ import annotations

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float


class TextToSpeechExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "text_to_speech"

    async def execute(
        self, config: dict, context: ExecutionContext
    ) -> ModuleResult:
        value, sensitive = context.resolve_value_with_sensitivity(config.get("text", ""))
        text = "" if value is None else str(value)
        if not text:
            return ModuleResult(success=False, error="朗读文本不能为空")
        if sensitive:
            return ModuleResult(success=False, error="朗读文本不能包含凭据或敏感变量")
        if context.speech is None:
            return ModuleResult(success=False, error="文本朗读服务不可用")
        lang_value = context.resolve_value(config.get("lang", "zh-CN"))
        lang = "zh-CN" if lang_value is None else str(lang_value)
        try:
            outcome = await context.speech.speak(
                text,
                lang=lang,
                rate=to_float(config.get("rate", 1), 1, context),
                pitch=to_float(config.get("pitch", 1), 1, context),
                volume=to_float(config.get("volume", 1), 1, context),
                timeout_seconds=60,
            )
        except Exception as error:  # noqa: BLE001 - transport errors become node errors.
            return ModuleResult(success=False, error=f"文本朗读失败: {error}")
        if not outcome.success:
            return ModuleResult(
                success=False, error=f"文本朗读失败: {outcome.error or '语音不可用'}"
            )
        summary = text[:50] + ("..." if len(text) > 50 else "")
        return ModuleResult(
            success=True,
            message=f"已朗读文本: {summary}",
            data={"text": text, "lang": lang},
        )
