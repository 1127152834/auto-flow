"""WebRPA AI executors adapted to AutoFlow's managed model boundary.

Source: reference/WebRPA/backend/app/executors/ai.py@5ccb900e8dcf1530aae66f676d87593c416c7ebb
License: LICENSE.WebRPA
Changes: model connection fields are replaced by stable main-application model IDs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from autoflow.domain.models import ModelInvocationResult
from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float, to_int


class AIChatExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "ai_chat"

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(config.get("modelId"), str) or not config["modelId"].strip():
            return False, "请选择主应用中的模型"
        if not isinstance(config.get("userPrompt"), str) or not config[
            "userPrompt"
        ].strip():
            return False, "用户提示词不能为空"
        return True, ""

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        if context.models is None:
            return ModuleResult(success=False, error="模型服务不可用")
        candidates = [config]
        fallbacks = config.get("fallbackModels")
        if isinstance(fallbacks, list):
            candidates.extend(
                {**config, **item}
                for item in fallbacks
                if isinstance(item, dict) and item.get("modelId")
            )
        fallback_ids = config.get("fallbackModelIds")
        if isinstance(fallback_ids, list):
            candidates.extend(
                {**config, "modelId": model_id}
                for model_id in fallback_ids
                if isinstance(model_id, str) and model_id
            )
        last_error = "所有候选模型均调用失败"
        for index, candidate in enumerate(candidates):
            model_id = candidate.get("modelId")
            if not isinstance(model_id, str) or not model_id.strip():
                continue
            try:
                result = await self._invoke(model_id, candidate, context)
            except Exception as error:  # noqa: BLE001 - provider errors become node errors.
                last_error = str(error) or "模型调用失败"
                if index + 1 < len(candidates):
                    await context.send_progress(
                        f"模型[{index + 1}/{len(candidates)}]调用失败，尝试切换下一个…",
                        "warning",
                    )
                continue
            variable_name = candidate.get("variableName", "")
            if isinstance(variable_name, str) and variable_name:
                context.set_variable(variable_name, result.content)
            preview = (
                f"{result.content[:100]}..."
                if len(result.content) > 100
                else result.content
            )
            return ModuleResult(
                success=True,
                message=f"AI回复: {preview}",
                data={
                    "response": result.content,
                    "reasoning": result.reasoning or None,
                    "model": result.model_key,
                    "modelId": model_id,
                    "usage": result.usage,
                },
            )
        return ModuleResult(success=False, error=last_error)

    async def _invoke(
        self,
        model_id: str,
        config: Mapping[str, Any],
        context: ExecutionContext,
    ) -> ModelInvocationResult:
        system_prompt = self.get_text(config.get("systemPrompt", ""), context)
        user_prompt = self.get_text(config.get("userPrompt", ""), context)
        if not user_prompt:
            raise ValueError("用户提示词不能为空")
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        assert context.models is not None
        result = await context.models.invoke(
            model_id,
            {
                "messages": messages,
                "temperature": to_float(config.get("temperature", 0.7), 0.7, context),
                "maxTokens": to_int(config.get("maxTokens", 2000), 2000, context),
                "timeoutSeconds": to_float(
                    config.get("timeoutSeconds", 180), 180, context
                ),
            },
        )
        if not isinstance(result, ModelInvocationResult):
            raise TypeError("模型服务返回格式异常")
        return result
