"""Canonical project End configuration and legacy document normalization."""

import re
from collections.abc import Mapping
from typing import Any

from autoflow.domain.workflows.variables import references_variable


def normalize_project_end(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return the flat PM9 contract without rewriting a frozen document."""
    value = dict(config)
    legacy = value.get("retainEnvironment")
    if isinstance(legacy, Mapping):
        nested = dict(legacy)
        value["retainEnvironment"] = nested.get("enabled", False)
        for source, target in (
            ("name", "name"),
            ("recordTargets", "recordTargets"),
            ("replaceAllowed", "replaceAllowed"),
            ("inputIds", "inputIds"),
        ):
            if target not in value and source in nested:
                value[target] = nested[source]
        if "saveMode" not in value and "mode" in nested:
            value["saveMode"] = {
                "saveAs": "save_as",
                "save_as": "save_as",
                "update": "auto",
                "auto": "auto",
            }.get(nested["mode"], nested["mode"])
    validate_project_end(value)
    return value


def validate_project_end(config: Mapping[str, Any]) -> None:
    result = config.get("businessResult", "succeeded")
    # Remediation M4 R4-07: a variable (e.g. the login outcome) may decide the result at run time;
    # it must then resolve to succeeded or failed.
    if result not in {"succeeded", "failed"} and not (isinstance(result, str) and references_variable(result)):
        raise ValueError("End 业务结果必须为成功、失败或引用一个变量")
    if type(config.get("retainEnvironment", False)) is not bool:
        raise ValueError("End 保留环境必须为布尔值")
    if config.get("saveMode", "auto") not in {"auto", "save_as"}:
        raise ValueError("End 只允许更新当前来源或另存")
    if type(config.get("replaceAllowed", False)) is not bool:
        raise ValueError("End 替换授权必须为布尔值")
    inputs = config.get("inputIds")
    if inputs is not None and (
        not isinstance(inputs, list)
        or len(inputs) > 100
        or any(not isinstance(identity, str) or not identity for identity in inputs)
    ):
        raise ValueError("End 输入目标必须是有界输入标识列表")
    name = config.get("name", "保留环境")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 36:
        raise ValueError("End 环境名称无效")
    targets = config.get("recordTargets", [])
    if isinstance(targets, str):
        if len(targets) > 4096 or not re.fullmatch(
            r"\$?\{[\w\u4e00-\u9fa5]+(?:\[[^{}\[\]]+\])*\}", targets
        ):
            raise ValueError("End 动态目标必须是完整变量引用")
    elif not isinstance(targets, list) or len(targets) > 100:
        raise ValueError("End 记录目标必须是有界列表或变量引用")
