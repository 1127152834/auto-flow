import httpx
import pytest
from autoflow.domain.models import ModelError
from autoflow.providers.model import HttpModelProvider
from autoflow.providers.model.workflow import WorkflowModelGateway


@pytest.mark.asyncio
async def test_gateway_resolves_only_parent_supplied_model_binding():
    async def handler(request):
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "完成"}}]}
        )

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


def test_gateway_rejects_malformed_parent_binding():
    with pytest.raises(ValueError, match="model binding"):
        WorkflowModelGateway([{"modelId": "model-1", "secret": "secret"}])
