from __future__ import annotations

import asyncio
import base64
import json
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx

from autoflow.domain.models import (
    DiscoveryResult,
    ModelError,
    ModelInvocationResult,
    ModelTestResult,
    ProviderConnection,
    RemoteModel,
)
from autoflow.domain.models.validation import normalize_base_url as _normalize_base_url
from autoflow.domain.models.validation import validate_connection

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_MEDIA_BYTES = 64 * 1024 * 1024
MAX_SAFE_INTEGER = 9_007_199_254_740_991


def normalize_base_url(connection: ProviderConnection) -> str:
    return _normalize_base_url(connection)


class HttpModelProvider:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self._transport = transport
        self._client_factory = client_factory

    async def discover(
        self, connection: ProviderConnection, secret: str
    ) -> DiscoveryResult:
        base_url = validate_connection(connection, secret)
        headers = _headers(connection, secret)
        params: dict[str, str | int] = {}
        started = time.perf_counter()
        if connection.preset_id == "openrouter":
            key_info = await self._request(
                "GET",
                _append_path(base_url, "key"),
                headers,
                {},
                None,
                15,
                "验证 OpenRouter API Key",
            )
            if not isinstance(key_info.get("data"), dict):
                raise _invalid("验证 OpenRouter API Key")
        if connection.preset_id == "qwen":
            parsed = urlsplit(base_url)
            endpoint = urlunsplit(
                (parsed.scheme, parsed.netloc, "/api/v1/models", parsed.query, "")
            )
            params["page_size"] = 500
        else:
            endpoint = _append_path(base_url, "models")
            if connection.provider_kind == "gemini":
                params.update(pageSize=1000, key=secret)
            elif connection.provider_kind == "anthropic":
                params["limit"] = 1000
        body = await self._request(
            "GET", endpoint, headers, params, None, 15, "获取模型列表"
        )
        items = _normalize_models(connection, body)
        latency = round((time.perf_counter() - started) * 1000, 2)
        return DiscoveryResult(
            tuple(items),
            latency,
            _safe_endpoint(endpoint),
            f"连接正常，发现 {len(items)} 个模型",
        )

    async def test_model(
        self, connection: ProviderConnection, secret: str, model_key: str
    ) -> ModelTestResult:
        base_url = validate_connection(connection, secret)
        headers = _headers(connection, secret)
        params: dict[str, str | int] = {}
        payload: dict[str, Any]
        if connection.provider_kind == "gemini":
            encoded = quote(model_key, safe="-._")
            endpoint = _append_path(base_url, f"models/{encoded}:generateContent")
            params["key"] = secret
            payload = {
                "contents": [{"parts": [{"text": "只回复 OK"}]}],
                "generationConfig": {"maxOutputTokens": 16},
            }
        elif connection.provider_kind == "anthropic":
            endpoint = _append_path(base_url, "messages")
            payload = {
                "model": model_key,
                "max_tokens": 16,
                "messages": [{"role": "user", "content": "只回复 OK"}],
            }
        else:
            endpoint = _append_path(base_url, "chat/completions")
            token_key = (
                "max_completion_tokens"
                if connection.provider_kind == "openai"
                else "max_tokens"
            )
            payload = {
                "model": model_key,
                "messages": [{"role": "user", "content": "只回复 OK"}],
                token_key: 16,
                "stream": False,
            }
        started = time.perf_counter()
        body = await self._request(
            "POST", endpoint, headers, params, payload, 30, "模型测试"
        )
        output, reasoning = _previews(connection.provider_kind, body)
        return ModelTestResult(
            round((time.perf_counter() - started) * 1000, 2),
            _safe_endpoint(endpoint),
            output[:240],
            reasoning[:2000],
            "模型调用成功",
        )

    async def invoke(
        self,
        connection: ProviderConnection,
        secret: str,
        model_key: str,
        payload: Mapping[str, Any],
    ) -> ModelInvocationResult:
        base_url = validate_connection(connection, secret)
        messages = payload.get("messages")
        if not isinstance(messages, list) or not all(
            isinstance(item, dict) for item in messages
        ):
            raise _invalid("模型调用")
        temperature = payload.get("temperature", 0.7)
        max_tokens = payload.get("maxTokens", payload.get("max_tokens", 2000))
        timeout = payload.get("timeoutSeconds", 180)
        tools = payload.get("tools")
        tool_choice = payload.get("toolChoice", payload.get("tool_choice", "auto"))
        if (
            not isinstance(temperature, (int, float))
            or isinstance(temperature, bool)
            or not isinstance(max_tokens, int)
            or isinstance(max_tokens, bool)
            or max_tokens <= 0
            or not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout <= 0
        ):
            raise _invalid("模型调用")
        if tools is not None and (
            not isinstance(tools, list)
            or not all(isinstance(item, dict) for item in tools)
            or not isinstance(tool_choice, (str, dict))
        ):
            raise _invalid("模型调用")
        if tools and connection.provider_kind in {"anthropic", "gemini"}:
            raise ModelError(
                "MODEL_PROVIDER_UNSUPPORTED_OPERATION",
                "所选模型供应商暂不支持助手工具调用",
                422,
            )
        params: dict[str, str | int] = {}
        if connection.provider_kind == "gemini":
            endpoint = _append_path(
                base_url, f"models/{quote(model_key, safe='-._')}:generateContent"
            )
            params["key"] = secret
            body = _gemini_payload(messages, float(temperature), max_tokens)
        elif connection.provider_kind == "anthropic":
            endpoint = _append_path(base_url, "messages")
            body = _anthropic_payload(
                model_key, messages, float(temperature), max_tokens
            )
        else:
            endpoint = _append_path(base_url, "chat/completions")
            body = {
                "model": model_key,
                "messages": messages,
                "temperature": float(temperature),
                "max_tokens": max_tokens,
                "stream": False,
            }
            if tools:
                body.update(tools=tools, tool_choice=tool_choice)
        response = await self._request(
            "POST",
            endpoint,
            _headers(connection, secret),
            params,
            body,
            float(timeout),
            "模型调用",
        )
        content, reasoning = _previews(connection.provider_kind, response)
        tool_calls = _openai_tool_calls(response) if tools else ()
        if not content and reasoning:
            content = reasoning
        if not content and not tool_calls:
            raise _invalid("模型调用")
        usage = response.get("usage")
        return ModelInvocationResult(
            model_key,
            content,
            reasoning,
            dict(usage) if isinstance(usage, dict) else {},
            _safe_endpoint(endpoint),
            tool_calls,
        )

    async def invoke_media(
        self,
        connection: ProviderConnection,
        secret: str,
        model_key: str,
        payload: Mapping[str, Any],
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        validate_connection(connection, secret)
        if connection.provider_kind in {"anthropic", "gemini"}:
            raise ModelError(
                "MODEL_PROVIDER_UNSUPPORTED_OPERATION",
                "所选模型供应商不支持媒体生成",
                422,
            )
        operation = payload.get("operation")
        prompt = payload.get("prompt")
        timeout = payload.get("timeoutSeconds", 300)
        if (
            operation not in {"image", "video"}
            or not isinstance(prompt, str)
            or not prompt.strip()
            or not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout <= 0
        ):
            raise _invalid("媒体生成")
        check = check_cancelled or (lambda: None)
        check()
        if operation == "image":
            return await self._invoke_image(
                connection,
                secret,
                model_key,
                payload,
                float(timeout),
                check,
            )
        return await self._invoke_video(
            connection,
            secret,
            model_key,
            payload,
            float(timeout),
            check,
        )

    async def _invoke_image(
        self,
        connection: ProviderConnection,
        secret: str,
        model_key: str,
        payload: Mapping[str, Any],
        timeout: float,
        check_cancelled: Callable[[], None],
    ) -> dict[str, Any]:
        count = payload.get("count", 1)
        if (
            not isinstance(count, int)
            or isinstance(count, bool)
            or not 1 <= count <= 10
        ):
            raise _invalid("AI生图")
        provider = payload.get("provider", "openai")
        if provider not in {"openai", "stability"}:
            raise ModelError(
                "MODEL_PROVIDER_UNSUPPORTED_OPERATION",
                f"不支持的AI提供商: {provider}",
                422,
            )
        if provider == "stability":
            return await self._invoke_stability_image(
                connection,
                secret,
                model_key,
                payload,
                count,
                timeout,
                check_cancelled,
            )
        endpoint = _append_path(normalize_base_url(connection), "images/generations")
        body = {
            "model": model_key,
            "prompt": payload["prompt"],
            "n": count,
            "size": payload.get("size", "1024x1024"),
            "quality": payload.get("quality", "standard"),
            "style": payload.get("style", "vivid"),
        }
        response = await self._request(
            "POST",
            endpoint,
            _headers(connection, secret),
            {},
            body,
            timeout,
            "AI生图",
        )
        raw_items = response.get("data")
        if not isinstance(raw_items, list) or not raw_items:
            raise _invalid("AI生图")
        items: list[dict[str, Any]] = []
        for raw in raw_items:
            check_cancelled()
            if not isinstance(raw, dict):
                raise _invalid("AI生图")
            url = raw.get("url")
            encoded = raw.get("b64_json")
            item: dict[str, Any] = {}
            if isinstance(url, str) and url:
                item["url"] = url
                if payload.get("download") is True:
                    item["content"] = await self._request_bytes(
                        url, timeout, "下载生成图片", check_cancelled
                    )
            elif isinstance(encoded, str) and encoded:
                try:
                    item["content"] = base64.b64decode(encoded, validate=True)
                except ValueError:
                    raise _invalid("AI生图") from None
            else:
                raise _invalid("AI生图")
            items.append(item)
        return {
            "modelKey": model_key,
            "endpoint": _safe_endpoint(endpoint),
            "items": items,
        }

    async def _invoke_stability_image(
        self,
        connection: ProviderConnection,
        secret: str,
        model_key: str,
        payload: Mapping[str, Any],
        count: int,
        timeout: float,
        check_cancelled: Callable[[], None],
    ) -> dict[str, Any]:
        try:
            width_text, height_text = str(payload.get("size", "1024x1024")).split(
                "x", 1
            )
            width, height = int(width_text), int(height_text)
        except (TypeError, ValueError):
            raise _invalid("AI生图") from None
        if width <= 0 or height <= 0:
            raise _invalid("AI生图")
        base_url = normalize_base_url(connection)
        prefix = (
            "generation"
            if urlsplit(base_url).path.rstrip("/").endswith("/v1")
            else "v1/generation"
        )
        endpoint = _append_path(
            base_url, f"{prefix}/{quote(model_key, safe='-._')}/text-to-image"
        )
        prompts = [{"text": payload["prompt"], "weight": 1.0}]
        negative = payload.get("negativePrompt")
        if isinstance(negative, str) and negative:
            prompts.append({"text": negative, "weight": -1.0})
        response = await self._request(
            "POST",
            endpoint,
            _headers(connection, secret),
            {},
            {
                "text_prompts": prompts,
                "cfg_scale": 7,
                "height": height,
                "width": width,
                "samples": count,
                "steps": 30,
            },
            timeout,
            "AI生图",
        )
        artifacts = response.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise _invalid("AI生图")
        items: list[dict[str, Any]] = []
        for artifact in artifacts:
            check_cancelled()
            encoded = artifact.get("base64") if isinstance(artifact, dict) else None
            if not isinstance(encoded, str) or not encoded:
                raise _invalid("AI生图")
            try:
                items.append({"content": base64.b64decode(encoded, validate=True)})
            except ValueError:
                raise _invalid("AI生图") from None
        return {
            "modelKey": model_key,
            "endpoint": _safe_endpoint(endpoint),
            "items": items,
        }

    async def _invoke_video(
        self,
        connection: ProviderConnection,
        secret: str,
        model_key: str,
        payload: Mapping[str, Any],
        timeout: float,
        check_cancelled: Callable[[], None],
    ) -> dict[str, Any]:
        provider = payload.get("provider", "runway")
        if provider not in {"runway", "custom"}:
            raise ModelError(
                "MODEL_PROVIDER_UNSUPPORTED_OPERATION",
                f"不支持的AI提供商: {provider}",
                422,
            )
        endpoint = (
            normalize_base_url(connection)
            if provider == "custom"
            else _append_path(normalize_base_url(connection), "generations")
        )
        response = await self._request(
            "POST",
            endpoint,
            _headers(connection, secret),
            {},
            {
                "model": model_key,
                "prompt": payload["prompt"],
                "duration": payload.get("duration", 5),
                "aspect_ratio": payload.get("aspectRatio", "16:9"),
                "fps": payload.get("fps", 24),
            },
            timeout,
            "AI生视频",
        )
        if provider == "custom":
            url = response.get("url") or response.get("video_url")
            if not isinstance(url, str) or not url:
                raise _invalid("AI生视频")
            custom_result: dict[str, Any] = {
                "modelKey": model_key,
                "endpoint": _safe_endpoint(endpoint),
                "url": url,
            }
            if payload.get("download") is True:
                custom_result["content"] = await self._request_bytes(
                    url, timeout, "下载生成视频", check_cancelled
                )
            return custom_result
        task_id = response.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise _invalid("AI生视频")
        poll_endpoint = _append_path(endpoint, quote(task_id, safe="-._"))
        for _attempt in range(60):
            check_cancelled()
            status = await self._request(
                "GET",
                poll_endpoint,
                _headers(connection, secret),
                {},
                None,
                timeout,
                "查询视频生成状态",
            )
            state = status.get("status")
            if state == "failed":
                message = status.get("error")
                raise ModelError(
                    "MODEL_MEDIA_GENERATION_FAILED",
                    str(message or "AI生视频失败"),
                    409,
                )
            if state != "completed":
                await _cancel_aware_sleep(5, check_cancelled)
                continue
            url = status.get("url") or status.get("video_url")
            if not isinstance(url, str) or not url:
                raise _invalid("AI生视频")
            completed_result: dict[str, Any] = {
                "modelKey": model_key,
                "endpoint": _safe_endpoint(endpoint),
                "url": url,
            }
            if payload.get("download") is True:
                completed_result["content"] = await self._request_bytes(
                    url, timeout, "下载生成视频", check_cancelled
                )
            return completed_result
        raise ModelError("MODEL_PROVIDER_TIMEOUT", "AI生视频超时", 504)

    async def _request_bytes(
        self,
        endpoint: str,
        timeout: float,
        action: str,
        check_cancelled: Callable[[], None],
    ) -> bytes:
        try:
            async with (
                self._client_factory(
                    timeout=timeout,
                    follow_redirects=True,
                    trust_env=False,
                    transport=self._transport,
                ) as client,
                client.stream("GET", endpoint) as response,
            ):
                if response.status_code >= 300:
                    await response.aclose()
                    _raise_status(response)
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    check_cancelled()
                    content.extend(chunk)
                    if len(content) > MAX_MEDIA_BYTES:
                        raise _invalid(action)
            return bytes(content)
        except ModelError:
            raise
        except httpx.TimeoutException:
            raise ModelError("MODEL_PROVIDER_TIMEOUT", f"{action}超时", 504) from None
        except httpx.RequestError:
            raise ModelError(
                "MODEL_PROVIDER_UNREACHABLE", f"{action}失败", 409
            ) from None

    async def _request(
        self,
        method: str,
        endpoint: str,
        headers: dict[str, str],
        params: dict[str, str | int],
        payload: dict[str, Any] | None,
        timeout: float,
        action: str,
    ) -> dict[str, Any]:
        try:
            endpoint = _with_params(endpoint, params)
            async with (
                self._client_factory(
                    timeout=timeout,
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                ) as client,
                client.stream(
                    method, endpoint, headers=headers, json=payload
                ) as response,
            ):
                if response.status_code >= 300:
                    await response.aclose()
                    _raise_status(response)
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise _invalid(action)
            body = json.loads(content)
            if not isinstance(body, dict):
                raise _invalid(action)
            return body
        except ModelError:
            raise
        except httpx.TimeoutException:
            raise ModelError(
                "MODEL_PROVIDER_TIMEOUT", f"{action}超时，请检查网络或 Base URL", 504
            ) from None
        except httpx.RequestError:
            raise ModelError(
                "MODEL_PROVIDER_UNREACHABLE", f"{action}失败：无法连接供应商", 409
            ) from None
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
            raise _invalid(action) from None


def _append_path(base_url: str, suffix: str) -> str:
    parsed = urlsplit(base_url)
    path = f"{parsed.path.rstrip('/')}/{suffix}"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


async def _cancel_aware_sleep(
    seconds: float, check_cancelled: Callable[[], None]
) -> None:
    remaining = seconds
    while remaining > 0:
        check_cancelled()
        interval = min(0.1, remaining)
        await asyncio.sleep(interval)
        remaining -= interval
    check_cancelled()


def _with_params(endpoint: str, params: dict[str, str | int]) -> str:
    if not params:
        return endpoint
    parsed = urlsplit(endpoint)
    existing: dict[str, str | int] = dict(
        parse_qsl(parsed.query, keep_blank_values=True)
    )
    existing.update(params)
    query = urlencode(existing)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def _safe_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    host = (
        f"[{parsed.hostname}]"
        if ":" in (parsed.hostname or "")
        else (parsed.hostname or "")
    )
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _headers(connection: ProviderConnection, secret: str) -> dict[str, str]:
    _validate_key(connection, secret)
    headers = {"content-type": "application/json"}
    if connection.provider_kind == "anthropic":
        headers.update({"x-api-key": secret, "anthropic-version": "2023-06-01"})
    elif connection.provider_kind != "gemini" and secret.strip():
        headers["authorization"] = f"Bearer {secret}"
    return headers


def _anthropic_payload(
    model_key: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    system = "\n".join(
        str(item.get("content") or "")
        for item in messages
        if item.get("role") == "system"
    ).strip()
    body: dict[str, Any] = {
        "model": model_key,
        "messages": [
            {**item, "content": _anthropic_content(item.get("content"))}
            for item in messages
            if item.get("role") in {"user", "assistant"}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system:
        body["system"] = system
    return body


def _gemini_payload(
    messages: list[dict[str, Any]], temperature: float, max_tokens: int
) -> dict[str, Any]:
    system = "\n".join(
        str(item.get("content") or "")
        for item in messages
        if item.get("role") == "system"
    ).strip()
    body: dict[str, Any] = {
        "contents": [
            {
                "role": "model" if item.get("role") == "assistant" else "user",
                "parts": _gemini_parts(item.get("content")),
            }
            for item in messages
            if item.get("role") in {"user", "assistant"}
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return body


def _data_image(url: str) -> tuple[str, str] | None:
    if not url.startswith("data:image/") or "," not in url:
        return None
    metadata, data = url[5:].split(",", 1)
    if ";base64" not in metadata:
        return None
    return metadata.split(";", 1)[0], data


def _anthropic_content(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    content: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            content.append({"type": "text", "text": item["text"]})
            continue
        image = item.get("image_url")
        url = image.get("url") if isinstance(image, dict) else None
        if item.get("type") != "image_url" or not isinstance(url, str):
            continue
        inline = _data_image(url)
        source = (
            {
                "type": "base64",
                "media_type": inline[0],
                "data": inline[1],
            }
            if inline
            else {"type": "url", "url": url}
        )
        content.append({"type": "image", "source": source})
    return content


def _gemini_parts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return [{"text": str(value or "")}]
    parts: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            parts.append({"text": item["text"]})
            continue
        image = item.get("image_url")
        url = image.get("url") if isinstance(image, dict) else None
        if item.get("type") != "image_url" or not isinstance(url, str):
            continue
        inline = _data_image(url)
        if inline:
            parts.append(
                {"inlineData": {"mimeType": inline[0], "data": inline[1]}}
            )
        else:
            parts.append(
                {"fileData": {"mimeType": "image/*", "fileUri": url}}
            )
    return parts


def _validate_key(connection: ProviderConnection, secret: str) -> None:
    if connection.provider_kind in {"anthropic", "gemini"} and not secret.strip():
        raise ModelError("MODEL_PROVIDER_API_KEY_REQUIRED", "该供应商需要 API Key", 422)
    if (
        connection.preset_id not in {"ollama", "custom-openai-compatible"}
        and not secret.strip()
    ):
        raise ModelError("MODEL_PROVIDER_API_KEY_REQUIRED", "该供应商需要 API Key", 422)


def _context_window(value: Any) -> int | None:
    return value if type(value) is int and 1 <= value <= MAX_SAFE_INTEGER else None


def _normalize_models(
    connection: ProviderConnection, body: dict[str, Any]
) -> list[RemoteModel]:
    if connection.preset_id == "qwen":
        output = body.get("output")
        source = output.get("models") if isinstance(output, dict) else None
    else:
        source = (
            body.get("models")
            if connection.provider_kind == "gemini"
            else body.get("data")
        )
    if not isinstance(source, list):
        raise _invalid("获取模型列表")
    items: list[RemoteModel] = []
    for raw in source:
        if not isinstance(raw, dict):
            continue
        if connection.preset_id == "qwen":
            raw_id = raw.get("model")
            info = raw.get("model_info")
            context = info.get("context_window") if isinstance(info, dict) else None
            owned_by = raw.get("provider") or "qwen"
            display = raw.get("name") or raw_id
        else:
            raw_id = (
                raw.get("name")
                if connection.provider_kind == "gemini"
                else raw.get("id")
            )
            context = (
                raw.get("inputTokenLimit")
                or raw.get("max_input_tokens")
                or raw.get("context_length")
            )
            owned_by = raw.get("owned_by")
            display = (
                raw.get("displayName")
                or raw.get("display_name")
                or raw.get("name")
                or raw_id
            )
        if not isinstance(raw_id, str) or not raw_id.strip():
            continue
        key = raw_id.removeprefix("models/").strip()
        items.append(RemoteModel(key, str(display), owned_by, _context_window(context)))
    return sorted(
        items, key=lambda item: (item.display_name.casefold(), item.model_key)
    )


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " ".join(
            item["text"]
            for item in value
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ).strip()
    return ""


def _openai_tool_calls(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    choices = body.get("choices")
    message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    raw_calls = message.get("tool_calls") if isinstance(message, dict) else None
    if raw_calls is None:
        return ()
    if not isinstance(raw_calls, list):
        raise _invalid("模型调用")
    calls: list[dict[str, Any]] = []
    for raw in raw_calls:
        function = raw.get("function") if isinstance(raw, dict) else None
        call_id = raw.get("id") if isinstance(raw, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        encoded = function.get("arguments") if isinstance(function, dict) else None
        if (
            not isinstance(call_id, str)
            or not call_id
            or not isinstance(name, str)
            or not name
            or not isinstance(encoded, str)
            or not encoded
        ):
            raise _invalid("模型调用")
        try:
            arguments = json.loads(encoded)
        except json.JSONDecodeError:
            raise _invalid("模型调用") from None
        if not isinstance(arguments, dict):
            raise _invalid("模型调用")
        calls.append({"id": call_id, "name": name, "arguments": arguments})
    return tuple(calls)


def _previews(kind: str, body: dict[str, Any]) -> tuple[str, str]:
    if kind == "gemini":
        candidates = body.get("candidates")
        if (
            isinstance(candidates, list)
            and candidates
            and isinstance(candidates[0], dict)
        ):
            content = candidates[0].get("content")
            parts = content.get("parts") if isinstance(content, dict) else None
            if isinstance(parts, list):
                return _text(
                    [p for p in parts if isinstance(p, dict) and not p.get("thought")]
                ), _text([p for p in parts if isinstance(p, dict) and p.get("thought")])
    elif kind == "anthropic":
        content = body.get("content")
        if isinstance(content, list):
            return _text(
                [p for p in content if isinstance(p, dict) and p.get("type") == "text"]
            ), " ".join(
                p["thinking"]
                for p in content
                if isinstance(p, dict)
                and p.get("type") == "thinking"
                and isinstance(p.get("thinking"), str)
            ).strip()
    else:
        choices = body.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                return _text(message.get("content")), _text(
                    message.get("reasoning_content") or message.get("reasoning")
                )
    raise _invalid("模型测试")


def _raise_status(response: httpx.Response) -> None:
    status = response.status_code
    if status in {401, 403}:
        raise ModelError(
            "MODEL_PROVIDER_AUTH_FAILED",
            "供应商拒绝认证，请检查 API Key",
            409,
            {"status": status},
        )
    if status == 404:
        raise ModelError(
            "MODEL_PROVIDER_ENDPOINT_NOT_FOUND",
            "供应商接口不存在，请检查 Base URL 或模型标识",
            409,
            {"status": status},
        )
    if status == 429:
        details: dict[str, Any] = {"status": status}
        retry_after = response.headers.get("retry-after")
        if retry_after and retry_after.isdigit():
            details["retryAfterSeconds"] = int(retry_after)
        raise ModelError(
            "MODEL_PROVIDER_RATE_LIMITED", "供应商触发速率或额度限制", 409, details
        )
    raise ModelError(
        "MODEL_PROVIDER_REQUEST_FAILED",
        f"供应商请求失败：远端返回 HTTP {status}",
        409,
        {"status": status},
    )


def _invalid(action: str) -> ModelError:
    return ModelError(
        "MODEL_PROVIDER_RESPONSE_INVALID", f"{action}失败：响应格式无效", 409
    )
