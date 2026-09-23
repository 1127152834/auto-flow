from copy import deepcopy
from typing import Any

# Project tasks reuse the approved browser bridge and pure-data executors.
# Families with additional resource ports stay gated until those ports are wired.
_RUNNABLE_MODULES = (
    ("open_page", "打开网页"),
    ("input_text", "输入文本"),
    ("click_element", "点击元素"),
    ("get_element_info", "读取文本"),
    ("screenshot", "网页截图"),
    ("csv_generate", "CSV生成"),
    ("csv_parse", "CSV解析"),
    ("dict_deep_copy", "字典深拷贝"),
    ("dict_filter", "字典过滤"),
    ("dict_flatten", "字典扁平化"),
    ("dict_get_path", "字典路径取值"),
    ("dict_invert", "字典反转"),
    ("dict_map_values", "字典映射值"),
    ("dict_merge", "字典合并"),
    ("dict_sort", "字典排序"),
    ("list_cartesian_product", "列表笛卡尔积"),
    ("list_chunk", "列表分组"),
    ("list_count", "列表计数"),
    ("list_difference", "列表差集"),
    ("list_filter", "列表过滤"),
    ("list_find", "列表查找"),
    ("list_flatten", "列表扁平化"),
    ("list_intersection", "列表交集"),
    ("list_map", "列表映射"),
    ("list_merge", "列表合并"),
    ("list_remove_empty", "列表去空"),
    ("list_reverse", "列表反转"),
    ("list_sample", "列表采样"),
    ("list_shuffle", "列表随机打乱"),
    ("list_to_string_advanced", "列表转字符串（高级）"),
    ("list_union", "列表并集"),
)


def node_catalog() -> list[dict[str, Any]]:
    return deepcopy(
        [
            {"moduleType": module_type, "title": title, "runnable": True}
            for module_type, title in _RUNNABLE_MODULES
        ]
    )


def runnable_module_types() -> frozenset[str]:
    return frozenset(module_type for module_type, _title in _RUNNABLE_MODULES)
