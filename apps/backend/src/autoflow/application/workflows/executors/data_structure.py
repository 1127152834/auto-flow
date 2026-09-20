"""Frozen WebRPA list, dictionary, string, and regex executors for AutoFlow.

Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
backend/app/executors/data_structure.py. This file contains all 15 approved nodes;
file publication is adapted to AutoFlow's run-bound artifact writer.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import regex
from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor
from .type_utils import to_int


@register_executor
class ListOperationExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "list_operation"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        list_variable = config.get("listVariable", "")
        action = context.resolve_value(config.get("listAction", "append"))
        value = context.resolve_value(config.get("listValue", ""))
        index = to_int(config.get("listIndex", 0), 0, context)
        result_variable = config.get("resultVariable", "")
        if not list_variable:
            return ModuleResult(success=False, error="列表变量名不能为空")
        list_data = context.get_variable(list_variable)
        if list_data is None:
            list_data = []
        if not isinstance(list_data, list):
            return ModuleResult(
                success=False, error=f"变量 '{list_variable}' 不是列表类型"
            )

        try:
            if action == "append":
                list_data.append(value)
                message = f"已追加元素: {value}"
            elif action == "insert":
                list_data.insert(index, value)
                message = f"已在位置 {index} 插入元素: {value}"
            elif action == "remove":
                if value not in list_data:
                    return ModuleResult(
                        success=False, error=f"列表中不存在元素: {value}"
                    )
                list_data.remove(value)
                message = f"已删除元素: {value}"
            elif action == "pop":
                if not list_data:
                    return ModuleResult(success=False, error="列表为空，无法弹出元素")
                if index < -len(list_data) or index >= len(list_data):
                    return ModuleResult(success=False, error=f"索引 {index} 超出范围")
                popped = list_data.pop(index)
                if result_variable:
                    context.set_variable(result_variable, popped)
                message = f"已弹出位置 {index} 的元素: {popped}"
            elif action == "clear":
                list_data.clear()
                message = "已清空列表"
            elif action == "reverse":
                list_data.reverse()
                message = "已反转列表"
            elif action == "sort":
                try:
                    list_data.sort()
                    message = "已排序列表"
                except TypeError:
                    return ModuleResult(
                        success=False, error="列表元素类型不一致，无法排序"
                    )
            else:
                return ModuleResult(success=False, error=f"不支持的操作: {action}")
            context.set_variable(list_variable, list_data)
            return ModuleResult(
                success=True,
                message=message,
                data={"list": list_data, "length": len(list_data)},
            )
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"列表操作失败: {error}")


@register_executor
class ListGetExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "list_get"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        list_variable = config.get("listVariable", "")
        index_str = context.resolve_value(str(config.get("listIndex", "0")))
        variable_name = config.get("variableName", "")
        if not list_variable:
            return ModuleResult(success=False, error="列表变量名不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")
        list_data = context.get_variable(list_variable)
        if list_data is None:
            return ModuleResult(success=False, error=f"变量 '{list_variable}' 不存在")
        if not isinstance(list_data, list):
            return ModuleResult(
                success=False, error=f"变量 '{list_variable}' 不是列表类型"
            )
        try:
            index = int(index_str)
        except ValueError:
            return ModuleResult(success=False, error=f"无效的索引值: {index_str}")
        if not list_data:
            return ModuleResult(success=False, error="列表为空")
        if index < -len(list_data) or index >= len(list_data):
            return ModuleResult(success=False, error=f"索引 {index} 超出范围")
        value = list_data[index]
        context.set_variable(variable_name, value)
        return ModuleResult(
            success=True, message=f"获取列表[{index}] = {value}", data=value
        )


@register_executor
class ListLengthExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "list_length"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        list_variable = config.get("listVariable", "")
        variable_name = config.get("variableName", "")
        if not list_variable:
            return ModuleResult(success=False, error="列表变量名不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")
        list_data = context.get_variable(list_variable)
        if list_data is None:
            return ModuleResult(success=False, error=f"变量 '{list_variable}' 不存在")
        if not isinstance(list_data, list):
            return ModuleResult(
                success=False, error=f"变量 '{list_variable}' 不是列表类型"
            )
        length = len(list_data)
        context.set_variable(variable_name, length)
        return ModuleResult(success=True, message=f"列表长度: {length}", data=length)


@register_executor
class ListExportExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "list_export"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        list_variable = config.get("listVariable", "")
        output_path = context.resolve_value(config.get("outputPath", ""))
        separator = context.resolve_value(config.get("separator", "\n"))
        encoding = context.resolve_value(config.get("encoding", "utf-8"))
        append_mode_raw = config.get("appendMode", False)
        if isinstance(append_mode_raw, str):
            append_mode_raw = context.resolve_value(append_mode_raw)
        append_mode = append_mode_raw in [True, "true", "True", "1", 1]

        if not list_variable:
            return ModuleResult(success=False, error="列表变量名不能为空")
        if not output_path:
            return ModuleResult(success=False, error="输出文件路径不能为空")

        list_data = context.get_variable(list_variable)
        if list_data is None:
            return ModuleResult(success=False, error=f"变量 '{list_variable}' 不存在")
        if not isinstance(list_data, list):
            return ModuleResult(
                success=False, error=f"变量 '{list_variable}' 不是列表类型"
            )

        try:
            if separator == "\\n":
                separator = "\n"
            elif separator == "\\t":
                separator = "\t"
            elif separator == "\\r\\n":
                separator = "\r\n"

            lines: list[str] = []
            for index, item in enumerate(list_data):
                if context.cancellation is not None:
                    context.cancellation.raise_if_cancelled()
                lines.append(
                    json.dumps(item, ensure_ascii=False)
                    if isinstance(item, (dict, list))
                    else str(item)
                )
                if index and index % 256 == 0:
                    await asyncio.sleep(0)
            content = separator.join(lines)
            if context.node_artifacts is None:
                raise RuntimeError("文件输出服务不可用")
            await context.node_artifacts.write_text(
                output_path=output_path,
                content=content,
                separator=separator,
                encoding=encoding,
                append=append_mode,
                mime_type="text/plain",
            )
            return ModuleResult(
                success=True,
                message=f"已导出 {len(list_data)} 条数据到: {output_path}",
                data={"path": output_path, "count": len(list_data)},
            )
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"导出失败: {error}")


@register_executor
class DictOperationExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "dict_operation"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        dict_variable = config.get("dictVariable", "")
        action = context.resolve_value(config.get("dictAction", "set"))
        key = context.resolve_value(config.get("dictKey", ""))
        value = context.resolve_value(config.get("dictValue", ""))
        if not dict_variable:
            return ModuleResult(success=False, error="字典变量名不能为空")
        dict_data = context.get_variable(dict_variable)
        if dict_data is None:
            dict_data = {}
        if not isinstance(dict_data, dict):
            return ModuleResult(
                success=False, error=f"变量 '{dict_variable}' 不是字典类型"
            )

        try:
            if action == "set":
                if not key:
                    return ModuleResult(success=False, error="键名不能为空")
                dict_data[key] = value
                message = f"已设置 {key} = {value}"
            elif action == "delete":
                if not key:
                    return ModuleResult(success=False, error="键名不能为空")
                if key not in dict_data:
                    return ModuleResult(success=False, error=f"键 '{key}' 不存在")
                del dict_data[key]
                message = f"已删除键: {key}"
            elif action == "clear":
                dict_data.clear()
                message = "已清空字典"
            else:
                return ModuleResult(success=False, error=f"不支持的操作: {action}")
            context.set_variable(dict_variable, dict_data)
            return ModuleResult(
                success=True,
                message=message,
                data={"dict": dict_data, "keys": list(dict_data.keys())},
            )
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"字典操作失败: {error}")


@register_executor
class DictGetExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "dict_get"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        dict_variable = config.get("dictVariable", "")
        key = context.resolve_value(config.get("dictKey", ""))
        default_value = context.resolve_value(config.get("defaultValue", ""))
        variable_name = config.get("variableName", "")
        if not dict_variable:
            return ModuleResult(success=False, error="字典变量名不能为空")
        if not key:
            return ModuleResult(success=False, error="键名不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")
        dict_data = context.get_variable(dict_variable)
        if dict_data is None:
            return ModuleResult(success=False, error=f"变量 '{dict_variable}' 不存在")
        if not isinstance(dict_data, dict):
            return ModuleResult(
                success=False, error=f"变量 '{dict_variable}' 不是字典类型"
            )
        if key in dict_data:
            value = dict_data[key]
            message = f"获取 {key} = {value}"
        else:
            value = default_value if default_value else None
            message = f"键 '{key}' 不存在，使用默认值: {value}"
        context.set_variable(variable_name, value)
        return ModuleResult(success=True, message=message, data=value)


@register_executor
class DictKeysExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "dict_keys"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        dict_variable = config.get("dictVariable", "")
        key_type = context.resolve_value(config.get("keyType", "keys"))
        variable_name = config.get("variableName", "")
        if not dict_variable:
            return ModuleResult(success=False, error="字典变量名不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")
        dict_data = context.get_variable(dict_variable)
        if dict_data is None:
            return ModuleResult(success=False, error=f"变量 '{dict_variable}' 不存在")
        if not isinstance(dict_data, dict):
            return ModuleResult(
                success=False, error=f"变量 '{dict_variable}' 不是字典类型"
            )
        if key_type == "keys":
            result = list(dict_data.keys())
            message = f"获取所有键: {result}"
        elif key_type == "values":
            result = list(dict_data.values())
            message = f"获取所有值: {result}"
        elif key_type == "items":
            result = [[key, value] for key, value in dict_data.items()]
            message = f"获取所有键值对: {len(result)} 对"
        else:
            return ModuleResult(success=False, error=f"不支持的类型: {key_type}")
        context.set_variable(variable_name, result)
        return ModuleResult(success=True, message=message, data=result)


@register_executor
class RegexExtractExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "regex_extract"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        input_text = context.resolve_value(config.get("inputText", ""))
        pattern = context.resolve_value(config.get("pattern", ""))
        extract_mode = context.resolve_value(config.get("extractMode", "first"))
        ignore_case_raw = config.get("ignoreCase", False)
        if isinstance(ignore_case_raw, str):
            ignore_case_raw = context.resolve_value(ignore_case_raw)
        ignore_case = ignore_case_raw in [True, "true", "True", "1", 1]
        variable_name = config.get("variableName", "")

        if not input_text:
            return ModuleResult(success=False, error="输入文本不能为空")
        if not pattern:
            return ModuleResult(success=False, error="正则表达式不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")

        try:
            flags = regex.IGNORECASE if ignore_case else 0
            compiled_regex = regex.compile(pattern, flags)
            result: Any
            if extract_mode == "first":
                match = compiled_regex.search(str(input_text))
                if match:
                    result = match.group(0)
                    message = f"匹配到: {result}"
                else:
                    result = None
                    message = "未找到匹配"
            elif extract_mode == "all":
                matches = compiled_regex.findall(str(input_text))
                result = matches
                message = f"找到 {len(matches)} 个匹配"
            elif extract_mode == "groups":
                match = compiled_regex.search(str(input_text))
                if match:
                    groups = match.groups()
                    result = list(groups) if groups else [match.group(0)]
                    message = f"提取到 {len(result)} 个分组"
                else:
                    result = []
                    message = "未找到匹配"
            else:
                return ModuleResult(
                    success=False, error=f"不支持的提取模式: {extract_mode}"
                )
            context.set_variable(variable_name, result)
            return ModuleResult(success=True, message=message, data=result)
        except regex.error as error:
            error_msg = str(error)
            if "unbalanced parenthesis" in error_msg:
                return ModuleResult(success=False, error="正则表达式错误: 括号不匹配")
            if "nothing to repeat" in error_msg:
                return ModuleResult(
                    success=False, error="正则表达式错误: 重复符号前面没有内容"
                )
            return ModuleResult(success=False, error=f"正则表达式错误: {error_msg}")
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"提取失败: {error}")


@register_executor
class StringReplaceExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "string_replace"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        input_text = context.resolve_value(config.get("inputText", ""))
        replace_mode = context.resolve_value(config.get("replaceMode", "text"))
        search_value = context.resolve_value(config.get("searchValue", ""))
        replace_value = context.resolve_value(config.get("replaceValue", ""))
        replace_all_raw = config.get("replaceAll", True)
        if isinstance(replace_all_raw, str):
            replace_all_raw = context.resolve_value(replace_all_raw)
        replace_all = replace_all_raw in [True, "true", "True", "1", 1]
        variable_name = config.get("variableName", "")

        if not input_text:
            return ModuleResult(success=False, error="输入文本不能为空")
        if not search_value:
            return ModuleResult(success=False, error="查找内容不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")

        try:
            input_str = str(input_text)
            if replace_mode == "regex":
                result = regex.sub(
                    search_value,
                    replace_value,
                    input_str,
                    count=0 if replace_all else 1,
                )
            else:
                result = input_str.replace(
                    search_value, replace_value, -1 if replace_all else 1
                )
            context.set_variable(variable_name, result)
            return ModuleResult(success=True, message="替换完成", data=result)
        except regex.error as error:
            return ModuleResult(success=False, error=f"正则表达式错误: {error}")
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"替换失败: {error}")


@register_executor
class StringSplitExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "string_split"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        input_text = context.resolve_value(config.get("inputText", ""))
        separator = context.resolve_value(config.get("separator", ""))
        max_split = to_int(config.get("maxSplit", 0), 0, context)
        variable_name = config.get("variableName", "")

        if not input_text:
            return ModuleResult(success=False, error="输入文本不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")

        try:
            input_str = str(input_text)
            if separator == "\\n":
                separator = "\n"
            elif separator == "\\t":
                separator = "\t"
            if max_split > 0:
                result = input_str.split(separator, max_split)
            else:
                result = input_str.split(separator) if separator else input_str.split()
            context.set_variable(variable_name, result)
            return ModuleResult(
                success=True, message=f"分割为 {len(result)} 个部分", data=result
            )
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"分割失败: {error}")


@register_executor
class StringJoinExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "string_join"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        list_variable = config.get("listVariable", "")
        separator = context.resolve_value(config.get("separator", ""))
        variable_name = config.get("variableName", "")

        if not list_variable:
            return ModuleResult(success=False, error="列表变量名不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")
        list_data = context.get_variable(list_variable)
        if list_data is None:
            return ModuleResult(success=False, error=f"变量 '{list_variable}' 不存在")
        if not isinstance(list_data, list):
            return ModuleResult(
                success=False, error=f"变量 '{list_variable}' 不是列表类型"
            )

        try:
            str_list = [str(item) for item in list_data]
            result = separator.join(str_list)
            context.set_variable(variable_name, result)
            return ModuleResult(
                success=True, message=f"连接 {len(str_list)} 个元素", data=result
            )
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"连接失败: {error}")


@register_executor
class StringConcatExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "string_concat"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        string1 = context.resolve_value(config.get("string1", ""))
        string2 = context.resolve_value(config.get("string2", ""))
        variable_name = config.get("variableName", "")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")

        try:
            str1 = str(string1) if string1 is not None else ""
            str2 = str(string2) if string2 is not None else ""
            result = str1 + str2
            context.set_variable(variable_name, result)
            preview = result if len(result) <= 50 else result[:50] + "..."
            return ModuleResult(
                success=True, message=f"拼接结果: {preview}", data=result
            )
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"拼接失败: {error}")


@register_executor
class StringTrimExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "string_trim"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        input_text = context.resolve_value(config.get("inputText", ""))
        trim_mode = context.resolve_value(config.get("trimMode", "both"))
        variable_name = config.get("variableName", "")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")

        try:
            input_str = str(input_text) if input_text else ""
            if trim_mode == "both":
                result = input_str.strip()
            elif trim_mode == "start":
                result = input_str.lstrip()
            elif trim_mode == "end":
                result = input_str.rstrip()
            elif trim_mode == "all":
                result = "".join(input_str.split())
            else:
                return ModuleResult(
                    success=False, error=f"不支持的去除模式: {trim_mode}"
                )
            context.set_variable(variable_name, result)
            return ModuleResult(success=True, message="去除空白完成", data=result)
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"去除空白失败: {error}")


@register_executor
class StringCaseExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "string_case"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        input_text = context.resolve_value(config.get("inputText", ""))
        case_mode = context.resolve_value(config.get("caseMode", "upper"))
        variable_name = config.get("variableName", "")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")

        try:
            input_str = str(input_text) if input_text else ""
            if case_mode == "upper":
                result = input_str.upper()
            elif case_mode == "lower":
                result = input_str.lower()
            elif case_mode == "capitalize":
                result = input_str.capitalize()
            elif case_mode == "title":
                result = input_str.title()
            else:
                return ModuleResult(
                    success=False, error=f"不支持的转换模式: {case_mode}"
                )
            context.set_variable(variable_name, result)
            return ModuleResult(success=True, message="大小写转换完成", data=result)
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"大小写转换失败: {error}")


@register_executor
class StringSubstringExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "string_substring"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        input_text = context.resolve_value(config.get("inputText", ""))
        start_index = context.resolve_value(str(config.get("startIndex", "0")))
        end_index = context.resolve_value(str(config.get("endIndex", "")))
        variable_name = config.get("variableName", "")
        if not variable_name:
            return ModuleResult(success=False, error="存储变量名不能为空")

        try:
            input_str = str(input_text) if input_text else ""
            start = int(start_index) if start_index else 0
            result = (
                input_str[start : int(end_index)] if end_index else input_str[start:]
            )
            context.set_variable(variable_name, result)
            return ModuleResult(
                success=True,
                message=f"截取完成: {result[:50]}{'...' if len(result) > 50 else ''}",
                data=result,
            )
        except ValueError as error:
            return ModuleResult(success=False, error=f"索引值无效: {error}")
        except Exception as error:  # noqa: BLE001 -- preserve node-result semantics.
            return ModuleResult(success=False, error=f"截取失败: {error}")
