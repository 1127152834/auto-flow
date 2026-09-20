from __future__ import annotations

from typing import Any

import pytest
from autoflow.application.workflows.executors.text_to_speech import (
    TextToSpeechExecutor,
)
from autoflow.domain.workflows.execution import ExecutionContext, SpeechResult


class SpeechGateway:
    def __init__(self, result: SpeechResult) -> None:
        self.result = result
        self.requests: list[dict[str, Any]] = []

    async def speak(
        self,
        text: str,
        *,
        lang: str,
        rate: float,
        pitch: float,
        volume: float,
        timeout_seconds: float,
    ) -> SpeechResult:
        self.requests.append(
            {
                "text": text,
                "lang": lang,
                "rate": rate,
                "pitch": pitch,
                "volume": volume,
                "timeoutSeconds": timeout_seconds,
            }
        )
        return self.result


@pytest.mark.asyncio
async def test_text_to_speech_uses_renderer_with_source_defaults() -> None:
    speech = SpeechGateway(SpeechResult(True))
    context = ExecutionContext(variables={"message": "通知"}, speech=speech)
    executor = TextToSpeechExecutor()

    result = await executor.execute({"text": "{message}"}, context)

    assert result.success is True
    assert result.message == "已朗读文本: 通知"
    assert result.data == {"text": "通知", "lang": "zh-CN"}
    assert speech.requests == [
        {
            "text": "通知",
            "lang": "zh-CN",
            "rate": 1,
            "pitch": 1,
            "volume": 1,
            "timeoutSeconds": 60,
        }
    ]


@pytest.mark.asyncio
async def test_text_to_speech_reports_renderer_failure_without_platform_fallback() -> None:
    executor = TextToSpeechExecutor()
    context = ExecutionContext(speech=SpeechGateway(SpeechResult(False, "语音不可用")))

    result = await executor.execute({"text": "通知"}, context)

    assert result.success is False
    assert result.error == "文本朗读失败: 语音不可用"


@pytest.mark.asyncio
async def test_text_to_speech_requires_text_and_transport() -> None:
    executor = TextToSpeechExecutor()

    assert (await executor.execute({}, ExecutionContext())).error == "朗读文本不能为空"
    assert (
        await executor.execute({"text": "通知"}, ExecutionContext())
    ).error == "文本朗读服务不可用"
