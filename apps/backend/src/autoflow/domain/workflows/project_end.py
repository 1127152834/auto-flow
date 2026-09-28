"""Bounded project End configuration; dynamic values only select leased records."""

import re
from typing import Any


def validate_project_end(config: dict[str, Any]) -> None:
    if config.get("businessResult", "succeeded") not in {"succeeded", "failed"}:
        raise ValueError("End 业务结果必须为成功或失败")
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
        or any(not isinstance(i, str) for i in inputs)
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
