"""Approved WebRPA control and variable executors.

Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
backend/app/executors/{control,control_extended,basic_variable,basic,
advanced,advanced_assert}.py. Licensed under LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import base64
import json
import random
import re
from datetime import UTC
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import format_selector

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor
from .type_utils import to_float, to_int


def _page(context: ExecutionContext) -> Any | None:
    if context.browser is None:
        return None
    try:
        return context.browser.active_page()
    except Exception:  # noqa: BLE001 -- absent/closed browser becomes a node result.
        return None


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value == "":
            return False
        if value.lower() in ("true", "1", "yes"):
            return True
        return value.lower() not in ("false", "0", "no")
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return bool(value)


@register_executor
class ConditionExecutor(ModuleExecutor):
    def requires_browser_for(self, config: dict[str, Any]) -> bool:
        return config.get("conditionType") in {"element_exists", "element_visible"}

    @property
    def module_type(self) -> str:
        return "condition"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        condition_type = context.resolve_value(config.get("conditionType", "variable"))
        operator = context.resolve_value(config.get("operator", "=="))
        try:
            result = False
            if condition_type == "logic":
                logic_operator = context.resolve_value(
                    config.get("logicOperator", "and")
                )

                def evaluate(raw: Any) -> bool:
                    return False if not raw else _truthy(context.resolve_value(raw))

                if logic_operator == "not":
                    result = not evaluate(config.get("condition", ""))
                elif logic_operator == "and":
                    result = evaluate(config.get("condition1", "")) and evaluate(
                        config.get("condition2", "")
                    )
                elif logic_operator == "or":
                    result = evaluate(config.get("condition1", "")) or evaluate(
                        config.get("condition2", "")
                    )
            elif condition_type == "boolean":
                raw_left = config.get("leftOperand") or config.get("leftValue", "")
                result = _truthy(context.resolve_value(raw_left))
            elif condition_type == "variable":
                raw_left = config.get("leftOperand") or config.get("leftValue", "")
                raw_right = config.get("rightOperand") or config.get("rightValue", "")
                left_value = context.resolve_value(raw_left)
                right_value = context.resolve_value(raw_right)
                try:
                    left_num = (
                        float(left_value)
                        if left_value is not None and str(left_value).strip() != ""
                        else None
                    )
                    right_num = (
                        float(right_value)
                        if right_value is not None and str(right_value).strip() != ""
                        else None
                    )
                    use_numeric = left_num is not None and right_num is not None
                except (ValueError, TypeError):
                    use_numeric = False
                    left_num = right_num = None

                if operator == "==":
                    result = str(left_value) == str(right_value)
                elif operator == "!=":
                    result = str(left_value) != str(right_value)
                elif operator == "isEmpty":
                    if left_value is None:
                        result = True
                    elif isinstance(left_value, str):
                        result = left_value == ""
                    elif isinstance(left_value, (list, dict)):
                        result = len(left_value) == 0
                    else:
                        result = not bool(left_value)
                elif operator == "isNotEmpty":
                    if left_value is None:
                        result = False
                    elif isinstance(left_value, str):
                        result = left_value != ""
                    elif isinstance(left_value, (list, dict)):
                        result = len(left_value) > 0
                    else:
                        result = bool(left_value)
                elif operator in (">", "<", ">=", "<="):
                    if not use_numeric:
                        return ModuleResult(
                            success=False,
                            error=(
                                f"运算符 '{operator}' 需要数值类型，但左值="
                                f"'{left_value}'，右值='{right_value}' 无法转换为数字"
                            ),
                        )
                    if operator == ">":
                        result = left_num > right_num  # type: ignore[operator]
                    elif operator == "<":
                        result = left_num < right_num  # type: ignore[operator]
                    elif operator == ">=":
                        result = left_num >= right_num  # type: ignore[operator]
                    else:
                        result = left_num <= right_num  # type: ignore[operator]
                elif operator == "contains":
                    result = str(right_value) in str(left_value)
                elif operator == "not_contains":
                    result = str(right_value) not in str(left_value)
                elif operator in ("startswith", "starts_with"):
                    result = str(left_value).startswith(str(right_value))
                elif operator in ("endswith", "ends_with"):
                    result = str(left_value).endswith(str(right_value))
                elif operator == "in":
                    result = (
                        left_value in right_value
                        if isinstance(right_value, (list, tuple))
                        else str(left_value) in str(right_value)
                    )
                elif operator == "not_in":
                    result = (
                        left_value not in right_value
                        if isinstance(right_value, (list, tuple))
                        else str(left_value) not in str(right_value)
                    )
                else:
                    return ModuleResult(
                        success=False, error=f"不支持的运算符: '{operator}'"
                    )
            elif condition_type in ("element_exists", "element_visible"):
                page = _page(context)
                if page is None:
                    return ModuleResult(
                        success=False, error="没有打开的页面，请先使用'打开网页'模块"
                    )
                selector = context.resolve_value(
                    config.get("leftOperand") or config.get("leftValue", "")
                )
                if not selector:
                    return ModuleResult(success=False, error="元素选择器不能为空")
                try:
                    element = page.locator(format_selector(str(selector)))
                    count = await element.count()
                    result = count > 0
                    if result and condition_type == "element_visible":
                        result = await element.first.is_visible()
                except Exception as error:  # noqa: BLE001 -- frozen node semantics.
                    return ModuleResult(
                        success=True,
                        message=f"条件判断结果: False (检查元素时出错: {error})",
                        branch="false",
                        data=False,
                    )
            branch = "true" if result else "false"
            return ModuleResult(
                success=True,
                message=f"条件判断结果: {result}",
                branch=branch,
                data=result,
            )
        except Exception as error:  # noqa: BLE001 -- frozen node semantics.
            return ModuleResult(success=False, error=f"条件判断失败: {error}")


@register_executor
class LoopExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "loop"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        loop_type = context.resolve_value(config.get("loopType", "count"))
        raw_count = (
            config.get("loopCount")
            if config.get("loopCount") is not None
            else config.get("count", 10)
        )
        count = to_int(raw_count, 10, context)
        condition = config.get("condition", "")
        max_iterations = to_int(config.get("maxIterations", 1000), 1000, context)
        index_variable = config.get("indexVariable", "index")
        start_value = to_int(config.get("startValue", 1), 1, context)
        end_value = to_int(config.get("endValue", 10), 10, context)
        raw_step = (
            config.get("stepValue")
            if config.get("stepValue") is not None
            else config.get("step", 1)
        )
        step_value = to_int(raw_step, 1, context)
        if loop_type == "range":
            initial_index = start_value
            if step_value > 0:
                count = max(0, (end_value - start_value) // step_value + 1)
            elif step_value < 0:
                count = max(0, (start_value - end_value) // abs(step_value) + 1)
            else:
                count = 0
        else:
            initial_index = 0
        loop_state = {
            "type": loop_type,
            "count": count,
            "condition": condition,
            "max_iterations": max_iterations,
            "index_variable": index_variable,
            "current_index": initial_index,
            "start_value": start_value,
            "end_value": end_value,
            "step_value": step_value,
        }
        context.loop_stack.append(loop_state)
        context.set_variable(str(index_variable), initial_index)
        if loop_type == "range":
            return ModuleResult(
                success=True,
                message=f"开始范围循环 ({start_value} 到 {end_value}，步长 {step_value})",
                data=loop_state,
            )
        return ModuleResult(
            success=True,
            message=f"开始循环 (类型: {loop_type}, 次数: {count})",
            data=loop_state,
        )


@register_executor
class ForeachExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "foreach"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        data_source = config.get("dataSource") or config.get("listVariable", "")
        item_variable = config.get("itemVariable", "item")
        index_variable = config.get("indexVariable", "index")
        data = context.resolve_value(data_source) if data_source else []
        if isinstance(data, str):
            data = context.get_variable(data, [])
        if not isinstance(data, (list, tuple)):
            return ModuleResult(success=False, error=f"数据源不是数组: {data_source}")
        loop_state = {
            "type": "foreach",
            "data": list(data),
            "item_variable": item_variable,
            "index_variable": index_variable,
            "current_index": 0,
        }
        context.loop_stack.append(loop_state)
        if data:
            context.set_variable(str(item_variable), data[0])
            context.set_variable(str(index_variable), 0)
        return ModuleResult(
            success=True,
            message=f"开始遍历 (共 {len(data)} 项)",
            data=loop_state,
        )


@register_executor
class InfiniteLoopExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "infinite_loop"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        index_variable = config.get("indexVariable", "loop_index")
        loop_state = {
            "type": "infinite",
            "count": 999999999,
            "condition": "",
            "max_iterations": 999999999,
            "index_variable": index_variable,
            "current_index": 0,
            "start_value": 0,
            "end_value": 999999999,
            "step_value": 1,
        }
        context.loop_stack.append(loop_state)
        context.set_variable(str(index_variable), 0)
        return ModuleResult(
            success=True,
            message="开始无限循环（使用'跳出循环'模块退出）",
            data=loop_state,
        )


@register_executor
class ForeachDictExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "foreach_dict"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        dict_variable = config.get("dictVariable", "")
        key_variable = config.get("keyVariable", "key")
        value_variable = config.get("valueVariable", "value")
        index_variable = config.get("indexVariable", "index")
        if not dict_variable:
            return ModuleResult(success=False, error="字典变量名不能为空")
        dict_data = context.get_variable(dict_variable)
        if dict_data is None:
            return ModuleResult(success=False, error=f"变量 '{dict_variable}' 不存在")
        if not isinstance(dict_data, dict):
            return ModuleResult(
                success=False, error=f"变量 '{dict_variable}' 不是字典类型"
            )
        items = list(dict_data.items())
        loop_state = {
            "type": "foreach_dict",
            "data": items,
            "key_variable": key_variable,
            "value_variable": value_variable,
            "index_variable": index_variable,
            "current_index": 0,
        }
        context.loop_stack.append(loop_state)
        if items:
            first_key, first_value = items[0]
            context.set_variable(str(key_variable), first_key)
            context.set_variable(str(value_variable), first_value)
            context.set_variable(str(index_variable), 0)
        return ModuleResult(
            success=True,
            message=f"开始遍历字典 (共 {len(items)} 项)",
            data=loop_state,
        )


@register_executor
class BreakLoopExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "break_loop"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        del config
        if not context.loop_stack:
            return ModuleResult(success=False, error="当前不在循环中")
        context.should_break = True
        return ModuleResult(success=True, message="跳出循环")


@register_executor
class ContinueLoopExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "continue_loop"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        del config
        if not context.loop_stack:
            return ModuleResult(success=False, error="当前不在循环中")
        context.should_continue = True
        return ModuleResult(success=True, message="继续下一次循环")


@register_executor
class SetVariableExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "set_variable"

    def _evaluate_expression(self, expression: str, context: ExecutionContext) -> Any:
        def replace_variable(match: re.Match[str]) -> str:
            value = context.variables.get(match.group(1).strip(), 0)
            try:
                if isinstance(value, (int, float)):
                    return str(value)
                return str(float(value))
            except (ValueError, TypeError):
                return str(value)

        resolved = re.sub(r"\{([^}]+)\}", replace_variable, expression)
        if re.match(r"^[\d\s\+\-\*\/\.\(\)]+$", resolved):
            try:
                result = eval(resolved, {"__builtins__": {}}, {})
                if isinstance(result, float) and result.is_integer():
                    return int(result)
                return result
            except Exception:  # noqa: BLE001, S110 -- frozen fallback behavior.
                pass
        try:
            if "." in resolved:
                return float(resolved)
            return int(resolved)
        except ValueError:
            return resolved

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        variable_name = config.get("variableName", "")
        variable_value = context.resolve_value(config.get("variableValue", ""))
        if not variable_name:
            return ModuleResult(success=False, error="变量名不能为空")
        try:
            resolved_value = self._evaluate_expression(variable_value, context)
            context.set_variable(str(variable_name), resolved_value)
            return ModuleResult(
                success=True,
                message=f"已设置变量 {variable_name} = {resolved_value}",
                data=resolved_value,
            )
        except Exception as error:  # noqa: BLE001 -- frozen node semantics.
            return ModuleResult(success=False, error=f"设置变量失败: {error}")


@register_executor
class IncrementDecrementExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "increment_decrement"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        variable_name = context.resolve_value(config.get("variableName", ""))
        operation = context.resolve_value(config.get("operation", "increment"))
        step = context.resolve_value(config.get("step", 1))
        if not variable_name:
            return ModuleResult(success=False, error="变量名不能为空")
        try:
            if isinstance(step, str):
                try:
                    step = float(step) if "." in step else int(step)
                except ValueError:
                    return ModuleResult(success=False, error=f"步长必须是数字: {step}")
            current_value = context.get_variable(variable_name)
            if current_value is None:
                current_value = 0
            if isinstance(current_value, str):
                try:
                    current_value = (
                        float(current_value)
                        if "." in current_value
                        else int(current_value)
                    )
                except ValueError:
                    return ModuleResult(
                        success=False,
                        error=f"变量 '{variable_name}' 的值不是数字: {current_value}",
                    )
            if not isinstance(current_value, (int, float)):
                return ModuleResult(
                    success=False,
                    error=f"变量 '{variable_name}' 的值不是数字类型",
                )
            if operation == "increment":
                new_value = current_value + step
                label = "自增"
            elif operation == "decrement":
                new_value = current_value - step
                label = "自减"
            else:
                return ModuleResult(success=False, error=f"未知的操作类型: {operation}")
            context.set_variable(str(variable_name), new_value)
            return ModuleResult(
                success=True,
                message=(
                    f"{label}: {variable_name} = {current_value} → {new_value} "
                    f"(步长: {step})"
                ),
                data={
                    "variable": variable_name,
                    "old_value": current_value,
                    "new_value": new_value,
                    "step": step,
                },
            )
        except Exception as error:  # noqa: BLE001 -- frozen node semantics.
            return ModuleResult(success=False, error=f"自增自减失败: {error}")


def _split_json_path(path: str) -> list[str]:
    parts: list[str] = []
    current = ""
    in_bracket = False
    for char in path:
        if char == "[":
            in_bracket = True
            current += char
        elif char == "]":
            current += char
            parts.append(current)
            current = ""
            in_bracket = False
        elif char == "." and not in_bracket:
            if current:
                parts.append(current)
                current = ""
        else:
            current += char
    if current:
        parts.append(current)
    return parts


def _parse_json_path(data: Any, path: str) -> Any:
    path = path.removeprefix("$").removeprefix(".")
    if not path:
        return data
    current = data
    for part in _split_json_path(path):
        if current is None:
            return None
        if part.startswith("[") and part.endswith("]"):
            index_text = part[1:-1]
            if index_text == "*":
                return current if isinstance(current, list) else None
            try:
                index = int(index_text)
                if isinstance(current, list) and -len(current) <= index < len(current):
                    current = current[index]
                else:
                    return None
            except ValueError:
                if isinstance(current, dict) and index_text in current:
                    current = current[index_text]
                else:
                    return None
        elif "[" in part:
            position = part.index("[")
            property_name = part[:position]
            if isinstance(current, dict) and property_name in current:
                current = _parse_json_path(current[property_name], part[position:])
            else:
                return None
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


@register_executor
class JsonParseExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "json_parse"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        source_variable = config.get("sourceVariable", "")
        json_path = context.resolve_value(config.get("jsonPath", ""))
        variable_name = config.get("variableName", "")
        column_name = config.get("columnName", "")
        if not source_variable:
            return ModuleResult(success=False, error="源数据变量不能为空")
        if not json_path:
            return ModuleResult(success=False, error="JSONPath表达式不能为空")
        source_data = context.get_variable(source_variable)
        if source_data is None:
            return ModuleResult(success=False, error=f"变量 '{source_variable}' 不存在")
        if isinstance(source_data, str):
            try:
                source_data = json.loads(source_data)
            except json.JSONDecodeError as error:
                return ModuleResult(
                    success=False, error=f"源数据不是有效的JSON: {error}"
                )
        try:
            result = _parse_json_path(source_data, str(json_path))
            if variable_name:
                context.set_variable(str(variable_name), result)
            if column_name:
                context.add_data_value(str(column_name), result)
            display = str(result)
            if len(display) > 100:
                display = display[:100] + "..."
            return ModuleResult(
                success=True, message=f"解析成功: {display}", data=result
            )
        except Exception as error:  # noqa: BLE001 -- frozen node semantics.
            return ModuleResult(success=False, error=f"JSON解析失败: {error}")


@register_executor
class Base64Executor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "base64"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        operation = context.resolve_value(config.get("operation", "encode"))
        variable_name = config.get("variableName", "")
        try:
            if operation == "encode":
                input_text = context.resolve_value(config.get("inputText", ""))
                if not input_text:
                    return ModuleResult(success=False, error="输入文本不能为空")
                result = base64.b64encode(str(input_text).encode()).decode()
                if variable_name:
                    context.set_variable(str(variable_name), result)
                display = result[:50] + "..." if len(result) > 50 else result
                return ModuleResult(
                    success=True, message=f"编码成功: {display}", data=result
                )
            if operation == "decode":
                encoded = context.resolve_value(config.get("inputBase64", ""))
                if not encoded:
                    return ModuleResult(success=False, error="Base64字符串不能为空")
                if "," in encoded:
                    encoded = encoded.split(",", 1)[1]
                result = base64.b64decode(encoded).decode()
                if variable_name:
                    context.set_variable(str(variable_name), result)
                display = result[:50] + "..." if len(result) > 50 else result
                return ModuleResult(
                    success=True, message=f"解码成功: {display}", data=result
                )
            if operation == "file_to_base64":
                file_path = context.resolve_value(config.get("filePath", ""))
                if not file_path:
                    return ModuleResult(success=False, error="文件路径不能为空")
                path = Path(file_path)
                if context.node_artifacts is None:
                    return ModuleResult(success=False, error="文件服务不可用")
                snapshot = await context.node_artifacts.read_binary_output(
                    output_path=str(file_path), max_bytes=64 * 1024 * 1024
                )
                if snapshot.content is None:
                    return ModuleResult(success=False, error=f"文件不存在: {file_path}")
                file_data = snapshot.content
                encoded = base64.b64encode(file_data).decode()
                mime_type = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                    ".svg": "image/svg+xml",
                    ".pdf": "application/pdf",
                    ".txt": "text/plain",
                    ".json": "application/json",
                    ".xml": "application/xml",
                }.get(path.suffix.lower(), "application/octet-stream")
                result = f"data:{mime_type};base64,{encoded}"
                if variable_name:
                    context.set_variable(str(variable_name), result)
                return ModuleResult(
                    success=True,
                    message=f"文件转换成功: {path.name} ({len(file_data)} 字节)",
                    data=result,
                )
            if operation == "base64_to_file":
                encoded = context.resolve_value(config.get("inputBase64", ""))
                output_path = context.resolve_value(config.get("outputPath", ""))
                file_name = context.resolve_value(config.get("fileName", "output.bin"))
                if not encoded:
                    return ModuleResult(success=False, error="Base64字符串不能为空")
                if not output_path:
                    return ModuleResult(success=False, error="保存路径不能为空")
                if "," in encoded:
                    encoded = encoded.split(",", 1)[1]
                file_data = base64.b64decode(encoded)
                if context.node_artifacts is None:
                    return ModuleResult(success=False, error="文件服务不可用")
                full_path = str(Path(output_path) / str(file_name))
                result = await context.node_artifacts.write_binary_output(
                    output_path=full_path,
                    content=file_data,
                    mime_type="application/octet-stream",
                )
                if variable_name:
                    context.set_variable(str(variable_name), result)
                return ModuleResult(
                    success=True,
                    message=f"文件保存成功: {full_path} ({len(file_data)} 字节)",
                    data=result,
                )
            return ModuleResult(success=False, error=f"未知操作类型: {operation}")
        except Exception as error:  # noqa: BLE001 -- frozen node semantics.
            return ModuleResult(success=False, error=f"Base64处理失败: {error}")


@register_executor
class RandomNumberExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "random_number"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        random_type = context.resolve_value(config.get("randomType", "integer"))
        minimum = to_float(config.get("minValue", 0), 0, context)
        maximum = to_float(config.get("maxValue", 100), 100, context)
        decimal_places = to_int(config.get("decimalPlaces", 2), 2, context)
        variable_name = config.get("variableName", "")
        if not variable_name:
            return ModuleResult(success=False, error="变量名不能为空")
        try:
            if minimum > maximum:
                minimum, maximum = maximum, minimum
            if random_type == "integer":
                result: int | float = random.randint(int(minimum), int(maximum))
            else:
                result = round(random.uniform(minimum, maximum), decimal_places)
            context.set_variable(str(variable_name), result)
            return ModuleResult(
                success=True,
                message=f"已生成随机数: {result}",
                data={"value": result},
            )
        except Exception as error:  # noqa: BLE001 -- frozen node semantics.
            return ModuleResult(success=False, error=f"生成随机数失败: {error}")


@register_executor
class GetTimeExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "get_time"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        time_format = context.resolve_value(config.get("timeFormat", "datetime"))
        custom_format = context.resolve_value(config.get("customFormat", ""))
        variable_name = config.get("variableName", "")
        if not variable_name:
            return ModuleResult(success=False, error="变量名不能为空")
        try:
            now = context.clock.now()
            if now.tzinfo is not None:
                # Frozen datetime.now() is local and naive. AutoFlow clocks are UTC-aware.
                now = now.astimezone().replace(tzinfo=None)
            if time_format == "datetime":
                result: str | int = now.strftime("%Y-%m-%d %H:%M:%S")
            elif time_format == "date":
                result = now.strftime("%Y-%m-%d")
            elif time_format == "time":
                result = now.strftime("%H:%M:%S")
            elif time_format == "timestamp":
                result = int(now.timestamp() * 1000)
            elif time_format == "iso8601":
                result = now.isoformat()
            elif time_format == "iso8601_utc":
                result = now.astimezone(UTC).isoformat().replace("+00:00", "Z")
            elif time_format == "custom" and custom_format:
                result = now.strftime(str(custom_format))
            else:
                result = now.strftime("%Y-%m-%d %H:%M:%S")
            context.set_variable(str(variable_name), result)
            return ModuleResult(
                success=True,
                message=f"已获取时间: {result}",
                data={"value": result},
            )
        except Exception as error:  # noqa: BLE001 -- frozen node semantics.
            return ModuleResult(success=False, error=f"获取时间失败: {error}")


@register_executor
class WaitExecutor(ModuleExecutor):
    def requires_browser_for(self, config: dict[str, Any]) -> bool:
        return config.get("waitType", "time") in {"selector", "navigation"}

    @property
    def module_type(self) -> str:
        return "wait"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        wait_type = context.resolve_value(config.get("waitType", "time"))
        try:
            if wait_type == "time":
                raw_duration = (
                    config.get("duration")
                    if config.get("duration") is not None
                    else config.get("waitTime")
                )
                if raw_duration is None:
                    raw_duration = config.get("waitDuration")
                if raw_duration is None:
                    raw_duration = config.get("waitTimeout")
                duration = to_float(raw_duration, 1, context)
                if isinstance(raw_duration, str):
                    resolved = context.resolve_value(raw_duration)
                    if isinstance(resolved, str):
                        text = resolved.strip().lower()
                        if text.endswith("ms"):
                            try:
                                duration = float(text[:-2].strip()) / 1000
                            except Exception:  # noqa: BLE001, S110 -- frozen fallback.
                                pass
                        elif text.endswith(("秒", "s")):
                            try:
                                duration = float(text[:-1].strip())
                            except Exception:  # noqa: BLE001, S110 -- frozen fallback.
                                pass
                if 1000 <= duration <= 3_600_000:
                    duration /= 1000
                duration = max(duration, 0)
                await asyncio.sleep(duration)
                return ModuleResult(success=True, message=f"已等待 {duration}秒")
            if wait_type == "selector":
                selector = context.resolve_value(config.get("selector", ""))
                state = context.resolve_value(config.get("state", "visible"))
                if not selector:
                    return ModuleResult(success=False, error="选择器不能为空")
                page = _page(context)
                if page is None:
                    return ModuleResult(success=False, error="没有打开的页面")
                await page.locator(format_selector(str(selector))).first.wait_for(
                    state=str(state)
                )
                return ModuleResult(success=True, message=f"元素已{state}: {selector}")
            if wait_type == "navigation":
                page = _page(context)
                if page is None:
                    return ModuleResult(success=False, error="没有打开的页面")
                await page.wait_for_load_state("networkidle", timeout_ms=30000)
                return ModuleResult(success=True, message="页面导航完成")
            return ModuleResult(success=False, error=f"未知的等待类型: {wait_type}")
        except Exception as error:  # noqa: BLE001 -- frozen node semantics.
            return ModuleResult(success=False, error=f"等待失败: {error}")


@register_executor
class StopWorkflowExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "stop_workflow"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        stop_reason = config.get("stopReason", "用户主动停止工作流")
        context.stop_workflow = True
        context.stop_reason = str(stop_reason)
        return ModuleResult(
            success=True,
            message=f"工作流已停止: {stop_reason}",
            data={"reason": stop_reason},
        )


def _to_number(value: Any) -> int | float | None:
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip().replace(",", "")
        return None if text == "" else float(text)
    except (ValueError, TypeError):
        return None


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple)):
        return len(value) == 0
    return False


def _compare(left: Any, right: Any, operator: str) -> tuple[bool, str | None]:
    op = (operator or "==").strip()
    if op in ("==", "equals"):
        return str(left) == str(right), None
    if op in ("!=", "not_equals"):
        return str(left) != str(right), None
    if op in ("isEmpty", "is_empty"):
        return _is_empty(left), None
    if op in ("isNotEmpty", "is_not_empty"):
        return not _is_empty(left), None
    if op == "contains":
        return str(right) in str(left), None
    if op == "not_contains":
        return str(right) not in str(left), None
    if op in ("startswith", "starts_with"):
        return str(left).startswith(str(right)), None
    if op in ("endswith", "ends_with"):
        return str(left).endswith(str(right)), None
    if op in ("matches", "regex"):
        try:
            return re.search(str(right), str(left)) is not None, None
        except re.error as error:
            return False, f"正则表达式无效: {error}"
    if op in (">", "<", ">=", "<="):
        left_number, right_number = _to_number(left), _to_number(right)
        if left_number is None or right_number is None:
            return (
                False,
                f"运算符 '{op}' 需要数值，但左值='{left}'、右值='{right}' 无法转为数字",
            )
        if op == ">":
            return left_number > right_number, None
        if op == "<":
            return left_number < right_number, None
        if op == ">=":
            return left_number >= right_number, None
        return left_number <= right_number, None
    return False, f"未知运算符: {op}"


@register_executor
class AssertCheckpointExecutor(ModuleExecutor):
    def requires_browser_for(self, config: dict[str, Any]) -> bool:
        return config.get("checkType", "variable") == "element"

    @property
    def module_type(self) -> str:
        return "assert_checkpoint"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        check_type = str(
            context.resolve_value(config.get("checkType", "variable")) or "variable"
        ).strip()
        on_fail = str(config.get("onFail", "stop") or "stop").strip()
        variable_name = config.get("variableName", "") or ""
        label = config.get("message", "") or ""
        if check_type == "variable":
            passed, detail, error = self._check_variable(config, context)
        elif check_type == "element":
            passed, detail, error = await self._check_element(config, context)
        elif check_type == "expression":
            passed, detail, error = self._check_expression(config, context)
        else:
            return ModuleResult(success=False, error=f"未知检查类型: {check_type}")
        if error:
            return ModuleResult(success=False, error=error)
        if variable_name:
            context.set_variable(str(variable_name), passed)
        title = label or detail
        if passed:
            return ModuleResult(
                success=True,
                message=f"断言通过: {title}",
                data={"passed": True, "detail": detail},
            )
        fail_message = f"断言失败: {title}"
        if on_fail == "stop":
            return ModuleResult(
                success=False,
                error=fail_message,
                data={"passed": False, "detail": detail},
            )
        try:
            await context.send_progress(fail_message, "warning")
        except Exception:  # noqa: BLE001, S110 -- progress is best effort.
            pass
        return ModuleResult(
            success=True,
            message=f"{fail_message}（已设为继续）",
            data={"passed": False, "detail": detail},
            skipped=on_fail == "continue",
        )

    def _check_variable(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> tuple[bool, str, str | None]:
        raw_left = config.get("actualValue")
        if raw_left in (None, ""):
            raw_left = config.get("leftValue", "")
        raw_right = config.get("expectedValue")
        if raw_right is None:
            raw_right = config.get("rightValue", "")
        operator = str(config.get("operator", "==") or "==").strip()
        left = context.resolve_value(raw_left)
        right = context.resolve_value(raw_right)
        passed, error = _compare(left, right, operator)
        if error:
            return False, "", error
        detail = f"{left!r} {operator} {right!r}"
        if operator in ("isEmpty", "is_empty", "isNotEmpty", "is_not_empty"):
            detail = f"{left!r} {operator}"
        return passed, detail, None

    def _check_expression(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> tuple[bool, str, None]:
        raw = config.get("expression", "")
        value = context.resolve_value(raw)
        if isinstance(value, str):
            passed = value.strip().lower() not in (
                "false",
                "0",
                "no",
                "",
                "none",
                "null",
            )
        elif isinstance(value, (int, float)):
            passed = value != 0
        elif isinstance(value, (list, dict, tuple)):
            passed = len(value) > 0
        elif value is None:
            passed = False
        else:
            passed = bool(value)
        return passed, f"表达式 {raw!r} → {value!r}", None

    async def _check_element(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> tuple[bool, str, str | None]:
        page = _page(context)
        if page is None:
            return False, "", "没有打开的页面，请先使用'打开网页'模块"
        selector = context.resolve_value(
            config.get("selector", "") or config.get("leftValue", "")
        )
        if not selector:
            return False, "", "元素选择器不能为空"
        element_check = str(config.get("elementCheck", "exists") or "exists").strip()
        expected_text = context.resolve_value(config.get("expectedText", ""))
        try:
            locator = page.locator(format_selector(str(selector)))
            count = await locator.count()
            if element_check == "exists":
                return count > 0, f"元素 {selector!r} 存在", None
            if element_check == "not_exists":
                return count == 0, f"元素 {selector!r} 不存在", None
            if element_check == "visible":
                visible = count > 0 and await locator.first.is_visible()
                return visible, f"元素 {selector!r} 可见", None
            if element_check == "hidden":
                visible = count > 0 and await locator.first.is_visible()
                return not visible, f"元素 {selector!r} 隐藏", None
            text = (await locator.first.inner_text()) or "" if count > 0 else ""
            if element_check == "text_contains":
                return (
                    str(expected_text) in text,
                    f"元素文本包含 {expected_text!r}（实际 {text[:50]!r}）",
                    None,
                )
            if element_check == "text_equals":
                return (
                    text.strip() == str(expected_text).strip(),
                    f"元素文本等于 {expected_text!r}（实际 {text[:50]!r}）",
                    None,
                )
            return False, "", f"未知元素检查: {element_check}"
        except Exception as error:  # noqa: BLE001 -- frozen node semantics.
            return False, "", f"元素断言异常: {error}"


CONTROL_VARIABLE_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    ConditionExecutor,
    LoopExecutor,
    ForeachExecutor,
    InfiniteLoopExecutor,
    ForeachDictExecutor,
    BreakLoopExecutor,
    ContinueLoopExecutor,
    SetVariableExecutor,
    IncrementDecrementExecutor,
    JsonParseExecutor,
    Base64Executor,
    RandomNumberExecutor,
    GetTimeExecutor,
    WaitExecutor,
    StopWorkflowExecutor,
    AssertCheckpointExecutor,
)
