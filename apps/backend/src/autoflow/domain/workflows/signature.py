"""Workflow signature: the inputs a workflow needs, independent of any automation (remediation M2 R2-18..21).

A workflow declares ``content.signature = {inputs: [{key, name, fields: [...]}], outputs: [...]}``.
Keys are stable identities (English recommended for new ones, old Chinese keys stay valid); names are
display text and can change. Nodes reference ``{input.<inputKey>.<fieldKey>}``, the whole group
``{input.<inputKey>}`` or the primary processing input ``{$record.<fieldKey>}``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

# Same kinds as project table fields; "any" accepts every field type.
FIELD_TYPES = frozenset({"string", "number", "boolean", "date", "any"})
KEY = re.compile(r"^[A-Za-z_一-龥][A-Za-z0-9_一-龥]{0,63}$")
# ``{input.group.field}`` / ``{input.group}`` / ``{$record.field}``, also inside ``${...}``.
REFERENCE = re.compile(
    r"\$?\{\s*(?:input\.(?P<group>[^.{}\s]+)(?:\.(?P<field>[^.{}\s]+))?|\$record\.(?P<record>[^.{}\s]+))\s*\}"
)


@dataclass(frozen=True, slots=True)
class SignatureField:
    key: str
    name: str
    type: str
    required: bool
    sensitive: bool
    sample: str | int | float | bool | None = None


@dataclass(frozen=True, slots=True)
class SignatureInput:
    key: str
    name: str
    fields: tuple[SignatureField, ...]

    def field(self, key: str) -> SignatureField | None:
        return next((item for item in self.fields if item.key == key), None)


@dataclass(frozen=True, slots=True)
class Signature:
    inputs: tuple[SignatureInput, ...]

    def input(self, key: str) -> SignatureInput | None:
        return next((item for item in self.inputs if item.key == key), None)


@dataclass(frozen=True, slots=True)
class SignatureIssue:
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class Reference:
    """One new-style reference; ``group`` is None for ``$record``."""

    text: str
    group: str | None
    field: str | None


def _sample_problem(kind: str, sample: Any) -> str | None:
    number = isinstance(sample, (int, float)) and not isinstance(sample, bool)
    if kind == "string" and not isinstance(sample, str):
        return "样例值需要是文本"
    if kind == "number" and not number:
        return "样例值需要是数字"
    if kind == "boolean" and not isinstance(sample, bool):
        return "样例值需要是“是”或“否”"
    if kind == "date":
        try:
            date.fromisoformat(sample) if isinstance(sample, str) else None
        except ValueError:
            return "样例值需要是 年-月-日 格式的日期"
        if not isinstance(sample, str):
            return "样例值需要是 年-月-日 格式的日期"
    if kind == "any" and not (isinstance(sample, (str, bool)) or number):
        return "样例值需要是文本、数字或“是/否”"
    return None


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_signature(raw: Any) -> tuple[Signature | None, list[SignatureIssue]]:
    """Return the signature (None when absent) and every problem found, never raising."""
    if raw is None:
        return None, []
    issues: list[SignatureIssue] = []
    if not isinstance(raw, Mapping) or not isinstance(raw.get("inputs", []), list):
        return None, [SignatureIssue("signature", "流程输入格式不正确")]
    inputs: list[SignatureInput] = []
    for index, item in enumerate(raw.get("inputs", [])):
        path = f"signature.inputs.{index}"
        if not isinstance(item, Mapping):
            issues.append(SignatureIssue(path, "流程输入格式不正确"))
            continue
        key, name = _text(item.get("key")), _text(item.get("name"))
        if key is None or not KEY.match(key):
            issues.append(SignatureIssue(f"{path}.key", "标识只能包含字母、数字、下划线或中文，且不能以数字开头"))
        elif any(existing.key == key for existing in inputs):
            issues.append(SignatureIssue(f"{path}.key", f"流程输入标识「{key}」重复"))
        fields: list[SignatureField] = []
        raw_fields = item.get("fields")
        for field_index, field in enumerate(raw_fields if isinstance(raw_fields, list) else []):
            field_path = f"{path}.fields.{field_index}"
            field_key = _text(field.get("key")) if isinstance(field, Mapping) else None
            if not isinstance(field, Mapping) or field_key is None or not KEY.match(field_key):
                issues.append(SignatureIssue(f"{field_path}.key", "字段标识只能包含字母、数字、下划线或中文，且不能以数字开头"))
                continue
            if any(existing.key == field_key for existing in fields):
                issues.append(SignatureIssue(f"{field_path}.key", f"字段标识「{field_key}」重复"))
                continue
            kind = field.get("type", "string")
            if kind not in FIELD_TYPES:
                issues.append(SignatureIssue(f"{field_path}.type", "字段类型不受支持"))
                continue
            sensitive, sample = field.get("sensitive") is True, field.get("sample")
            if sample is not None:
                problem = "敏感字段不能保存样例值" if sensitive else _sample_problem(str(kind), sample)
                if problem is not None:
                    issues.append(SignatureIssue(f"{field_path}.sample", problem))
                    sample = None
            fields.append(SignatureField(
                field_key, _text(field.get("name")) or field_key, str(kind),
                field.get("required") is True, sensitive, sample,
            ))
        if key is not None and KEY.match(key):
            inputs.append(SignatureInput(key, name or key, tuple(fields)))
    return Signature(tuple(inputs)), issues


def document_signature(document: Mapping[str, Any]) -> Any:
    content = document.get("content", document)
    return content.get("signature") if isinstance(content, Mapping) else None


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            if key not in {"label", "note", "remark"}:
                yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def node_references(data: Any) -> list[Reference]:
    return [
        Reference(match.group(0), match.group("group"), match.group("field") or match.group("record"))
        for text in _strings(data)
        for match in REFERENCE.finditer(text)
    ]


def reference_issues(document: Mapping[str, Any], signature: Signature) -> list[tuple[str, str]]:
    """(nodeId, message) for every new-style reference the signature does not declare."""
    content = document.get("content", document)
    problems: list[tuple[str, str]] = []
    for node in content.get("nodes", []) if isinstance(content, Mapping) else []:
        if not isinstance(node, Mapping):
            continue
        for reference in node_references(node.get("data", {})):
            if reference.group is None:
                continue  # $record is checked against the bound primary input at start
            group = signature.input(reference.group)
            if group is None:
                problems.append((str(node.get("id")), f"引用了不存在的流程输入「{reference.group}」"))
            elif reference.field is not None and group.field(reference.field) is None:
                problems.append((str(node.get("id")), f"流程输入「{group.name}」没有字段「{reference.field}」"))
    return problems


def sensitive_references(signature: Signature, record_group: str | None) -> set[str]:
    """Dotted names whose values are sensitive, e.g. ``input.account.password`` and ``$record.password``."""
    names: set[str] = set()
    for group in signature.inputs:
        for field in group.fields:
            if field.sensitive:
                names.add(f"input.{group.key}.{field.key}")
                if group.key == record_group:
                    names.add(f"$record.{field.key}")
    return names


def keep_signature(previous: Any, incoming: dict[str, Any]) -> dict[str, Any]:
    """A Studio save that does not mention ``signature`` keeps the stored one; ``null`` removes it.

    Older Studio windows and imported files know nothing about signatures and must not erase them.
    """
    if "signature" in incoming:
        return {key: value for key, value in incoming.items() if key != "signature" or value is not None}
    stored = document_signature(previous) if isinstance(previous, Mapping) else None
    return {**incoming, "signature": stored} if stored is not None else incoming
