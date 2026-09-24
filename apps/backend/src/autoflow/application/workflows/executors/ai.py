"""WebRPA AI executors adapted to AutoFlow's managed model boundary.

Source: reference/WebRPA/backend/app/executors/ai.py@5ccb900e8dcf1530aae66f676d87593c416c7ebb
License: LICENSE.WebRPA
Changes: model connection fields are replaced by stable main-application model IDs.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from autoflow.domain.models import ModelInvocationResult
from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float, to_int


def _model_candidates(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates = [dict(config)]
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
    return candidates


async def invoke_managed_chat(
    config: Mapping[str, Any],
    context: ExecutionContext,
    system_prompt: str,
    user_prompt: str,
    *,
    default_temperature: float,
) -> tuple[ModelInvocationResult, str]:
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    return await invoke_managed_messages(
        config,
        context,
        messages,
        default_temperature=default_temperature,
    )


async def invoke_managed_messages(
    config: Mapping[str, Any],
    context: ExecutionContext,
    messages: list[dict[str, Any]],
    *,
    default_temperature: float,
) -> tuple[ModelInvocationResult, str]:
    if context.models is None:
        raise RuntimeError("模型服务不可用")
    candidates = _model_candidates(config)
    last_error = "所有候选模型均调用失败"
    for index, candidate in enumerate(candidates):
        model_id = candidate.get("modelId")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        try:
            result = await context.models.invoke(
                model_id,
                {
                    "messages": messages,
                    "temperature": to_float(
                        candidate.get("temperature", default_temperature),
                        default_temperature,
                        context,
                    ),
                    "maxTokens": to_int(
                        candidate.get("maxTokens", 2000), 2000, context
                    ),
                    "timeoutSeconds": to_float(
                        candidate.get("timeoutSeconds", 180), 180, context
                    ),
                },
            )
            if not isinstance(result, ModelInvocationResult):
                raise TypeError("模型服务返回格式异常")
            if not result.content.strip():
                raise ValueError("AI返回内容为空")
            return result, model_id
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            last_error = str(error) or "模型调用失败"
            if index + 1 < len(candidates):
                await context.send_progress(
                    f"模型[{index + 1}/{len(candidates)}]调用失败，尝试切换下一个…",
                    "warning",
                )
    raise RuntimeError(last_error)


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
        try:
            result, model_id = await self._invoke(config, context)
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=str(error) or "模型调用失败")
        variable_name = config.get("variableName", "")
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

    async def _invoke(
        self,
        config: Mapping[str, Any],
        context: ExecutionContext,
    ) -> tuple[ModelInvocationResult, str]:
        system_prompt = self.get_text(config.get("systemPrompt", ""), context)
        user_prompt = self.get_text(config.get("userPrompt", ""), context)
        if not user_prompt:
            raise ValueError("用户提示词不能为空")
        return await invoke_managed_chat(
            config,
            context,
            system_prompt,
            user_prompt,
            default_temperature=0.7,
        )


def _resolve_vision_image(raw: Any) -> tuple[str | None, str | None]:
    text = str(raw or "").strip()
    if not text:
        return None, None
    if text.startswith("data:"):
        return (text.split(",", 1)[1] if "," in text else None), None
    if text.startswith(("http://", "https://")):
        return None, text
    try:
        candidate = Path(text)
        if candidate.is_file():
            return base64.b64encode(candidate.read_bytes()).decode("utf-8"), None
    except (OSError, ValueError):
        pass
    return None, None


class AIVisionExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "ai_vision"

    def requires_browser_for(self, config: dict[str, Any]) -> bool:
        return config.get("imageSource", "element") in {"element", "screenshot"}

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(config.get("modelId"), str) or not config["modelId"].strip():
            return False, "请选择主应用中的模型"
        if not isinstance(config.get("userPrompt"), str) or not config[
            "userPrompt"
        ].strip():
            return False, "提问内容不能为空"
        return True, ""

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        user_prompt = self.get_text(config.get("userPrompt", ""), context)
        if not user_prompt:
            return ModuleResult(success=False, error="提问内容不能为空")
        image_source = self.get_text(config.get("imageSource", "element"), context)
        try:
            image_base64, image_url = await self._image(config, context, image_source)
            if not image_base64 and not image_url:
                return ModuleResult(success=False, error="无法获取图片数据")
            content: list[dict[str, Any]] = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            f"data:image/png;base64,{image_base64}"
                            if image_base64
                            else image_url
                        )
                    },
                },
                {"type": "text", "text": user_prompt},
            ]
            result, model_id = await invoke_managed_messages(
                config,
                context,
                [{"role": "user", "content": content}],
                default_temperature=0.2,
            )
        except Exception as error:  # noqa: BLE001 - provider/browser errors become node errors.
            return ModuleResult(success=False, error=str(error) or "AI视觉调用失败")

        variable_name = config.get("variableName", "") or config.get(
            "resultVariable", ""
        )
        if isinstance(variable_name, str) and variable_name:
            context.set_variable(variable_name, result.content)
        preview = (
            f"{result.content[:100]}..."
            if len(result.content) > 100
            else result.content
        )
        return ModuleResult(
            success=True,
            message=f"AI视觉回复: {preview}",
            data={
                "response": result.content,
                "reasoning": result.reasoning or None,
                "model": result.model_key,
                "modelId": model_id,
                "image_source": image_source,
                "usage": result.usage,
            },
        )

    async def _image(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
        image_source: str,
    ) -> tuple[str | None, str | None]:
        if image_source in {"element", "screenshot"}:
            if context.browser is None:
                raise RuntimeError("没有打开的页面")
            page = context.browser.current_page()
            if image_source == "screenshot":
                screenshot = await page.screenshot(full_page=False)
                return base64.b64encode(screenshot).decode("utf-8"), None
            selector = self.get_text(config.get("imageSelector", ""), context)
            if not selector:
                raise ValueError("请指定图片元素选择器")
            element = page.locator(selector).first
            await element.wait_for(
                state="visible",
                timeout_ms=to_float(config.get("timeout", 30), 30, context) * 1000,
            )
            if await element.evaluate("el => el.tagName.toLowerCase()") == "img":
                source = await element.get_attribute("src")
                if source and source.startswith("data:"):
                    return _resolve_vision_image(source)
                if source and source.startswith(("http://", "https://")):
                    return None, source
            screenshot = await element.screenshot()
            return base64.b64encode(screenshot).decode("utf-8"), None
        if image_source == "url":
            raw = self.get_text(config.get("imageUrl", ""), context)
            resolved = _resolve_vision_image(raw)
            if resolved == (None, None):
                raise ValueError(
                    f"图片地址无效：既不是 http(s) 网址，本地也找不到该文件：{raw}"
                )
            return resolved
        if image_source == "variable":
            name = config.get("imageVariable", "")
            if not isinstance(name, str) or not name:
                raise ValueError("请指定图片变量名")
            value = context.get_variable(name)
            if not value:
                raise ValueError(f"变量 '{name}' 不存在或为空")
            image_base64, image_url = _resolve_vision_image(value)
            return (image_base64 or str(value), image_url)
        raise ValueError(f"不支持的图片来源: {image_source}")
