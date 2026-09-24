"""WebRPA AI media executors adapted to AutoFlow managed models and artifacts.

Source: reference/WebRPA/backend/app/executors/ai_media.py@5ccb900e8dcf1530aae66f676d87593c416c7ebb
License: LICENSE.WebRPA
Changes: node secrets/endpoints are replaced by main-application model IDs and all
generated files pass through the workflow artifact boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float, to_int


def _cancel_check(context: ExecutionContext):  # type: ignore[no-untyped-def]
    return (
        context.cancellation.raise_if_cancelled
        if context.cancellation is not None
        else None
    )


def _numbered_path(raw: str, index: int, count: int, suffix: str) -> str:
    path = Path(raw)
    if count == 1:
        return str(path)
    actual_suffix = path.suffix or suffix
    stem = path.stem if path.suffix else path.name
    return str(path.with_name(f"{stem}_{index + 1}{actual_suffix}"))


async def _write_media(
    context: ExecutionContext,
    *,
    output_path: str,
    default_name: str,
    content: bytes,
    mime_type: str,
) -> str:
    writer = context.node_artifacts
    if writer is None:
        raise RuntimeError("媒体产物存储未配置")
    if output_path:
        return await writer.write_binary_output(
            output_path=output_path,
            content=content,
            mime_type=mime_type,
        )
    return await writer.write_bytes(
        name=default_name,
        content=content,
        mime_type=mime_type,
    )


class _AIManagedMediaExecutor(ModuleExecutor):
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(config.get("modelId"), str) or not config["modelId"].strip():
            return False, "请选择主应用中的模型"
        if not isinstance(config.get("prompt"), str) or not config["prompt"].strip():
            return False, "提示词不能为空"
        return True, ""

    async def _invoke(
        self,
        config: Mapping[str, Any],
        context: ExecutionContext,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if context.models is None:
            raise RuntimeError("模型服务不可用")
        model_id = config.get("modelId")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("请选择主应用中的模型")
        return await context.models.invoke_media(
            model_id,
            payload,
            check_cancelled=_cancel_check(context),
        )


class AIGenerateImageExecutor(_AIManagedMediaExecutor):
    @property
    def module_type(self) -> str:
        return "ai_generate_image"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        prompt = self.get_text(config.get("prompt", ""), context)
        if not prompt:
            return ModuleResult(success=False, error="提示词不能为空")
        save_path = self.get_text(config.get("savePath", ""), context)
        count = to_int(config.get("n", 1), 1, context)
        try:
            response = await self._invoke(
                config,
                context,
                {
                    "operation": "image",
                    "provider": self.get_text(
                        config.get("provider", "openai"), context
                    ),
                    "prompt": prompt,
                    "negativePrompt": self.get_text(
                        config.get("negativePrompt", ""), context
                    ),
                    "size": self.get_text(config.get("size", "1024x1024"), context),
                    "quality": self.get_text(
                        config.get("quality", "standard"), context
                    ),
                    "style": self.get_text(config.get("style", "vivid"), context),
                    "count": count,
                    "timeoutSeconds": to_float(
                        config.get("timeoutSeconds", 120), 120, context
                    ),
                    "download": bool(save_path),
                },
            )
            raw_items = response.get("items")
            if not isinstance(raw_items, list) or not raw_items:
                raise ValueError("模型未返回图片")
            urls: list[str] = []
            paths: list[str] = []
            values: list[str] = []
            for index, item in enumerate(raw_items):
                if not isinstance(item, Mapping):
                    raise TypeError("模型返回的图片格式无效")
                url = item.get("url")
                if isinstance(url, str) and url:
                    urls.append(url)
                content = item.get("content")
                if isinstance(content, bytes):
                    target = (
                        _numbered_path(save_path, index, len(raw_items), ".png")
                        if save_path
                        else "ai_image_"
                        + context.clock.now().strftime("%Y%m%d_%H%M%S")
                        + f"_{index + 1}.png"
                    )
                    path = await _write_media(
                        context,
                        output_path=target if save_path else "",
                        default_name=target,
                        content=content,
                        mime_type="image/png",
                    )
                    paths.append(path)
                    values.append(path)
                elif isinstance(url, str) and url:
                    values.append(url)
                else:
                    raise ValueError("模型返回的图片格式无效")
            variable_name = config.get("variableName", "ai_image_urls")
            if isinstance(variable_name, str) and variable_name:
                context.set_variable(variable_name, values)
            return ModuleResult(
                success=True,
                message=f"AI生图成功，生成 {len(values)} 张图片",
                data={
                    "urls": urls,
                    **({"paths": paths} if paths else {}),
                    "model": response.get("modelKey"),
                    "modelId": config["modelId"],
                },
            )
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=str(error) or "AI生图失败")


class AIGenerateVideoExecutor(_AIManagedMediaExecutor):
    @property
    def module_type(self) -> str:
        return "ai_generate_video"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        prompt = self.get_text(config.get("prompt", ""), context)
        if not prompt:
            return ModuleResult(success=False, error="提示词不能为空")
        save_path = self.get_text(config.get("savePath", ""), context)
        try:
            response = await self._invoke(
                config,
                context,
                {
                    "operation": "video",
                    "provider": self.get_text(
                        config.get("provider", "runway"), context
                    ),
                    "prompt": prompt,
                    "duration": to_int(config.get("duration", 5), 5, context),
                    "aspectRatio": self.get_text(
                        config.get("aspectRatio", "16:9"), context
                    ),
                    "fps": to_int(config.get("fps", 24), 24, context),
                    "timeoutSeconds": to_float(
                        config.get("timeoutSeconds", 300), 300, context
                    ),
                    "download": bool(save_path),
                },
            )
            url = response.get("url")
            if not isinstance(url, str) or not url:
                raise ValueError("模型未返回视频地址")
            value = url
            data: dict[str, Any] = {
                "url": url,
                "model": response.get("modelKey"),
                "modelId": config["modelId"],
            }
            content = response.get("content")
            if save_path:
                if not isinstance(content, bytes):
                    raise ValueError("生成视频下载失败")
                value = await _write_media(
                    context,
                    output_path=save_path,
                    default_name="ai_video.mp4",
                    content=content,
                    mime_type="video/mp4",
                )
                data["path"] = value
            variable_name = config.get("variableName", "ai_video_url")
            if isinstance(variable_name, str) and variable_name:
                context.set_variable(variable_name, value)
            return ModuleResult(success=True, message="AI生视频成功", data=data)
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=str(error) or "AI生视频失败")


AI_MEDIA_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    AIGenerateImageExecutor,
    AIGenerateVideoExecutor,
)
