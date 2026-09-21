from copy import deepcopy
from typing import Any

# PM3 Task 4/6 freezes the first worker chain to navigation, input, click and
# text extraction. Other Studio modules remain valid draft content.
_RUNNABLE_MODULES = (
    ("open_page", "打开网页"),
    ("input_text", "输入文本"),
    ("click_element", "点击元素"),
    ("get_element_info", "读取文本"),
    ("condition", "条件判断"),
    ("loop", "循环"),
    ("foreach", "遍历列表"),
    ("foreach_dict", "遍历字典"),
    ("break_loop", "跳出循环"),
    ("continue_loop", "继续循环"),
    ("set_variable", "设置变量"),
    ("subflow", "项目子流程"),
    ("project_data", "项目数据"),
    ("project_manual", "人工处理"),
    ("project_end", "结束并保留环境"),
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
