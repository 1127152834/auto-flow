from __future__ import annotations

import json
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext, InputPromptRequest

from .base import ModuleExecutor, ModuleResult


class InputPromptExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "input_prompt"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        variable_name = str(config.get("variableName") or "")
        if not variable_name:
            return ModuleResult(success=False, error="变量名不能为空")
        if context.input_prompts is None:
            return ModuleResult(success=False, error="输入请求服务不可用")

        input_mode = str(context.resolve_value(config.get("inputMode", "single")))
        required_raw = context.resolve_value(config.get("required", True))
        required = required_raw in (True, "true", "True", "1", 1)
        timeout = _number(context.resolve_value(config.get("timeout", 0)), 0.0)
        timeout = max(timeout, 0.0)
        request = InputPromptRequest(
            variable_name=variable_name,
            title=_text(context.resolve_value(config.get("promptTitle", "输入"))),
            message=_text(
                context.resolve_value(config.get("promptMessage", "请输入值:"))
            ),
            default_value=_default_value(
                context.resolve_value(config.get("defaultValue", ""))
            ),
            input_mode=input_mode,
            min_value=_optional_number(config.get("minValue"), context),
            max_value=_optional_number(config.get("maxValue"), context),
            max_length=_optional_integer(config.get("maxLength"), context),
            required=required,
            select_options=_select_options(config.get("selectOptions"), context),
        )
        try:
            user_input = await context.input_prompts.request_input(
                request, timeout_seconds=timeout
            )
            if user_input is None:
                message = (
                    f"等待用户输入超时（{timeout:g} 秒内未收到输入），变量 {variable_name} 保持不变。"
                    "如需一直等待，请把该模块的超时设为 0。"
                    if timeout > 0
                    else f"用户取消输入，变量 {variable_name} 保持不变"
                )
                return ModuleResult(
                    success=True,
                    message=message,
                    data={"cancelled": True, "timeout": timeout > 0},
                )
            value, value_type = _convert_input(input_mode, user_input)
            if input_mode == "password":
                context.mark_sensitive_use()
            context.set_variable(variable_name, value)
            return ModuleResult(
                success=True,
                message=_success_message(variable_name, value, input_mode),
                data=_result_data(value, value_type, input_mode),
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            return ModuleResult(success=False, error=str(error))
        except Exception as error:  # noqa: BLE001 -- source returns a node failure.
            return ModuleResult(success=False, error=f"输入框失败: {error}")


def _convert_input(mode: str, value: str) -> tuple[Any, str | None]:
    if mode == "checkbox":
        return value.lower() in ("true", "1", "yes", "on"), "boolean"
    if mode == "slider_int":
        try:
            return int(float(value)), "integer"
        except ValueError:
            raise ValueError("滑动条返回的值不是有效的整数") from None
    if mode == "slider_float":
        try:
            return float(value), "float"
        except ValueError:
            raise ValueError("滑动条返回的值不是有效的数字") from None
    if mode == "select_multiple":
        try:
            selected = json.loads(value)
        except json.JSONDecodeError:
            selected = [value]
        return (selected if isinstance(selected, list) else [selected]), "list"
    if mode == "list":
        return [line.strip() for line in value.split("\n") if line.strip()], "list"
    if mode == "integer":
        try:
            return int(value), "integer"
        except ValueError:
            raise ValueError("输入的值不是有效的整数") from None
    if mode == "number":
        try:
            return float(value), "number"
        except ValueError:
            raise ValueError("输入的值不是有效的数字") from None
    if mode in {"file", "folder", "select_single"}:
        return value, "string" if mode == "select_single" else mode
    return value, None


def _select_options(value: Any, context: ExecutionContext) -> tuple[str, ...] | None:
    if value in (None, ""):
        return None
    resolved = context.resolve_value(value)
    if not isinstance(resolved, list) and isinstance(value, str):
        resolved = context.get_variable(value.strip("{}"), [])
    if not isinstance(resolved, list):
        return ()
    return tuple(
        json.dumps(item, ensure_ascii=False)
        if isinstance(item, dict)
        else str(item)
        for item in resolved
    )


def _optional_number(value: Any, context: ExecutionContext) -> float | None:
    if value in (None, ""):
        return None
    return float(context.resolve_value(value))


def _optional_integer(value: Any, context: ExecutionContext) -> int | None:
    if value in (None, ""):
        return None
    return int(context.resolve_value(value))


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _default_value(value: Any) -> str | float | bool | None:
    return value if isinstance(value, (str, float, bool)) or value is None else str(value)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _success_message(name: str, value: Any, mode: str) -> str:
    if mode == "password":
        return f"已设置变量 {name} = ******"
    if isinstance(value, list):
        return f"已设置变量 {name} = 列表({len(value)}项)"
    if mode in {"file", "folder"}:
        return f"已设置{'文件' if mode == 'file' else '文件夹'}路径 {name} = {value}"
    return f"已设置变量 {name} = {value}"


def _result_data(value: Any, value_type: str | None, mode: str) -> dict[str, Any]:
    data: dict[str, Any] = {"value": value}
    if mode in {"checkbox", "slider_int", "slider_float", "select_single"}:
        data["type"] = value_type
    elif mode == "select_multiple":
        data.update({"count": len(value), "type": "list"})
    elif mode == "list":
        data["count"] = len(value)
    elif mode in {"file", "folder"}:
        data["type"] = mode
    return data
