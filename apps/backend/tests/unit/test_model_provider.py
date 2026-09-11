import json

import httpx
import pytest

from autoflow.domain.models import ModelError, ProviderConnection
from autoflow.providers.model import HttpModelProvider, normalize_base_url


def connection(
    kind="openai-compatible",
    *,
    preset="custom-openai-compatible",
    url="https://api.example/v1",
):
    return ProviderConnection(preset, kind, url)


@pytest.mark.asyncio
async def test_openai_discovery_preserves_query_and_normalizes_context():
    async def handler(request):
        assert str(request.url) == "https://api.example/v1/models?region=cn"
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "z", "owned_by": "vendor"},
                    {"id": "a", "display_name": "A", "max_input_tokens": True},
                ]
            },
        )

    gateway = HttpModelProvider(transport=httpx.MockTransport(handler))
    result = await gateway.discover(
        connection(url="https://api.example/v1?region=cn"), "secret"
    )
    assert [item.model_key for item in result.items] == ["a", "z"]
    assert result.items[0].context_window is None
    assert result.endpoint == "https://api.example/v1/models"


@pytest.mark.asyncio
@pytest.mark.parametrize("preset", ["ollama", "custom-openai-compatible"])
async def test_optional_key_has_no_authorization_and_redirect_is_not_followed(preset):
    calls = []

    async def handler(request):
        calls.append(request)
        assert "authorization" not in request.headers
        return httpx.Response(302, headers={"location": "https://other.example/models"})

    gateway = HttpModelProvider(transport=httpx.MockTransport(handler))
    with pytest.raises(ModelError) as caught:
        await gateway.discover(connection(preset=preset), "  ")
    assert caught.value.code == "MODEL_PROVIDER_REQUEST_FAILED"
    assert caught.value.details == {"status": 302}
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_anthropic_and_gemini_protocols():
    calls = []

    async def handler(request):
        calls.append(request)
        if request.url.host == "api.anthropic.com":
            assert request.headers["x-api-key"] == "ak"
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert request.url.params["limit"] == "1000"
            return httpx.Response(
                200, json={"data": [{"id": "claude", "max_input_tokens": 200000}]}
            )
        assert "authorization" not in request.headers
        assert request.url.params["key"] == "gk"
        assert request.url.params["pageSize"] == "1000"
        return httpx.Response(
            200,
            json={"models": [{"name": "models/gemini", "inputTokenLimit": 1000000}]},
        )

    gateway = HttpModelProvider(transport=httpx.MockTransport(handler))
    anthropic = await gateway.discover(
        ProviderConnection("anthropic", "anthropic", None), "ak"
    )
    gemini = await gateway.discover(ProviderConnection("gemini", "gemini", None), "gk")
    assert anthropic.items[0].model_key == "claude"
    assert gemini.items[0].model_key == "gemini"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_qwen_replaces_path_but_keeps_custom_host_and_query():
    async def handler(request):
        assert request.url.host == "private.example"
        assert request.url.path == "/api/v1/models"
        assert dict(request.url.params) == {"tenant": "one", "page_size": "500"}
        return httpx.Response(
            200,
            json={
                "output": {
                    "models": [
                        {
                            "model": "qwen-plus",
                            "name": "Qwen Plus",
                            "provider": "qwen",
                            "model_info": {"context_window": 32768},
                        }
                    ]
                }
            },
        )

    gateway = HttpModelProvider(transport=httpx.MockTransport(handler))
    result = await gateway.discover(
        connection(
            preset="qwen", url="https://private.example/compatible/v1?tenant=one"
        ),
        "key",
    )
    assert result.items[0].context_window == 32768


def test_normalize_trims_only_path_and_preserves_query_value_slash():
    assert (
        normalize_base_url(connection(url="https://example.test/v1/?prefix=/"))
        == "https://example.test/v1?prefix=/"
    )


@pytest.mark.asyncio
async def test_protocol_query_parameters_override_base_url_duplicates():
    async def handler(request):
        assert request.url.params.get_list("limit") == ["1000"]
        return httpx.Response(200, json={"data": []})

    gateway = HttpModelProvider(transport=httpx.MockTransport(handler))
    await gateway.discover(
        ProviderConnection(
            "anthropic", "anthropic", "https://api.anthropic.com/v1?limit=1"
        ),
        "key",
    )


@pytest.mark.asyncio
async def test_client_security_and_timeout_options_are_explicit():
    seen = []

    def factory(**kwargs):
        seen.append(kwargs)
        return httpx.AsyncClient(**kwargs)

    async def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    gateway = HttpModelProvider(
        transport=httpx.MockTransport(handler), client_factory=factory
    )
    await gateway.discover(connection(), "key")
    await gateway.test_model(connection(), "key", "sample")
    assert [
        (item["trust_env"], item["follow_redirects"], item["timeout"]) for item in seen
    ] == [(False, False, 15), (False, False, 30)]


@pytest.mark.asyncio
async def test_generation_payload_encoding_and_preview_limits():
    async def handler(request):
        assert (
            request.url.raw_path.decode()
            .split("?", 1)[0]
            .endswith("/models/name%2Fwith%20space:generateContent")
        )
        payload = json.loads(request.content)
        assert payload["contents"][0]["parts"][0]["text"] == "只回复 OK"
        assert payload["generationConfig"]["maxOutputTokens"] == 16
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "o" * 300},
                                {"text": "r" * 2100, "thought": True},
                            ]
                        }
                    }
                ]
            },
        )

    gateway = HttpModelProvider(transport=httpx.MockTransport(handler))
    result = await gateway.test_model(
        ProviderConnection("gemini", "gemini", None), "key", "name/with space"
    )
    assert len(result.output_preview) == 240
    assert len(result.reasoning_preview) == 2000
    assert "key=" not in result.endpoint


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        (401, "MODEL_PROVIDER_AUTH_FAILED"),
        (403, "MODEL_PROVIDER_AUTH_FAILED"),
        (404, "MODEL_PROVIDER_ENDPOINT_NOT_FOUND"),
        (429, "MODEL_PROVIDER_RATE_LIMITED"),
        (500, "MODEL_PROVIDER_REQUEST_FAILED"),
    ],
)
async def test_http_errors_are_fixed_and_redacted(status, code):
    async def handler(_request):
        return httpx.Response(
            status,
            text="secret https://user:pass@example?key=secret",
            headers={"retry-after": "9"},
        )

    with pytest.raises(ModelError) as caught:
        await HttpModelProvider(transport=httpx.MockTransport(handler)).discover(
            connection(), "secret"
        )
    assert caught.value.code == code
    rendered = f"{caught.value} {caught.value.details!r}"
    assert "secret" not in rendered and "example" not in rendered
    if status == 429:
        assert caught.value.details["retryAfterSeconds"] == 9


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"unexpected": []}),
        httpx.Response(200, content=b" " * (8 * 1024 * 1024 + 1)),
    ],
)
async def test_invalid_and_oversized_responses_are_rejected(response):
    with pytest.raises(ModelError) as caught:
        await HttpModelProvider(
            transport=httpx.MockTransport(lambda _request: response)
        ).discover(connection(), "key")
    assert caught.value.code == "MODEL_PROVIDER_RESPONSE_INVALID"


@pytest.mark.asyncio
async def test_timeout_and_request_errors_do_not_expose_causes():
    for exception, code in [
        (httpx.ReadTimeout("secret timeout"), "MODEL_PROVIDER_TIMEOUT"),
        (httpx.ConnectError("secret host"), "MODEL_PROVIDER_UNREACHABLE"),
    ]:

        async def handler(request, error=exception):
            raise error

        with pytest.raises(ModelError) as caught:
            await HttpModelProvider(transport=httpx.MockTransport(handler)).discover(
                connection(), "secret"
            )
        assert caught.value.code == code
        assert "secret" not in f"{caught.value} {caught.value.details!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/models",
        "https://user:pass@example/v1",
        "https://example/v1#fragment",
        "https://example/v1?API_KEY=secret",
        "https://example:99999/v1",
    ],
)
async def test_invalid_or_authenticating_base_urls_are_rejected(url):
    with pytest.raises(ModelError) as caught:
        await HttpModelProvider().discover(connection(url=url), "key")
    assert caught.value.code == "MODEL_PROVIDER_BASE_URL_INVALID"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,preset",
    [("anthropic", "ollama"), ("gemini", "ollama"), ("openai-compatible", None)],
)
async def test_required_key_policy_precedes_network(kind, preset):
    with pytest.raises(ModelError) as caught:
        await HttpModelProvider().discover(connection(kind, preset=preset), "  ")
    assert caught.value.code == "MODEL_PROVIDER_API_KEY_REQUIRED"
