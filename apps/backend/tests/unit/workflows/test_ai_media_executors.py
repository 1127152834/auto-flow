from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


class Models:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    async def invoke(self, _model_id: str, _payload: Mapping[str, Any]) -> Any:
        raise AssertionError("media nodes must not use the chat endpoint")

    async def invoke_media(
        self,
        model_id: str,
        payload: Mapping[str, Any],
        **_options: Any,
    ) -> Mapping[str, Any]:
        self.calls.append((model_id, payload))
        if payload["operation"] == "image":
            return {
                "modelKey": "image-model",
                "items": [
                    {"url": "https://cdn.example/image-1.png", "content": b"PNG1"},
                    {"url": "https://cdn.example/image-2.png", "content": b"PNG2"},
                ],
            }
        return {
            "modelKey": "video-model",
            "url": "https://cdn.example/video.mp4",
            "content": b"MP4",
        }


class Artifacts:
    def __init__(self) -> None:
        self.writes: list[tuple[str, bytes, str]] = []

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        self.writes.append((name, content, mime_type))
        return f"/runs/artifacts/{name}"

    async def write_binary_output(
        self,
        *,
        output_path: str,
        content: bytes,
        mime_type: str,
        expected_identity: str | None = None,
    ) -> str:
        assert expected_identity is None
        self.writes.append((output_path, content, mime_type))
        return f"/runs/artifacts/{output_path}"


@pytest.mark.asyncio
async def test_ai_generate_image_uses_managed_model_and_registered_artifacts():
    models, artifacts = Models(), Artifacts()
    context = ExecutionContext(
        variables={"subject": "一只猫"}, models=models, artifacts=artifacts
    )
    result = (
        await build_production_executor_registry()
        .get("ai_generate_image")
        .execute(
            {
                "modelId": "managed-image",
                "prompt": "{subject}",
                "negativePrompt": "模糊",
                "size": "1024x1024",
                "quality": "hd",
                "style": "natural",
                "n": 2,
                "savePath": "generated/output.png",
                "variableName": "images",
            },
            context,
        )
    )

    assert result.success is True
    assert models.calls == [
        (
            "managed-image",
            {
                "operation": "image",
                "provider": "openai",
                "prompt": "一只猫",
                "negativePrompt": "模糊",
                "size": "1024x1024",
                "quality": "hd",
                "style": "natural",
                "count": 2,
                "timeoutSeconds": 120.0,
                "download": True,
            },
        )
    ]
    assert artifacts.writes == [
        ("generated/output_1.png", b"PNG1", "image/png"),
        ("generated/output_2.png", b"PNG2", "image/png"),
    ]
    assert context.variables == {
        "subject": "一只猫",
        "images": [
            "/runs/artifacts/generated/output_1.png",
            "/runs/artifacts/generated/output_2.png",
        ],
    }
    assert result.data == {
        "urls": ["https://cdn.example/image-1.png", "https://cdn.example/image-2.png"],
        "paths": [
            "/runs/artifacts/generated/output_1.png",
            "/runs/artifacts/generated/output_2.png",
        ],
        "model": "image-model",
        "modelId": "managed-image",
    }


@pytest.mark.asyncio
async def test_ai_generate_video_uses_managed_model_and_registered_artifact():
    models, artifacts = Models(), Artifacts()
    context = ExecutionContext(models=models, artifacts=artifacts)
    result = (
        await build_production_executor_registry()
        .get("ai_generate_video")
        .execute(
            {
                "modelId": "managed-video",
                "prompt": "海上日出",
                "duration": 8,
                "aspectRatio": "16:9",
                "fps": 30,
                "savePath": "generated/video.mp4",
                "variableName": "video",
            },
            context,
        )
    )

    assert result.success is True
    assert models.calls[0] == (
        "managed-video",
        {
            "operation": "video",
            "provider": "runway",
            "prompt": "海上日出",
            "duration": 8,
            "aspectRatio": "16:9",
            "fps": 30,
            "timeoutSeconds": 300.0,
            "download": True,
        },
    )
    assert artifacts.writes == [("generated/video.mp4", b"MP4", "video/mp4")]
    assert context.variables["video"] == "/runs/artifacts/generated/video.mp4"
    assert result.data == {
        "url": "https://cdn.example/video.mp4",
        "path": "/runs/artifacts/generated/video.mp4",
        "model": "video-model",
        "modelId": "managed-video",
    }


@pytest.mark.parametrize("module_type", ["ai_generate_image", "ai_generate_video"])
def test_ai_media_nodes_require_managed_model_and_reject_legacy_secret_only(
    module_type: str,
):
    executor = build_production_executor_registry().get(module_type)
    valid, message = executor.validate_config(
        {"apiKey": "legacy-secret", "apiBase": "https://legacy.invalid", "prompt": "x"}
    )

    assert valid is False
    assert message == "请选择主应用中的模型"
