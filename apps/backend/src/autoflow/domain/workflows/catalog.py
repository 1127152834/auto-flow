from copy import deepcopy
from typing import Any

# AutoFlow's selected editing contract. WebRPA UI/executor field evidence is recorded
# in docs/superpowers/plans/2026-09-12-automation-studio-replication-method.md.
_TEXT = {"type": "string"}
_TIMEOUT = {"type": "number", "exclusiveMinimum": 0, "default": 60}


def _enum(*values: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values), "default": values[0]}


def _definition(
    node_type: str,
    title: str,
    description: str,
    properties: dict[str, Any],
    defaults: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    properties = {
        name: {**definition, **({"minLength": 1} if name in required else {})}
        for name, definition in properties.items()
    }
    if "selector" in properties:
        properties["framePath"] = {"type": "array", "items": {"type": "string", "minLength": 1}, "default": []}
        defaults = {**defaults, "framePath": []}
    return {
        "type": node_type,
        "title": title,
        "description": description,
        "category": "浏览器",
        "defaultConfig": {**defaults, "timeoutSeconds": 60},
        "configSchema": {
            "type": "object",
            "properties": {**properties, "timeoutSeconds": _TIMEOUT},
            "required": required,
            "additionalProperties": False,
        },
        "inputPorts": ["in"],
        "outputPorts": ["out"],
        "runnable": True,
    }


_DEFINITIONS = [
    _definition(
        "open_page",
        "打开网页",
        "在当前或新标签页打开网址。",
        {
            "url": _TEXT,
            "openMode": _enum("new_tab", "current_tab"),
            "waitUntil": _enum("load", "domcontentloaded", "networkidle"),
        },
        {"url": "", "openMode": "new_tab", "waitUntil": "load"},
        ["url"],
    ),
    _definition(
        "click_element",
        "点击元素",
        "点击 CSS 或 XPath 选择器定位的元素。",
        {
            "selector": _TEXT,
            "clickType": _enum("single", "double", "right"),
            "followNewTab": {"type": "boolean", "default": False},
        },
        {"selector": "", "clickType": "single", "followNewTab": False},
        ["selector"],
    ),
    _definition(
        "input_text",
        "输入文本",
        "替换或追加输入框中的文本。",
        {
            "selector": _TEXT,
            "text": _TEXT,
            "clearBefore": {"type": "boolean", "default": True},
        },
        {"selector": "", "text": "", "clearBefore": True},
        ["selector"],
    ),
    _definition(
        "wait_element",
        "等待元素",
        "等待元素可见、隐藏、出现或移除。",
        {
            "selector": _TEXT,
            "waitCondition": _enum("visible", "hidden", "attached", "detached"),
        },
        {"selector": "", "waitCondition": "visible"},
        ["selector"],
    ),
    _definition(
        "get_element_info",
        "提取数据",
        "提取文本、HTML 或属性到变量。",
        {
            "selector": _TEXT,
            "attribute": _enum(
                "text", "innerHTML", "value", "href", "src", "attributes"
            ),
            "variableName": _TEXT,
        },
        {"selector": "", "attribute": "text", "variableName": "element_value"},
        ["selector", "variableName"],
    ),
    _definition(
        "screenshot",
        "网页截图",
        "保存整页、视口或指定元素的截图。",
        {
            "screenshotType": _enum("fullpage", "viewport", "element"),
            "selector": _TEXT,
            "savePath": _TEXT,
            "variableName": _TEXT,
        },
        {
            "screenshotType": "fullpage",
            "selector": "",
            "savePath": "",
            "variableName": "screenshot_path",
        },
        ["variableName"],
    ),
]

# Recorder output must be executable through the same catalog and scheduler.
_DEFINITIONS[0]['configSchema']['properties']['pageAlias'] = _TEXT
_DEFINITIONS[0]['defaultConfig']['pageAlias'] = ''
_DEFINITIONS[1]['configSchema']['properties']['newPageAlias'] = _TEXT
_DEFINITIONS[1]['defaultConfig']['newPageAlias'] = ''
_DEFINITIONS[2]['configSchema']['properties'].update(inputMode=_enum('fill', 'sequential'), requiresValue={'type': 'boolean', 'default': False})
_DEFINITIONS[2]['defaultConfig'].update(inputMode='fill', requiresValue=False)

_DEFINITIONS[-1]["configSchema"]["allOf"] = [
    {
        "if": {
            "required": ["screenshotType"],
            "properties": {"screenshotType": {"const": "element"}},
        },
        "then": {
            "required": ["selector"],
            "properties": {"selector": {"type": "string", "minLength": 1}},
        },
    }
]


_VALUE = {"type": "object"}
_RULES = {"type": "array"}
_CONDITION = {"match": _enum("all", "any"), "rules": _RULES}
_RULE_DEFAULT = {"kind": "value", "operator": "eq", "left": {"kind": "literal", "value": True}, "right": {"kind": "literal", "value": True}}
_CONTROLS: list[tuple[str, str, dict[str, Any], dict[str, Any], list[str]]] = [
    ("condition", "条件判断", {**_CONDITION, "endNodeId": _TEXT}, {"match": "all", "rules": [_RULE_DEFAULT], "endNodeId": ""}, ["true", "false"]),
    ("condition_end", "条件结束", {"ownerNodeId": _TEXT}, {"ownerNodeId": ""}, ["out"]),
    ("loop", "循环", {**_CONDITION, "endNodeId": _TEXT, "mode": _enum("count", "foreach", "while"), "source": _VALUE, "indexVariable": _TEXT, "itemVariable": _TEXT, "maxIterations": {"type": "number"}},
     {"endNodeId": "", "mode": "count", "source": {"kind": "literal", "value": 1}, "indexVariable": "index", "itemVariable": "item", "maxIterations": 1000, "match": "all", "rules": [_RULE_DEFAULT]}, ["body", "done"]),
    ("loop_end", "循环结束", {"ownerNodeId": _TEXT}, {"ownerNodeId": ""}, []),
    ("break_loop", "退出循环", {}, {}, []),
    ("continue_loop", "跳过本次循环", {}, {}, []),
    ("set_variable", "设置变量", {"variableName": _TEXT, "operation": _enum("assign", "add", "subtract", "append"), "value": _VALUE},
     {"variableName": "", "operation": "assign", "value": {"kind": "literal", "value": 1}}, ["out"]),
]
for kind, title, properties, defaults, outputs in _CONTROLS:
    definition = _definition(kind, title, title, properties, defaults, ["variableName"] if kind == "set_variable" else [])
    definition.update(category="流程控制", outputPorts=outputs)
    _DEFINITIONS.append(definition)


_DEFINITIONS.extend([
    _definition('select_option', '选择下拉选项', '按原生选项值精确选择。',
                {'selector': _TEXT, 'values': {'type': 'array', 'items': _TEXT}}, {'selector': '', 'values': []}, ['selector', 'values']),
    _definition('set_checked', '设置勾选状态', '设置原生复选框或单选按钮状态。',
                {'selector': _TEXT, 'checked': {'type': 'boolean'}}, {'selector': '', 'checked': True}, ['selector']),
    _definition('press_key', '按键', '向明确元素发送业务按键。',
                {'selector': _TEXT, 'key': _enum('Enter', 'Tab', 'Escape', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'),
                 'followNewTab': {'type': 'boolean'}, 'newPageAlias': _TEXT},
                {'selector': '', 'key': 'Enter', 'followNewTab': False, 'newPageAlias': ''}, ['selector']),
    _definition('scroll_page', '滚动页面或元素', '设置当前框架文档或容器的绝对滚动位置。',
                {'target': _enum('page', 'element'), 'selector': _TEXT, 'x': {'type': 'number'}, 'y': {'type': 'number'}},
                {'target': 'page', 'selector': '', 'x': 0, 'y': 0}, []),
    _definition('wait_page', '等待页面', '等待当前页面地址和加载状态，不重新导航。',
                {'url': _TEXT, 'waitUntil': _enum('domcontentloaded', 'load', 'networkidle')}, {'url': '', 'waitUntil': 'domcontentloaded'}, ['url']),
    _definition('switch_page', '切换标签页', '切换到运行中已绑定的页面别名。', {'pageAlias': _TEXT}, {'pageAlias': ''}, ['pageAlias']),
    _definition('close_page', '关闭标签页', '关闭明确别名的页面。', {'pageAlias': _TEXT}, {'pageAlias': ''}, ['pageAlias']),
])


def node_catalog() -> list[dict[str, Any]]:
    return deepcopy(_DEFINITIONS)
