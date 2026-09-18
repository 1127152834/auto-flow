from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from autoflow.domain.project_automations.models import AutomationRecord
from autoflow.domain.project_automations.rules import _environment
from autoflow.domain.projects.models import ProjectError

from .models import BatchStart, ProjectRunError


def validate_batch_start(
    automation: AutomationRecord,
    payload: dict[str, Any],
    *,
    allow_data_inputs: bool = False,
) -> BatchStart:
    if not isinstance(payload, dict):
        raise _error("form", "请求必须是对象")
    allowed = {
        "expectedAutomationRevision",
        "parameters",
        "maxTasks",
        "concurrency",
        "environmentOverride",
    }
    required = {"expectedAutomationRevision", "parameters"}
    if set(payload) - allowed or required - set(payload):
        field = min((required - set(payload)) or (set(payload) - allowed))
        raise _error(field, "缺少必填字段" if field in required else "未知字段")
    revision = payload["expectedAutomationRevision"]
    if type(revision) is not int or revision < 1:
        raise _error("expectedAutomationRevision", "必须是正整数")
    if revision != automation.management_revision:
        raise ProjectRunError(
            "REVISION_CONFLICT",
            "自动化配置已更新，请刷新后重试",
            409,
            {
                "expectedAutomationRevision": revision,
                "currentAutomationRevision": automation.management_revision,
                "domainCode": "revision_conflict",
                "retryable": False,
            },
        )
    if automation.input_plan.get("inputs") and not allow_data_inputs:
        raise _error("inputPlan.inputs", "当前仅支持参数型运行，请移除项目数据输入")
    parameters = _parameters(automation.parameter_schema, payload["parameters"])
    max_tasks = (
        payload["maxTasks"]
        if "maxTasks" in payload
        else automation.run_policy.get("maxTasks", 1)
    )
    has_required_data = any(
        isinstance(item, dict) and item.get("required") is True
        for item in automation.input_plan.get("inputs", [])
    )
    if max_tasks is None:
        if not has_required_data:
            raise _error("maxTasks", "不限次数至少需要一个必要数据输入")
    elif type(max_tasks) is not int or not 1 <= max_tasks <= 100:
        raise _error("maxTasks", "必须是 1–100 的整数，或为不限次数")
    concurrency = payload.get(
        "concurrency", automation.run_policy.get("concurrency", 1)
    )
    if type(concurrency) is not int or not 1 <= concurrency <= 100:
        raise _error("concurrency", "必须是 1–100 的整数")
    if not automation.input_plan.get("inputs") and concurrency != 1:
        raise _error("concurrency", "参数型运行当前并发数必须为 1")
    environment_override = payload.get("environmentOverride")
    if "environmentOverride" in payload and not isinstance(environment_override, dict):
        raise _error("environmentOverride", "必须是环境策略对象")
    if environment_override is not None:
        try:
            environment_override = _environment(deepcopy(environment_override))
        except ProjectError as error:
            fields = error.details.get("fields", {})
            field, message = next(
                iter(fields.items()), ("environmentPolicy", "环境策略无效")
            )
            raise _error(
                field.replace("environmentPolicy", "environmentOverride", 1), message
            ) from error
    effective_environment = environment_override or automation.environment_policy
    source = effective_environment.get("source")
    if source not in {"newFromProfile", "fixedEnvironment", "inputEnvironment"}:
        field = (
            "environmentOverride.source"
            if environment_override is not None
            else "environmentPolicy.source"
        )
        raise _error(field, "无效的环境来源")
    if source == "inputEnvironment" and not automation.input_plan.get("inputs"):
        field = (
            "environmentOverride.inputId"
            if environment_override is not None
            else "environmentPolicy.inputId"
        )
        raise _error(field, "记录关联环境需要数据输入")
    return BatchStart(
        expected_automation_revision=revision,
        parameters=parameters,
        max_tasks=max_tasks,
        concurrency=concurrency,
        environment_override=deepcopy(environment_override),
    )


def _parameters(definitions: list[dict[str, Any]], supplied: Any) -> dict[str, Any]:
    if not isinstance(supplied, dict):
        raise _error("parameters", "必须是以 parameterId 为键的对象")
    known = {definition["parameterId"]: definition for definition in definitions}
    for parameter_id in supplied:
        if type(parameter_id) is not str or parameter_id not in known:
            raise _error(f"parameters.{parameter_id}", "未知参数")
    resolved: dict[str, Any] = {}
    for parameter_id, definition in known.items():
        if parameter_id in supplied:
            value = supplied[parameter_id]
        elif "defaultValue" in definition:
            value = definition["defaultValue"]
        elif definition["required"]:
            raise _error(f"parameters.{parameter_id}", "缺少必填参数")
        else:
            continue
        if not _matches(value, definition["type"]):
            raise _error(f"parameters.{parameter_id}", "参数值类型不匹配")
        resolved[parameter_id] = deepcopy(value)
    return resolved


def _matches(value: Any, kind: str) -> bool:
    if value is None:
        return True
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return type(value) is bool
    if type(value) not in {int, float}:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _error(field: str, message: str) -> ProjectRunError:
    return ProjectRunError(
        "VALIDATION_ERROR",
        "批次启动参数无效",
        422,
        {"fields": {field: message}, "retryable": False},
    )
