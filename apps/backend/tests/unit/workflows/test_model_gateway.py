import asyncio

import httpx
import pytest

from autoflow.domain.models import ModelError
from autoflow.providers.model import HttpModelProvider
from autoflow.providers.model.workflow import WorkflowModelGateway


@pytest.mark.asyncio
async def test_gateway_resolves_only_parent_supplied_model_binding():
    async def handler(request):
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(200, json={"choices": [{"message": {"content": "完成"}}]})

    gateway = WorkflowModelGateway(
        [
            {
                "modelId": "model-1",
                "modelKey": "remote-model",
                "presetId": "custom-openai-compatible",
                "providerKind": "openai-compatible",
                "baseUrl": "https://model.example/v1",
                "secret": "secret",
            }
        ],
        HttpModelProvider(transport=httpx.MockTransport(handler)),
    )

    result = await gateway.invoke(
        "model-1", {"messages": [{"role": "user", "content": "执行"}]}
    )

    assert (result.model_key, result.content) == ("remote-model", "完成")
    assert "secret" not in repr(gateway)
    with pytest.raises(ModelError) as missing:
        await gateway.invoke(
            "other", {"messages": [{"role": "user", "content": "执行"}]}
        )
    assert missing.value.code == "MODEL_NOT_AVAILABLE_FOR_RUN"


@pytest.mark.asyncio
async def test_gateway_generates_media_with_parent_supplied_model_binding():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer secret"
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(
                200,
                json={"data": [{"b64_json": "UE5H"}]},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    gateway = WorkflowModelGateway(
        [
            {
                "modelId": "model-1",
                "modelKey": "image-model",
                "presetId": "custom-openai-compatible",
                "providerKind": "openai-compatible",
                "baseUrl": "https://model.example/v1",
                "secret": "secret",
            }
        ],
        HttpModelProvider(transport=httpx.MockTransport(handler)),
    )

    result = await gateway.invoke_media(
        "model-1",
        {
            "operation": "image",
            "prompt": "一只猫",
            "size": "1024x1024",
            "quality": "hd",
            "style": "natural",
            "count": 1,
            "download": True,
        },
    )

    assert result["modelKey"] == "image-model"
    assert result["items"] == [{"content": b"PNG"}]
    assert result["endpoint"] == "https://model.example/v1/images/generations"
    assert requests[0].url.path == "/v1/images/generations"


@pytest.mark.asyncio
async def test_gateway_polls_completed_video_immediately_and_downloads_result():
    requests: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(200, json={"id": "job-1"})
        if request.url.path.endswith("/generations/job-1"):
            return httpx.Response(
                200,
                json={"status": "completed", "url": "https://model.example/media.mp4"},
            )
        if request.url.path.endswith("/media.mp4"):
            return httpx.Response(200, content=b"MP4")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    gateway = WorkflowModelGateway(
        [
            {
                "modelId": "model-1",
                "modelKey": "video-model",
                "presetId": "custom-openai-compatible",
                "providerKind": "openai-compatible",
                "baseUrl": "https://model.example/v1",
                "secret": "secret",
            }
        ],
        HttpModelProvider(transport=httpx.MockTransport(handler)),
    )

    async with asyncio.timeout(0.2):
        result = await gateway.invoke_media(
            "model-1",
            {
                "operation": "video",
                "prompt": "海上日出",
                "duration": 5,
                "aspectRatio": "16:9",
                "fps": 24,
                "download": True,
            },
        )

    assert result["url"] == "https://model.example/media.mp4"
    assert result["content"] == b"MP4"
    assert requests == [
        ("POST", "/v1/generations"),
        ("GET", "/v1/generations/job-1"),
        ("GET", "/media.mp4"),
    ]


@pytest.mark.asyncio
async def test_gateway_preserves_stability_image_protocol_with_managed_secret():
    request_body: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/generation/stable-xl/text-to-image"
        assert request.headers["authorization"] == "Bearer secret"
        request_body.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={"artifacts": [{"base64": "UE5H"}]})

    gateway = WorkflowModelGateway(
        [
            {
                "modelId": "model-1",
                "modelKey": "stable-xl",
                "presetId": "custom-openai-compatible",
                "providerKind": "openai-compatible",
                "baseUrl": "https://stability.example/v1",
                "secret": "secret",
            }
        ],
        HttpModelProvider(transport=httpx.MockTransport(handler)),
    )

    result = await gateway.invoke_media(
        "model-1",
        {
            "operation": "image",
            "provider": "stability",
            "prompt": "猫",
            "negativePrompt": "模糊",
            "size": "1024x768",
            "count": 1,
        },
    )

    assert request_body["text_prompts"] == [
        {"text": "猫", "weight": 1.0},
        {"text": "模糊", "weight": -1.0},
    ]
    assert (request_body["width"], request_body["height"]) == (1024, 768)
    assert result["items"] == [{"content": b"PNG"}]


@pytest.mark.asyncio
async def test_gateway_uses_managed_base_url_for_custom_video_protocol():
    requests: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.method == "POST":
            assert request.headers["authorization"] == "Bearer secret"
            return httpx.Response(
                200, json={"video_url": "https://model.example/video.mp4"}
            )
        return httpx.Response(200, content=b"MP4")

    gateway = WorkflowModelGateway(
        [
            {
                "modelId": "model-1",
                "modelKey": "video-model",
                "presetId": "custom-openai-compatible",
                "providerKind": "openai-compatible",
                "baseUrl": "https://model.example/media",
                "secret": "secret",
            }
        ],
        HttpModelProvider(transport=httpx.MockTransport(handler)),
    )

    result = await gateway.invoke_media(
        "model-1",
        {
            "operation": "video",
            "provider": "custom",
            "prompt": "海上日出",
            "download": True,
        },
    )

    assert result["url"] == "https://model.example/video.mp4"
    assert result["content"] == b"MP4"
    assert requests == [("POST", "/media"), ("GET", "/video.mp4")]


@pytest.mark.asyncio
async def test_gateway_cancels_pending_video_poll_without_waiting_for_timeout():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": "job-1"})
        return httpx.Response(200, json={"status": "pending"})

    gateway = WorkflowModelGateway(
        [
            {
                "modelId": "model-1",
                "modelKey": "video-model",
                "presetId": "custom-openai-compatible",
                "providerKind": "openai-compatible",
                "baseUrl": "https://model.example/v1",
                "secret": "secret",
            }
        ],
        HttpModelProvider(transport=httpx.MockTransport(handler)),
    )
    checks = 0

    def check_cancelled() -> None:
        nonlocal checks
        checks += 1
        if checks >= 3:
            raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        await gateway.invoke_media(
            "model-1",
            {"operation": "video", "prompt": "海上日出"},
            check_cancelled=check_cancelled,
        )
    assert checks == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "provider"),
    [("image", "midjourney"), ("video", "pika")],
)
async def test_gateway_rejects_unsupported_media_protocol(
    operation: str, provider: str
):
    gateway = WorkflowModelGateway(
        [
            {
                "modelId": "model-1",
                "modelKey": "media-model",
                "presetId": "custom-openai-compatible",
                "providerKind": "openai-compatible",
                "baseUrl": "https://model.example/v1",
                "secret": "secret",
            }
        ],
        HttpModelProvider(transport=httpx.MockTransport(lambda _request: None)),
    )

    with pytest.raises(ModelError) as unsupported:
        await gateway.invoke_media(
            "model-1",
            {"operation": operation, "provider": provider, "prompt": "测试"},
        )

    assert unsupported.value.code == "MODEL_PROVIDER_UNSUPPORTED_OPERATION"


def test_gateway_rejects_malformed_parent_binding():
    with pytest.raises(ValueError, match="model binding"):
        WorkflowModelGateway([{"modelId": "model-1", "secret": "secret"}])
