"""Minimal node output contract (remediation M2 R2-29).

A node output is identified by ``(nodeId, outputKey)``: the output key is the configuration field that
names the variable the node writes (``variableName``, ``resultVariable``…). References written as
``{node.<nodeId>.<outputKey>}`` therefore survive renaming the node or its variable. Old ``{variable}``
references keep working until M6.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Configuration fields that name a written variable, with their display names.
OUTPUT_FIELDS: dict[str, str] = {
    "variableName": "结果", "resultVariable": "结果", "outputVariable": "结果", "targetVariable": "结果",
    "dataVariable": "数据", "saveResult": "结果", "saveToVariable": "结果",
    "itemVariable": "当前元素", "indexVariable": "当前序号", "loopIndexVariable": "当前序号",
    "keyVariable": "当前键", "valueVariable": "当前值",
    "variableNameX": "横坐标", "variableNameY": "纵坐标",
    "imageVariable": "图片", "textVariable": "文本", "urlVariable": "网址", "fileVariable": "文件",
    "responseVariable": "响应", "headersVariable": "响应头", "cookiesVariable": "Cookie", "bodyVariable": "响应内容",
    "statusVariable": "状态码", "errorVariable": "错误", "countVariable": "数量", "exitCodeVariable": "退出码",
    "stdoutVariable": "标准输出", "stderrVariable": "错误输出", "returnCodeVariable": "返回码",
    "saveNewElementSelector": "新元素选择器", "saveChangeInfo": "变化信息",
}
# Loop variables exist only inside the loop body; after the loop they may never have been set.
LOOP_SCOPED_FIELDS = frozenset({"itemVariable", "indexVariable", "loopIndexVariable", "keyVariable", "valueVariable"})
LOOP_TYPES = frozenset({"loop", "foreach", "foreach_dict", "infinite_loop"})
# Values these nodes read are secrets by declaration (cookies, page storage).
SENSITIVE_TYPES = frozenset({"web_cookie", "web_storage"})
NODE_OUTPUTS = "\x00nodeOutputs"
REFERENCE = re.compile(r"\$?\{\s*node\.(?P<node>[^.{}\s]+)\.(?P<key>[^.{}\s]+)\s*\}")


def declared_outputs(module_type: str, reads: frozenset[str]) -> list[dict[str, Any]]:
    """Outputs of a node type: the variable-name fields its executor really reads."""
    return [
        {
            "key": key,
            "name": name,
            "sensitive": module_type in SENSITIVE_TYPES,
            "availability": "loopBody" if module_type in LOOP_TYPES and key in LOOP_SCOPED_FIELDS else "afterSuccess",
        }
        for key, name in OUTPUT_FIELDS.items()
        if key in reads
    ]


def node_output_names(nodes: list[Any]) -> dict[str, dict[str, str]]:
    """``nodeId → outputKey → variable name`` for outputs whose variable name is set explicitly."""
    names: dict[str, dict[str, str]] = {}
    for node in nodes:
        if not isinstance(node, Mapping) or not isinstance(node.get("id"), str):
            continue
        data = node.get("data")
        if not isinstance(data, Mapping):
            continue
        nested = data.get("config")
        config: Mapping[str, Any] = nested if isinstance(nested, Mapping) else data
        fields = {key: value.strip() for key, value in config.items() if key in OUTPUT_FIELDS and isinstance(value, str) and value.strip()}
        if fields:
            names[node["id"]] = fields
    return names


def reference_issues(nodes: list[Any]) -> list[tuple[str, str]]:
    """(nodeId, message) for ``{node.X.k}`` references to a missing node or an unnamed output."""
    known = {node.get("id") for node in nodes if isinstance(node, Mapping)}
    names = node_output_names(nodes)
    problems: list[tuple[str, str]] = []

    def strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, Mapping):
            return [text for key, item in value.items() if key not in {"label", "note", "remark"} for text in strings(item)]
        if isinstance(value, list):
            return [text for item in value for text in strings(item)]
        return []

    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        for text in strings(node.get("data", {})):
            for match in REFERENCE.finditer(text):
                target, key = match.group("node"), match.group("key")
                if target not in known:
                    problems.append((str(node.get("id")), f"引用的节点已删除：{match.group(0)}"))
                elif key not in names.get(target, {}):
                    problems.append((str(node.get("id")), f"引用的节点输出没有设置变量名：{match.group(0)}"))
    return problems
