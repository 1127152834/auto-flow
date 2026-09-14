from __future__ import annotations

import base64
import json
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from autoflow.domain.project_data.rules import validate_value
from autoflow.domain.projects.models import ProjectError

MAX_ENCODED = 64 * 1024
MISSING = object()


def invalid(message: str) -> ProjectError:
    return ProjectError("INVALID_PROJECT_DATA_QUERY", message, 422)


def decode_query(value: str, name: str) -> Any:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("ascii", "ignore")) != len(value)
        or len(value) > MAX_ENCODED
        or "=" in value
    ):
        raise invalid(f"Invalid {name}")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if base64.urlsafe_b64encode(raw).decode().rstrip("=") != value:
            raise ValueError
        text = raw.decode("utf-8")
        if len(raw) > MAX_ENCODED or any(0xD800 <= ord(c) <= 0xDFFF for c in text):
            raise ValueError

        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in items:
                if key in result:
                    raise ValueError
                result[key] = item
            return result

        result = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )

        def valid_strings(item: Any) -> bool:
            if isinstance(item, str):
                return not any(0xD800 <= ord(c) <= 0xDFFF for c in item)
            if isinstance(item, list):
                return all(valid_strings(child) for child in item)
            if isinstance(item, dict):
                return all(
                    valid_strings(key) and valid_strings(child)
                    for key, child in item.items()
                )
            return True

        if not valid_strings(result):
            raise ValueError
        return result
    except (ValueError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise invalid(f"Invalid {name}") from error


def validate_filter(
    node: Any, fields: dict[str, str], statuses: set[str]
) -> dict[str, Any]:
    counts = {"leaves": 0}

    def walk(item: Any, depth: int) -> dict[str, Any]:
        if not isinstance(item, dict) or depth > 5 or "type" not in item:
            raise invalid("Invalid filter expression")
        kind = item["type"]
        if not isinstance(kind, str):
            raise invalid("Invalid filter type")
        if kind in {"all", "any"}:
            if (
                set(item) != {"type", "items"}
                or not isinstance(item["items"], list)
                or len(item["items"]) > 50
            ):
                raise invalid("Invalid filter group")
            result: dict[str, Any] = {
                "type": kind,
                "items": [walk(child, depth + 1) for child in item["items"]],
            }
        elif kind == "not":
            if set(item) != {"type", "item"}:
                raise invalid("Invalid not filter")
            result = {"type": kind, "item": walk(item["item"], depth + 1)}
        elif kind == "compare":
            allowed = {"type", "fieldId", "operator", "value"}
            if (
                set(item) - allowed
                or not isinstance(item.get("fieldId"), str)
                or item["fieldId"] not in fields
            ):
                raise invalid("Filter field was not found")
            operator = item.get("operator")
            if not isinstance(operator, str):
                raise invalid("Invalid field comparison")
            nullop = operator in {"isNull", "isNotNull"}
            valid = {
                "string": {"eq", "neq", "contains", "startsWith"},
                "number": {"eq", "neq", "gt", "gte", "lt", "lte"},
                "boolean": {"eq", "neq"},
                "date": {"eq", "neq", "gt", "gte", "lt", "lte"},
            }[fields[item["fieldId"]]] | {"isNull", "isNotNull"}
            if (
                operator not in valid
                or (nullop and "value" in item)
                or (not nullop and ("value" not in item or item["value"] is None))
                or (
                    not nullop
                    and not compatible(fields[item["fieldId"]], item["value"])
                )
            ):
                raise invalid("Invalid field comparison")
            counts["leaves"] += 1
            result = item.copy()
        elif kind == "status":
            if set(item) - {"type", "operator", "statusId"}:
                raise invalid("Invalid status filter")
            operator = item.get("operator")
            if not isinstance(operator, str):
                raise invalid("Invalid status filter")
            nullop = operator in {"isNull", "isNotNull"}
            if (
                operator not in {"eq", "neq", "isNull", "isNotNull"}
                or (nullop and "statusId" in item)
                or (
                    not nullop
                    and (
                        not isinstance(item.get("statusId"), str)
                        or item["statusId"] not in statuses
                    )
                )
            ):
                raise invalid("Invalid status filter")
            counts["leaves"] += 1
            result = item.copy()
        else:
            raise invalid("Unknown filter type")
        if counts["leaves"] > 100:
            raise invalid("Filter is too complex")
        return result

    return walk(node, 1)


def validate_order(value: Any, fields: dict[str, str]) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > 8:
        raise invalid("Invalid orderBy")
    seen = set()
    result = []
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) not in ({"fieldId", "direction"}, {"systemField", "direction"})
            or not isinstance(item.get("direction"), str)
            or item["direction"] not in {"asc", "desc"}
        ):
            raise invalid("Invalid orderBy")
        target = (
            ("field", item["fieldId"])
            if "fieldId" in item
            else ("system", item["systemField"])
        )
        if not isinstance(target[1], str):
            raise invalid("Invalid orderBy target")
        if (
            target in seen
            or (target[0] == "field" and target[1] not in fields)
            or (
                target[0] == "system"
                and target[1] not in {"status", "createdAt", "updatedAt", "recordKey"}
            )
        ):
            raise invalid("Invalid orderBy target")
        seen.add(target)
        result.append(item.copy())
    return result


def compatible(kind: str, value: Any) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return type(value) is bool
    if kind == "number":
        if type(value) is int:
            return abs(value) <= 9007199254740991
        return (
            type(value) is float
            and math.isfinite(value)
            and (not value.is_integer() or abs(value) <= 9007199254740991)
        )
    return date_value(value) is not None


def date_value(value: Any) -> tuple[int, Any] | None:
    try:
        canonical = validate_value(
            {
                "key": "value",
                "name": "Value",
                "type": "date",
                "required": False,
                "validation": {},
            },
            value,
        )
    except ProjectError:
        return None
    if not isinstance(canonical, dict):
        return None
    try:
        raw = canonical["value"]
        offset = canonical["offset"]
        assert isinstance(raw, str)
        if canonical["precision"] == "date":
            return 0, date.fromisoformat(raw).toordinal()
        local = datetime.fromisoformat(raw[:19])
        fraction = Decimal("0." + raw.split(".", 1)[1]) if "." in raw else Decimal(0)
        seconds = (
            local.toordinal() * 86400
            + local.hour * 3600
            + local.minute * 60
            + local.second
        )
        if offset is None:
            return 1, (seconds, fraction)
        assert isinstance(offset, str)
        if offset != "Z":
            sign = 1 if offset[0] == "+" else -1
            seconds -= sign * (int(offset[1:3]) * 3600 + int(offset[4:6]) * 60)
        return 2, (seconds, fraction)
    except (ValueError, TypeError, OverflowError):
        return None


def compare_values(kind: str, left: Any, right: Any) -> int | None:
    if (
        left is MISSING
        or left is None
        or right is MISSING
        or right is None
        or not compatible(kind, left)
        or not compatible(kind, right)
    ):
        return None
    if kind == "date":
        a, b = date_value(left), date_value(right)
        if a is None or b is None or a[0] != b[0]:
            return None
        left, right = a[1], b[1]
    return (left > right) - (left < right)


def matches(node: dict[str, Any], values: dict[str, Any], status: str | None) -> bool:
    kind = node["type"]
    if kind == "all":
        return all(matches(x, values, status) for x in node["items"])
    if kind == "any":
        return any(matches(x, values, status) for x in node["items"])
    if kind == "not":
        return not matches(node["item"], values, status)
    if kind == "status":
        current, op = status, node["operator"]
        if op == "isNull":
            return current is None
        if op == "isNotNull":
            return current is not None
        return current is not None and (
            (current == node["statusId"])
            if op == "eq"
            else (current != node["statusId"])
        )
    current, op = values.get(node["fieldId"], MISSING), node["operator"]
    if op == "isNull":
        return current is MISSING or current is None
    if op == "isNotNull":
        return current is not MISSING and current is not None
    comparison = compare_values(
        "string"
        if isinstance(node["value"], str)
        else "boolean"
        if type(node["value"]) is bool
        else "number"
        if type(node["value"]) in (int, float)
        else "date",
        current,
        node["value"],
    )
    if comparison is None:
        return False
    if op == "eq":
        return comparison == 0
    if op == "neq":
        return comparison != 0
    if op == "contains":
        return node["value"] in current
    if op == "startsWith":
        return current.startswith(node["value"])
    return {
        "gt": comparison > 0,
        "gte": comparison >= 0,
        "lt": comparison < 0,
        "lte": comparison <= 0,
    }[op]
