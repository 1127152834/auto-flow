from copy import deepcopy
from typing import Any

# Project tasks admit the five-node Studio bridge; other families require
# their project resource ports before admission.
_RUNNABLE_MODULES = (
    ("open_page", "打开网页"),
    ("input_text", "输入文本"),
    ("click_element", "点击元素"),
    ("get_element_info", "读取文本"),
    ("screenshot", "网页截图"),
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
