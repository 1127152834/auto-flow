"""字典高级操作模块执行器"""

from __future__ import annotations

# ruff: noqa: BLE001 -- frozen executors convert every operation error to ModuleResult.
# Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
# backend/app/executors/dict_advanced.py.
import asyncio
import copy

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor


async def _checkpoint(context: ExecutionContext, index: int) -> None:
    if context.cancellation is None or index % 256:
        return
    context.cancellation.raise_if_cancelled()
    await asyncio.sleep(0)
    context.cancellation.raise_if_cancelled()


_MAX_NESTING_DEPTH = 256
_MAX_COLLECTION_ITEMS = 100_000


def _credential_safe_expression_error(
    prefix: str, error: Exception, source: object
) -> str:
    from .safe_expr import format_expression_error

    return format_expression_error(prefix, error, source)


@register_executor
class DictMergeExecutor(ModuleExecutor):
    """字典合并模块执行器"""

    @property
    def module_type(self) -> str:
        return "dict_merge"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        try:
            # 字段与前端面板对齐: dict1/dict2 两个字典变量名；兼容旧字段 dictVariables(逗号分隔)
            dict_variables = context.resolve_value(config.get("dictVariables", ""))
            if dict_variables:
                var_names = [
                    v.strip() for v in str(dict_variables).split(",") if v.strip()
                ]
            else:
                d1 = context.resolve_value(config.get("dict1", ""))
                d2 = context.resolve_value(config.get("dict2", ""))
                var_names = [str(x).strip() for x in (d1, d2) if x not in ("", None)]
            result_variable = config.get("resultVariable", "")

            if not var_names:
                return ModuleResult(success=False, error="字典变量名不能为空")
            if not result_variable:
                return ModuleResult(success=False, error="结果变量名不能为空")

            result = {}

            for index, var_name in enumerate(var_names):
                await _checkpoint(context, index)
                dict_data = context.get_variable(var_name)
                if dict_data is not None and isinstance(dict_data, dict):
                    result.update(dict_data)

            context.set_variable(result_variable, result)
            return ModuleResult(
                success=True,
                message=f"字典合并完成，共 {len(result)} 个键",
                data=result,
            )
        except Exception as e:
            return ModuleResult(success=False, error=f"合并失败: {e!s}")


@register_executor
class DictFilterExecutor(ModuleExecutor):
    """字典过滤模块执行器"""

    @property
    def module_type(self) -> str:
        return "dict_filter"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        try:
            dict_variable = context.resolve_value(config.get("dictVariable", ""))
            # 字段与前端面板对齐: condition(表达式，值以 v、键以 k 引用，如 "v > 10")
            condition = context.resolve_value(config.get("condition", ""))
            filter_keys = context.resolve_value(config.get("filterKeys", ""))
            filter_mode = context.resolve_value(config.get("filterMode", "include"))
            result_variable = config.get("resultVariable", "")

            if not dict_variable:
                return ModuleResult(success=False, error="字典变量名不能为空")
            if not result_variable:
                return ModuleResult(success=False, error="结果变量名不能为空")

            dict_data = context.get_variable(dict_variable)
            if dict_data is None:
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不存在"
                )
            if not isinstance(dict_data, dict):
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不是字典类型"
                )

            # 优先使用面板的表达式过滤（值以 v、键以 k 引用）
            if condition:
                from .safe_expr import UnsafeExpressionError, safe_eval

                expression_source = config.get("condition", "")

                try:
                    result = {}
                    for index, (k, v) in enumerate(dict_data.items()):
                        await _checkpoint(context, index)
                        if safe_eval(condition, {"v": v, "k": k}):
                            result[k] = v
                except UnsafeExpressionError as e:
                    return ModuleResult(
                        success=False,
                        error=_credential_safe_expression_error(
                            "过滤条件不合法", e, expression_source
                        ),
                    )
                except Exception as e:
                    return ModuleResult(
                        success=False,
                        error=_credential_safe_expression_error(
                            "过滤条件求值失败", e, expression_source
                        ),
                    )
                context.set_variable(result_variable, result)
                return ModuleResult(
                    success=True,
                    message=f"过滤完成，保留 {len(result)} 个键",
                    data=result,
                )

            if filter_mode not in {"include", "exclude"}:
                return ModuleResult(
                    success=False, error=f"不支持的过滤模式: {filter_mode}"
                )

            keys = [k.strip() for k in filter_keys.split(",") if k.strip()]

            if filter_mode == "include":
                result = {}
                for index, (k, v) in enumerate(dict_data.items()):
                    await _checkpoint(context, index)
                    if k in keys:
                        result[k] = v
            else:  # exclude
                result = {}
                for index, (k, v) in enumerate(dict_data.items()):
                    await _checkpoint(context, index)
                    if k not in keys:
                        result[k] = v

            context.set_variable(result_variable, result)
            return ModuleResult(
                success=True, message=f"过滤完成，保留 {len(result)} 个键", data=result
            )
        except Exception as e:
            return ModuleResult(success=False, error=f"过滤失败: {e!s}")


@register_executor
class DictMapValuesExecutor(ModuleExecutor):
    """字典映射值模块执行器"""

    @property
    def module_type(self) -> str:
        return "dict_map_values"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        try:
            dict_variable = context.resolve_value(config.get("dictVariable", ""))
            # 字段与前端面板对齐: expression(表达式，值以 v、键以 k 引用，如 "v * 2")
            expression = context.resolve_value(config.get("expression", ""))
            operation = context.resolve_value(config.get("operation", "multiply"))
            operand = context.resolve_value(config.get("operand", "1"))
            result_variable = config.get("resultVariable", "")

            if not dict_variable:
                return ModuleResult(success=False, error="字典变量名不能为空")
            if not result_variable:
                return ModuleResult(success=False, error="结果变量名不能为空")

            dict_data = context.get_variable(dict_variable)
            if dict_data is None:
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不存在"
                )
            if not isinstance(dict_data, dict):
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不是字典类型"
                )

            # 优先使用面板的表达式映射（值以 v、键以 k 引用）
            if expression:
                from .safe_expr import UnsafeExpressionError, safe_eval

                expression_source = config.get("expression", "")

                try:
                    result = {}
                    for index, (k, v) in enumerate(dict_data.items()):
                        await _checkpoint(context, index)
                        result[k] = safe_eval(expression, {"v": v, "k": k})
                except UnsafeExpressionError as e:
                    return ModuleResult(
                        success=False,
                        error=_credential_safe_expression_error(
                            "映射表达式不合法", e, expression_source
                        ),
                    )
                except Exception as e:
                    return ModuleResult(
                        success=False,
                        error=_credential_safe_expression_error(
                            "映射表达式求值失败", e, expression_source
                        ),
                    )
                context.set_variable(result_variable, result)
                return ModuleResult(
                    success=True,
                    message=f"映射完成，处理 {len(result)} 个键值对",
                    data=result,
                )

            if operation not in {"multiply", "divide", "add", "subtract"}:
                return ModuleResult(
                    success=False, error=f"不支持的映射操作: {operation}"
                )

            result = {}
            op_val = float(operand)

            for index, (key, value) in enumerate(dict_data.items()):
                await _checkpoint(context, index)
                if not isinstance(value, (int, float)):
                    try:
                        value = float(value)
                    except Exception:
                        result[key] = value
                        continue

                if operation == "multiply":
                    result[key] = value * op_val
                elif operation == "divide":
                    result[key] = value / op_val if op_val != 0 else value
                elif operation == "add":
                    result[key] = value + op_val
                elif operation == "subtract":
                    result[key] = value - op_val

            context.set_variable(result_variable, result)
            return ModuleResult(
                success=True,
                message=f"映射完成，处理 {len(result)} 个键值对",
                data=result,
            )
        except Exception as e:
            return ModuleResult(success=False, error=f"映射失败: {e!s}")


@register_executor
class DictInvertExecutor(ModuleExecutor):
    """字典反转模块执行器"""

    @property
    def module_type(self) -> str:
        return "dict_invert"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        try:
            dict_variable = context.resolve_value(config.get("dictVariable", ""))
            result_variable = config.get("resultVariable", "")

            if not dict_variable:
                return ModuleResult(success=False, error="字典变量名不能为空")
            if not result_variable:
                return ModuleResult(success=False, error="结果变量名不能为空")

            dict_data = context.get_variable(dict_variable)
            if dict_data is None:
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不存在"
                )
            if not isinstance(dict_data, dict):
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不是字典类型"
                )
            if len(dict_data) > _MAX_COLLECTION_ITEMS:
                return ModuleResult(
                    success=False, error="字典规模超过工作流安全限制"
                )

            result = {}
            for index, (k, v) in enumerate(dict_data.items()):
                await _checkpoint(context, index)
                result[str(v)] = k
            context.set_variable(result_variable, result)
            return ModuleResult(
                success=True,
                message=f"字典反转完成，共 {len(result)} 个键值对",
                data=result,
            )
        except Exception as e:
            return ModuleResult(success=False, error=f"反转失败: {e!s}")


@register_executor
class DictSortExecutor(ModuleExecutor):
    """字典排序模块执行器"""

    @property
    def module_type(self) -> str:
        return "dict_sort"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        try:
            dict_variable = context.resolve_value(config.get("dictVariable", ""))
            sort_by = context.resolve_value(config.get("sortBy", "key"))
            # 字段与前端面板对齐: order(asc/desc)，兼容旧字段名 sortOrder
            sort_order = context.resolve_value(
                config.get("sortOrder", config.get("order", "asc"))
            )
            result_variable = config.get("resultVariable", "")

            if not dict_variable:
                return ModuleResult(success=False, error="字典变量名不能为空")
            if not result_variable:
                return ModuleResult(success=False, error="结果变量名不能为空")

            dict_data = context.get_variable(dict_variable)
            if dict_data is None:
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不存在"
                )
            if not isinstance(dict_data, dict):
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不是字典类型"
                )
            if sort_by not in {"key", "value"}:
                return ModuleResult(
                    success=False, error=f"不支持的排序字段: {sort_by}"
                )
            if sort_order not in {"asc", "desc"}:
                return ModuleResult(
                    success=False, error=f"不支持的排序顺序: {sort_order}"
                )
            if len(dict_data) > _MAX_COLLECTION_ITEMS:
                return ModuleResult(
                    success=False, error="字典规模超过工作流安全限制"
                )

            reverse = sort_order == "desc"

            await _checkpoint(context, 0)
            if sort_by == "key":
                result = dict(
                    sorted(dict_data.items(), key=lambda x: x[0], reverse=reverse)
                )
            else:  # sort by value
                result = dict(
                    sorted(dict_data.items(), key=lambda x: x[1], reverse=reverse)
                )

            await _checkpoint(context, 0)
            context.set_variable(result_variable, result)
            order_text = "降序" if reverse else "升序"
            by_text = "键" if sort_by == "key" else "值"
            return ModuleResult(
                success=True, message=f"按{by_text}{order_text}排序完成", data=result
            )
        except Exception as e:
            return ModuleResult(success=False, error=f"排序失败: {e!s}")


@register_executor
class DictDeepCopyExecutor(ModuleExecutor):
    """字典深拷贝模块执行器"""

    @property
    def module_type(self) -> str:
        return "dict_deep_copy"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        try:
            dict_variable = context.resolve_value(config.get("dictVariable", ""))
            result_variable = config.get("resultVariable", "")

            if not dict_variable:
                return ModuleResult(success=False, error="字典变量名不能为空")
            if not result_variable:
                return ModuleResult(success=False, error="结果变量名不能为空")

            dict_data = context.get_variable(dict_variable)
            if dict_data is None:
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不存在"
                )
            if not isinstance(dict_data, dict):
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不是字典类型"
                )
            if len(dict_data) > _MAX_COLLECTION_ITEMS:
                return ModuleResult(
                    success=False, error="字典规模超过工作流安全限制"
                )

            await _checkpoint(context, 0)
            result = copy.deepcopy(dict_data)
            await _checkpoint(context, 0)
            context.set_variable(result_variable, result)
            return ModuleResult(success=True, message="字典深拷贝完成", data=result)
        except Exception as e:
            return ModuleResult(success=False, error=f"深拷贝失败: {e!s}")


@register_executor
class DictGetPathExecutor(ModuleExecutor):
    """字典路径取值模块执行器"""

    @property
    def module_type(self) -> str:
        return "dict_get_path"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        try:
            dict_variable = context.resolve_value(config.get("dictVariable", ""))
            path = context.resolve_value(config.get("path", ""))
            default_value = context.resolve_value(config.get("defaultValue", ""))
            result_variable = config.get("resultVariable", "")

            if not dict_variable:
                return ModuleResult(success=False, error="字典变量名不能为空")
            if not path:
                return ModuleResult(success=False, error="路径不能为空")
            if not result_variable:
                return ModuleResult(success=False, error="结果变量名不能为空")

            dict_data = context.get_variable(dict_variable)
            if dict_data is None:
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不存在"
                )
            if not isinstance(dict_data, dict):
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不是字典类型"
                )

            keys = path.split(".")
            result = dict_data

            for index, key in enumerate(keys):
                await _checkpoint(context, index)
                if isinstance(result, dict) and key in result:
                    result = result[key]
                else:
                    result = default_value
                    break

            context.set_variable(result_variable, result)
            return ModuleResult(
                success=True, message=f"路径取值完成: {path}", data=result
            )
        except Exception as e:
            return ModuleResult(success=False, error=f"路径取值失败: {e!s}")


@register_executor
class DictFlattenExecutor(ModuleExecutor):
    """字典扁平化模块执行器"""

    @property
    def module_type(self) -> str:
        return "dict_flatten"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        try:
            dict_variable = context.resolve_value(config.get("dictVariable", ""))
            separator = context.resolve_value(config.get("separator", "."))
            result_variable = config.get("resultVariable", "")

            if not dict_variable:
                return ModuleResult(success=False, error="字典变量名不能为空")
            if not result_variable:
                return ModuleResult(success=False, error="结果变量名不能为空")

            dict_data = context.get_variable(dict_variable)
            if dict_data is None:
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不存在"
                )
            if not isinstance(dict_data, dict):
                return ModuleResult(
                    success=False, error=f"变量 '{dict_variable}' 不是字典类型"
                )

            async def flatten_dict(d, parent_key="", depth=0, active_ids=None):
                if depth > _MAX_NESTING_DEPTH:
                    raise ValueError("字典嵌套超过工作流安全限制")
                if active_ids is None:
                    active_ids = set()
                dict_id = id(d)
                if dict_id in active_ids:
                    raise ValueError("字典包含循环引用")
                active_ids.add(dict_id)
                items = []
                try:
                    for index, (k, v) in enumerate(d.items()):
                        await _checkpoint(context, index)
                        new_key = f"{parent_key}{separator}{k}" if parent_key else k
                        if isinstance(v, dict):
                            nested = await flatten_dict(
                                v, new_key, depth + 1, active_ids
                            )
                            items.extend(nested.items())
                        else:
                            items.append((new_key, v))
                finally:
                    active_ids.remove(dict_id)
                return dict(items)

            result = await flatten_dict(dict_data)
            context.set_variable(result_variable, result)
            return ModuleResult(
                success=True,
                message=f"字典扁平化完成，共 {len(result)} 个键",
                data=result,
            )
        except Exception as e:
            return ModuleResult(success=False, error=f"扁平化失败: {e!s}")
