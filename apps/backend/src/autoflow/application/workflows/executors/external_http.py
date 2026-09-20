"""HTTP executors migrated from WebRPA@5ccb900e.

Sources: backend/app/executors/advanced.py, webhook.py and notify_apprise.py.
License and adaptation record: LICENSE.WebRPA.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float


def _text(value: Any, context: ExecutionContext) -> str:
    resolved = context.resolve_value(value)
    return "" if resolved is None else str(resolved)


def _object(value: Any, context: ExecutionContext, *, strict: bool) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): context.resolve_value(item) for key, item in value.items()}
    text = _text(value, context).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        if strict:
            raise ValueError("JSON格式错误") from None
        return {}
    if not isinstance(parsed, dict):
        if strict:
            raise ValueError("JSON必须是对象")
        return {}
    return {str(key): item for key, item in parsed.items()}


def _cookies(value: Any, context: ExecutionContext) -> dict[str, str]:
    if isinstance(value, Mapping):
        return {str(key): _text(item, context) for key, item in value.items()}
    text = _text(value, context).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return {str(key): str(item) for key, item in parsed.items()}
    result: dict[str, str] = {}
    for part in text.split(";"):
        if "=" in part:
            key, item = part.split("=", 1)
            if key.strip():
                result[key.strip()] = item.strip()
    return result


async def _request(
    context: ExecutionContext, payload: dict[str, Any]
) -> Mapping[str, Any]:
    if context.external_integrations is None:
        raise RuntimeError("HTTP服务不可用")
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()
    response = await context.external_integrations.call("http", payload)
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()
    if not isinstance(response, Mapping):
        raise TypeError("HTTP服务返回格式异常")
    return response


def _payload(
    *,
    url: str,
    method: str,
    headers: dict[str, Any],
    cookies: dict[str, str],
    body_type: str,
    body: Any,
    timeout: float,
    follow_redirects: bool,
    verify_ssl: bool,
) -> dict[str, Any]:
    json_body: Any = None
    content: str | None = None
    form: dict[str, Any] | None = None
    if method in {"POST", "PUT", "PATCH"}:
        if body_type == "json":
            json_body = body
        elif body_type == "form":
            form = body if isinstance(body, dict) else {}
        elif body_type == "raw":
            content = str(body)
    return {
        "url": url,
        "method": method,
        "headers": headers,
        "cookies": cookies,
        "json": json_body,
        "content": content,
        "form": form,
        "timeoutSeconds": timeout,
        "followRedirects": follow_redirects,
        "verifySSL": verify_ssl,
    }


class ApiRequestExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "api_request"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        url = _text(config.get("requestUrl", ""), context)
        if not url:
            return ModuleResult(success=False, error="请求地址不能为空")
        try:
            headers = _object(config.get("requestHeaders", ""), context, strict=True)
        except ValueError as error:
            return ModuleResult(success=False, error=f"请求头{error}")
        raw_body = _text(config.get("requestBody", ""), context)
        try:
            body: Any = json.loads(raw_body) if raw_body else None
        except json.JSONDecodeError:
            body = raw_body
        try:
            response = await _request(
                context,
                _payload(
                    url=url,
                    method=_text(config.get("requestMethod", "GET"), context).upper(),
                    headers=headers,
                    cookies=_cookies(config.get("requestCookies", ""), context),
                    body_type="json" if isinstance(body, dict) else "raw",
                    body=body,
                    timeout=to_float(config.get("requestTimeout", 30), 30, context),
                    follow_redirects=False,
                    verify_ssl=True,
                ),
            )
        except Exception as error:  # noqa: BLE001 - integration errors become node errors.
            return ModuleResult(success=False, error=str(error) or "API请求失败")
        status = int(response.get("statusCode", 0))
        response_body = response.get("body")
        variable_name = config.get("variableName", "")
        if isinstance(variable_name, str) and variable_name:
            context.set_variable(variable_name, response_body)
        preview = str(response_body)
        if len(preview) > 100:
            preview = f"{preview[:100]}..."
        return ModuleResult(
            success=True,
            message=f"请求成功 ({status}): {preview}",
            data={"status_code": status, "response": response_body},
        )


class WebhookRequestExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "webhook_request"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        url = _text(config.get("url", ""), context)
        if not url:
            return ModuleResult(
                success=False, error="URL为空", message="Webhook URL不能为空"
            )
        method = _text(config.get("method", "POST"), context).upper()
        body_type = str(config.get("bodyType", "json"))
        raw_body = config.get("body", {})
        if body_type == "json":
            try:
                body: Any = _object(raw_body, context, strict=False)
            except ValueError:
                body = _text(raw_body, context)
        elif body_type == "form":
            body = _object(raw_body, context, strict=False)
        else:
            body = _text(
                raw_body.get("raw", "") if isinstance(raw_body, dict) else raw_body,
                context,
            )
        try:
            response = await _request(
                context,
                _payload(
                    url=url,
                    method=method,
                    headers=_object(config.get("headers", {}), context, strict=False),
                    cookies=_cookies(config.get("cookies", {}), context),
                    body_type=body_type,
                    body=body,
                    timeout=to_float(config.get("timeout", 30), 30, context),
                    follow_redirects=config.get("followRedirects", True) is not False,
                    verify_ssl=config.get("verifySSL", True) is not False,
                ),
            )
        except Exception as error:  # noqa: BLE001 - integration errors become node errors.
            return ModuleResult(success=False, error=str(error) or "Webhook请求失败")
        status = int(response.get("statusCode", 0))
        response_body = response.get("body")
        if config.get("saveResponse"):
            context.set_variable(
                str(config.get("responseVariable") or "webhook_response"), response_body
            )
        if config.get("saveStatus"):
            context.set_variable(
                str(config.get("statusVariable") or "webhook_status"), status
            )
        if config.get("saveHeaders"):
            context.set_variable(
                str(config.get("headersVariable") or "webhook_headers"),
                dict(response.get("headers") or {}),
            )
        if config.get("saveCookies"):
            context.set_variable(
                str(config.get("cookiesVariable") or "webhook_cookies"),
                dict(response.get("cookies") or {}),
            )
        data = {
            "status_code": status,
            "response": response_body if config.get("saveResponse") else None,
        }
        if 200 <= status < 300:
            return ModuleResult(
                success=True, message=f"Webhook请求成功，状态码: {status}", data=data
            )
        return ModuleResult(
            success=False,
            message=f"Webhook请求失败，状态码: {status}",
            error=f"HTTP {status}: {str(response_body)[:200]}",
            data={"status_code": status, "response": response_body},
        )


class NotifyWebhookExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "notify_webhook"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        url = _text(config.get("webhookUrl", ""), context)
        message = _text(config.get("message", config.get("body", "")), context)
        if not url:
            return ModuleResult(success=False, error="服务配置不完整")
        if not message:
            return ModuleResult(success=False, error="通知内容不能为空")
        try:
            body = json.loads(message)
        except json.JSONDecodeError:
            body = {"message": message}
        try:
            response = await _request(
                context,
                _payload(
                    url=url,
                    method=_text(config.get("method", "POST"), context).upper(),
                    headers={"Content-Type": "application/json"},
                    cookies={},
                    body_type="json",
                    body=body,
                    timeout=to_float(config.get("timeout", 30), 30, context),
                    follow_redirects=True,
                    verify_ssl=True,
                ),
            )
        except Exception as error:  # noqa: BLE001 - integration errors become node errors.
            return ModuleResult(success=False, error=str(error) or "通知发送失败")
        status = int(response.get("statusCode", 0))
        if 200 <= status < 300:
            return ModuleResult(success=True, message="通知发送成功")
        return ModuleResult(success=False, error=f"通知发送失败: HTTP {status}")


EXTERNAL_HTTP_EXECUTORS = (
    ApiRequestExecutor,
    WebhookRequestExecutor,
    NotifyWebhookExecutor,
)
