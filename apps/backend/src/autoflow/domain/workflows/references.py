import re
from uuid import UUID

from .models import WorkflowError


def is_canonical_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def require_canonical_uuid(value: object, field: str) -> str:
    if is_canonical_uuid(value):
        assert isinstance(value, str)
        return value
    raise WorkflowError(
        "VALIDATION_ERROR",
        "请求参数无效",
        422,
        details={
            "fields": {field: "必须是规范小写 UUID"},
            "domainCode": "validation_error",
            "retryable": False,
        },
    )


def is_workflow_id(value: object) -> bool:
    """Retain identities emitted by both AutoFlow and the migrated Studio."""
    return is_canonical_uuid(value) or (
        isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{21}", value) is not None
    )


def require_workflow_id(value: object, field: str) -> str:
    if is_workflow_id(value):
        assert isinstance(value, str)
        return value
    raise WorkflowError(
        "VALIDATION_ERROR", "请求参数无效", 422,
        details={
            "fields": {field: "必须是规范小写 UUID 或 Studio Nano ID"},
            "domainCode": "validation_error", "retryable": False,
        },
    )
