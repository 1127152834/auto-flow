"""Existing Studio webhook validation/payload rules shared with project delivery."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from autoflow.domain.workflows.runs import WorkflowRunError

SENSITIVE_WEBHOOK_HEADERS = {
    "authorization", "cookie", "x-api-key", "x-auth-token", "x-csrf-token", "proxy-authorization",
}


def webhook_payload(state: Mapping[str, Any], *, method: str, headers: Mapping[str, str],
                    query: Mapping[str, str], body: Any) -> dict[str, Any]:
    if state["status"] != "pending":
        raise WorkflowRunError("WEBHOOK_NOT_FOUND", "Webhook不存在、HTTP方法不匹配或已经触发", 404)
    if str(state["method"]).upper() not in {"ANY", method.upper()}:
        raise WorkflowRunError("WEBHOOK_NOT_FOUND", "Webhook不存在或HTTP方法不匹配", 404)
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    if any(normalized_headers.get(str(key).lower()) != str(value)
           for key, value in dict(state["validateHeaders"]).items()):
        raise WorkflowRunError("WEBHOOK_HEADER_MISMATCH", "Webhook请求头验证失败", 403)
    if any(query.get(str(key)) != str(value) for key, value in dict(state["validateParams"]).items()):
        raise WorkflowRunError("WEBHOOK_PARAM_MISMATCH", "Webhook查询参数验证失败", 403)
    return {
        "method": method.upper(),
        "headers": {key: value for key, value in headers.items() if key.lower() not in SENSITIVE_WEBHOOK_HEADERS},
        "body": copy.deepcopy(body), "query": dict(query), "timestamp": datetime.now(UTC).isoformat(),
    }
