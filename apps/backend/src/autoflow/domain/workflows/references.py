"""The shared, non-expression variable grammar used by drafts and runs."""

import re
import unicodedata
from copy import deepcopy
from typing import Any

REFERENCE_PATTERN = re.compile(r"\$\{([^{}]*)\}|(?<![${])\{([^{}]*)\}(?!})")

TEXT_FIELDS = ('url', 'selector', 'framePath', 'text', 'savePath', 'values')


def text_leaves(value: Any, path: str = 'config') -> dict[str, str]:
    if isinstance(value, str):
        return {path: value}
    if isinstance(value, list):
        return {p: v for i, item in enumerate(value) for p, v in text_leaves(item, f'{path}.{i}').items()}
    if isinstance(value, dict):
        return {p: v for key, item in value.items() for p, v in text_leaves(item, f'{path}.{key}').items()}
    return {}


def literal_eligible(node: dict[str, Any]) -> set[str]:
    config = node['config']
    if node['type'] in {'condition', 'loop'}:
        return {path for i, rule in enumerate(config.get('rules', [])) if isinstance(rule, dict) and rule.get('kind') == 'page'
                for field in ('selector', 'framePath') for path in text_leaves(rule.get(field), f'config.rules.{i}.{field}')}
    return {path for field in TEXT_FIELDS for path in text_leaves(config.get(field), f'config.{field}')}


def reference_config(node: dict[str, Any]) -> dict[str, Any]:
    """A non-mutating view for reference scanning; literal leaves contain no tokens."""
    config = deepcopy(node['config'])
    for path in node.get('literalPaths', []):
        parts = path.split('.')[1:]
        parent = config
        try:
            for part in parts[:-1]:
                parent = parent[int(part)] if isinstance(parent, list) else parent[part]
            key = int(parts[-1]) if isinstance(parent, list) else parts[-1]
            parent[key] = ''
        except (KeyError, IndexError, ValueError, TypeError):
            continue  # Structural validation reports invalid paths before execution.
    return config


def substitute_text(value: Any, lookup: Any, literals: set[str], path: str) -> Any:
    if isinstance(value, list):
        return [substitute_text(v, lookup, literals, f'{path}.{i}') for i, v in enumerate(value)]
    if not isinstance(value, str) or path in literals:
        return value
    return REFERENCE_PATTERN.sub(lambda m: lookup(m.group(1) if m.group(1) is not None else m.group(2))
                                 if is_variable_name(m.group(1) if m.group(1) is not None else m.group(2)) else m.group(0), value)


def is_variable_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and (value[0] == "_" or unicodedata.category(value[0]).startswith("L"))
        and all(
            character == "_" or unicodedata.category(character)[0] in {"L", "N"}
            for character in value
        )
    )
