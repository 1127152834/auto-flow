from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Protocol


class CredentialReader(Protocol):
    def get_field(self, name: str, field: str) -> Any | None: ...


_CREDENTIAL_REFERENCE = re.compile(
    r"\{\{\s*(?:cred|凭据)\s*[:：]\s*([^{}]+?)\s*\}\}"
)
_VARIABLE_NAME = r"(?:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|[a-zA-Z_\u4e00-\u9fa5][a-zA-Z0-9_\u4e00-\u9fa5]*)"
_VARIABLE_REFERENCE = re.compile(
    r"(?:\$\{?|(?<!\$)\{)"
    rf"({_VARIABLE_NAME})"
)


def references_sensitive_value(value: Any, sensitive_names: set[str]) -> bool:
    if isinstance(value, Mapping):
        return any(
            references_sensitive_value(key, sensitive_names)
            or references_sensitive_value(item, sensitive_names)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(references_sensitive_value(item, sensitive_names) for item in value)
    if not isinstance(value, str):
        return False
    if _CREDENTIAL_REFERENCE.search(value):
        return True
    return any(match.group(1) in sensitive_names for match in _VARIABLE_REFERENCE.finditer(value))


def _json_safe(value: Any, depth: int = 0) -> Any:
    if depth > 20:
        return str(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, datetime):
        if value.time() == time():
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(_json_safe(k, depth + 1)): _json_safe(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item, depth + 1) for item in value]
    return str(value)


def _replacement_text(value: Any) -> str:
    if value is None:
        return ""
    safe = _json_safe(value)
    if isinstance(safe, (list, dict)):
        return json.dumps(safe, ensure_ascii=False)
    return safe if isinstance(safe, str) else str(safe)


def resolve_value(
    value: Any,
    variables: Mapping[str, Any],
    credentials: CredentialReader | None = None,
    *, preserve_types: bool = False,
) -> Any:
    if isinstance(value, dict):
        return {key: resolve_value(item, variables, credentials, preserve_types=preserve_types) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_value(item, variables, credentials, preserve_types=preserve_types) for item in value]
    if isinstance(value, tuple):
        return tuple(resolve_value(item, variables, credentials, preserve_types=preserve_types) for item in value)
    if not isinstance(value, str):
        return value

    if credentials is not None and "{{" in value:
        def replace_credential(match: re.Match[str]) -> str:
            reference = match.group(1).strip()
            if "." in reference:
                name, field_name = (part.strip() for part in reference.split(".", 1))
            else:
                name, field_name = reference, "value"
            try:
                resolved = credentials.get_field(name, field_name)
            # Frozen WebRPA keeps credential placeholders on any provider failure.
            except Exception:  # noqa: BLE001
                return match.group(0)
            return resolved if isinstance(resolved, str) else (
                match.group(0) if resolved is None else _replacement_text(resolved)
            )

        value = _CREDENTIAL_REFERENCE.sub(replace_credential, value)

    missing = object()

    def resolve_access_path(expression: str) -> Any:
        expression = resolve_nested(expression.strip(), max_depth=3)
        match = re.match(
            rf"^({_VARIABLE_NAME})((?:\[[^\]]+\])*)",
            expression,
        )
        if not match:
            return missing
        base_name, access_path = match.group(1), match.group(2)
        if base_name not in variables:
            return missing
        result = variables[base_name]
        if not access_path:
            return result
        for accessor in re.findall(r"\[([^\]]+)\]", access_path):
            accessor = accessor.strip()
            if (
                len(accessor) >= 2
                and accessor[0] == accessor[-1]
                and accessor[0] in {'"', "'"}
            ):
                accessor = accessor[1:-1]
            try:
                if isinstance(result, list):
                    index = int(accessor)
                    if not -len(result) <= index < len(result):
                        return missing
                    result = result[index]
                elif isinstance(result, Mapping):
                    if accessor in result:
                        result = result[accessor]
                    else:
                        numeric_key = int(accessor)
                        if numeric_key not in result:
                            return missing
                        result = result[numeric_key]
                else:
                    return missing
            except (ValueError, IndexError, KeyError, TypeError):
                return missing
        return result

    def resolve_nested(text: str, max_depth: int = 5) -> str:
        if max_depth <= 0:
            return text
        pattern = re.compile(r"(?<!\$)\{([^{}]+)\}")
        matches = list(pattern.finditer(text))
        if not matches:
            return text
        for match in reversed(matches):
            resolved = resolve_access_path(match.group(1).strip())
            if resolved is not missing:
                text = text[: match.start()] + _replacement_text(resolved) + text[match.end() :]
        if pattern.search(text):
            return resolve_nested(text, max_depth - 1)
        return text

    if preserve_types:
        reference = re.fullmatch(r"\$?\{([^{}]+)\}", value)
        if reference:
            resolved = resolve_access_path(reference.group(1))
            if resolved is not missing:
                return resolved
    result = value
    for match in reversed(list(re.finditer(r"\$\{([^}]+)\}", result))):
        resolved = resolve_access_path(match.group(1).strip())
        if resolved is not missing:
            result = result[: match.start()] + _replacement_text(resolved) + result[match.end() :]
    return resolve_nested(result)


@dataclass(slots=True)
class VariableManager:
    _global_vars: dict[str, Any] = field(default_factory=dict)
    _local_vars: dict[str, Any] = field(default_factory=dict)
    _scope_stack: list[dict[str, Any]] = field(default_factory=list)

    def set(self, name: str, value: Any, scope: str = "global") -> None:
        target = self._global_vars if scope == "global" else self._local_vars
        target[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        return self._local_vars.get(name, self._global_vars.get(name, default))

    def delete(self, name: str) -> None:
        self._local_vars.pop(name, None)
        self._global_vars.pop(name, None)

    def exists(self, name: str) -> bool:
        return name in self._local_vars or name in self._global_vars

    def get_all(self) -> dict[str, Any]:
        return {**self._global_vars, **self._local_vars}

    def get_global_vars(self) -> dict[str, Any]:
        return self._global_vars.copy()

    def get_local_vars(self) -> dict[str, Any]:
        return self._local_vars.copy()

    def clear_local(self) -> None:
        self._local_vars.clear()

    def clear_all(self) -> None:
        self._global_vars.clear()
        self._local_vars.clear()

    def push_scope(self) -> None:
        self._scope_stack.append(self._local_vars.copy())
        self._local_vars = {}

    def pop_scope(self) -> None:
        if self._scope_stack:
            self._local_vars = self._scope_stack.pop()

    def resolve(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._resolve_string(value)
        if isinstance(value, dict):
            return {key: self.resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.resolve(item) for item in value]
        return value

    def _resolve_string(self, text: str) -> str:
        def replacer(match: re.Match[str]) -> str:
            resolved = self.get(match.group(1).strip())
            return match.group(0) if resolved is None else str(resolved)

        result = re.sub(r"\$\{([^}]+)\}", replacer, text)
        return re.sub(r"(?<!\$)\{([^}]+)\}", replacer, result)

    def evaluate_expression(self, expression: str) -> Any:
        resolved = self._resolve_string(expression)
        try:
            if all(character in set("0123456789+-*/.() ") for character in resolved):
                return eval(resolved, {"__builtins__": {}}, {})
        except (ArithmeticError, SyntaxError):
            return resolved
        return resolved
