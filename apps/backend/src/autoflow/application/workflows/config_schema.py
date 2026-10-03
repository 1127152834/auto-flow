"""Executor configuration schema derived from what each executor actually reads (remediation M2 R2-11).

The key set of a node type is every string key its executor code reads from the node configuration:
``config.get("key")``, ``config["key"]``, ``"key" in config`` and helper calls ``helper(config, "key")``.
Module-level helpers in the executor's own file count for every executor of that file, so the set is a
superset per file. A key in this schema only proves the code reads it; whether an option really
changes behaviour is still proven by that node's execution tests.
"""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap
from collections.abc import Iterable, Mapping
from functools import cache
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.outputs import declared_outputs

from .config_schema_debt import EDITOR_DEFAULT_KEYS, PANEL_ONLY_KEYS
from .executors.base import ModuleExecutor

# Node fields that the editor and runtime own for every node type (identity, display, shared
# runtime options). The legacy retry/timeout keys are reported separately as migration candidates.
COMMON_NODE_KEYS = frozenset({
    "label", "moduleType", "name", "remark", "customName", "isHighlighted", "disabled", "config",
    "timeout", "errorPolicy", "subflowName", "subflowGroupId", "isSubflow", "parameterValues",
    "retryCount", "retryDelay", "retryBackoff", "retryExhaustedAction", "timeoutAction", "onTimeout",
})
# "candidate" is a model-candidate view of the node config (executors/ai.py).
CANVAS_ONLY_TYPES = frozenset({"group", "note"})
_CONFIG_NAMES = frozenset({"config", "cfg", "data", "node_config", "settings", "options", "params", "candidate"})


def _is_config(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id in _CONFIG_NAMES


def _key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.isidentifier():
        return node.value
    return None


def read_keys(tree: ast.AST) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(tree):
        found: Iterable[ast.AST] = ()
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in {"get", "pop", "setdefault"} and _is_config(func.value):
                found = node.args[:1]
            elif any(_is_config(arg) for arg in node.args):
                found = node.args
        elif isinstance(node, ast.Subscript) and _is_config(node.value):
            found = (node.slice,)
        elif isinstance(node, ast.Compare) and any(_is_config(item) for item in node.comparators):
            found = (node.left,)
        elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            # Key lists read in a loop, e.g. ``for key in ("startX", "startY"): config.get(key)``
            # or ``for key, value in (("stdoutVariable", out), ...)``.
            heads = [item.elts[0] if isinstance(item, ast.Tuple) and item.elts else item for item in node.elts]
            found = heads if heads and all(_key(item) for item in heads) else ()
        elif isinstance(node, ast.IfExp):
            # ``field = "imagePath" if image else "textContent"`` followed by ``config.get(field)``.
            found = (node.body, node.orelse)
        keys.update(key for item in found if (key := _key(item)) is not None)
    return keys


@cache
def _file_helper_keys(path: str) -> frozenset[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    helpers = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return frozenset(key for helper in helpers for key in read_keys(helper))


def _called_keys(tree: ast.AST, namespace: Mapping[str, Any], seen: set[Any]) -> set[str]:
    """Keys read by helpers the code calls with the config, followed across autoflow modules.

    Covers ``helper(config)``, ``module.helper(config)`` and ``OtherClass.helper(config)``.
    """
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not any(_is_config(arg) for arg in node.args):
            continue
        target: Any = None
        if isinstance(node.func, ast.Name):
            target = namespace.get(node.func.id)
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            target = getattr(namespace.get(node.func.value.id), node.func.attr, None)
        if (
            inspect.isfunction(target) and target.__module__.startswith("autoflow.")
            and target not in seen
        ):
            seen.add(target)
            helper = ast.parse(textwrap.dedent(inspect.getsource(target)))
            keys |= read_keys(helper) | _called_keys(helper, target.__globals__, seen)
    return keys


def executor_keys(executor_class: type[ModuleExecutor]) -> frozenset[str]:
    keys: set[str] = set()
    seen: set[Any] = set()
    for owner in executor_class.__mro__:
        if owner in (ModuleExecutor, object) or not owner.__module__.startswith("autoflow."):
            continue
        tree = ast.parse(textwrap.dedent(inspect.getsource(owner)))
        keys |= read_keys(tree) | _called_keys(tree, vars(sys.modules[owner.__module__]), seen)
        source = inspect.getsourcefile(owner)
        if source:
            keys |= _file_helper_keys(source)
    return frozenset(keys)


@cache
def production_config_schema() -> Mapping[str, frozenset[str]]:
    from .executors.production import PRODUCTION_EXECUTORS

    schema: dict[str, frozenset[str]] = {}
    for executor_class in PRODUCTION_EXECUTORS:
        module_type = executor_class().module_type
        schema[module_type] = schema.get(module_type, frozenset()) | executor_keys(executor_class)
    return schema


def unknown_config_keys(data: Mapping[str, Any], module_type: str, schema: Mapping[str, frozenset[str]] | None = None) -> list[str]:
    """Saved keys that are neither read by the node's executor nor a known field of its panel.

    Typical sources: a document from another version, a changed node type or a hand-edited file.
    Empty for node types without a derived schema and for canvas-only nodes.
    """
    if schema is None:
        from .config_schema_snapshot import READ_KEYS

        schema = READ_KEYS
    known = schema.get(module_type)
    if known is None or module_type in CANVAS_ONLY_TYPES:
        return []
    nested = data.get("config")
    config = {**data, **nested} if isinstance(nested, Mapping) else dict(data)
    panel_only = PANEL_ONLY_KEYS.get(module_type, frozenset()) | EDITOR_DEFAULT_KEYS.get(module_type, frozenset())
    return sorted(key for key in config if key not in known and key not in COMMON_NODE_KEYS and key not in panel_only)


def describe_unknown_keys(label: str, keys: list[str]) -> str:
    return f"「{label}」有 {len(keys)} 项设置不会被运行读取（{'、'.join(keys)}），可能来自其他版本或其他节点类型"


def export_schema() -> dict[str, dict[str, Any]]:
    return {
        module_type: {
            "reads": sorted(keys),
            "panelOnly": sorted(PANEL_ONLY_KEYS.get(module_type, ())),
            "editorDefaults": sorted(EDITOR_DEFAULT_KEYS.get(module_type, ())),
            # Remediation M2 R2-29: the minimal output contract of this node type.
            "outputs": declared_outputs(module_type, keys),
        }
        for module_type, keys in sorted(production_config_schema().items())
    }
