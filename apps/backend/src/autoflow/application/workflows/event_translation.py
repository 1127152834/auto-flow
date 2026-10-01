"""Failure wording shared by the Studio runtime and the project batch graph (remediation M1, R1-03).

Both paths turn an executor failure into text a person reads in the run log. The rules live here so the
same failure or credential-derived error produces the same safe reason on either path.
"""

from __future__ import annotations

NODE_TIMEOUT_CODE = "WORKFLOW_NODE_TIMEOUT"
MAX_REASON_CHARS = 1000
SENSITIVE_SUCCESS_MESSAGE = "节点执行成功（结果包含凭据派生值）"
SENSITIVE_FAILURE_REASON = "节点执行失败（错误包含凭据派生值）"


def failure_reason(raw: object) -> str:
    """The executor's own words, without the bare timeout code, bounded for display."""
    reason = str(raw or "").strip()
    if reason == NODE_TIMEOUT_CODE:
        return ""
    return reason[:MAX_REASON_CHARS] + "…" if len(reason) > MAX_REASON_CHARS else reason


def node_failure_message(raw: object, *, timeout: bool) -> str:
    headline = "工作流节点执行超时" if timeout else "工作流节点执行失败"
    detail = failure_reason(raw)
    return f"{headline}：{detail}" if detail else headline
