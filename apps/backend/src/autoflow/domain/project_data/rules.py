from __future__ import annotations

import math
import unicodedata
from datetime import date, datetime
from typing import Any, TypeAlias, cast

import regex

from autoflow.domain.project_data.identity import MAX_SAFE_INTEGER
from autoflow.domain.projects.models import ProjectError

FieldWrite: TypeAlias = dict[str, Any]

_FIELD_KEYS = {"key", "name", "type", "required", "validation"}
_FIELD_TYPES = {"string", "number", "boolean", "date"}
_STRING_RULES = {"minLength", "maxLength", "pattern"}
_NUMBER_RULES = {"minimum", "maximum"}
_DATE_PATTERN = regex.compile(r"^\d{4}-\d{2}-\d{2}$", regex.ASCII)
_DATETIME_PATTERN = regex.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$",
    regex.ASCII,
)
_OFFSET_PATTERN = regex.compile(
    r"^(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$", regex.ASCII
)
_PATTERN_TIMEOUT_SECONDS = 0.05
_MAX_PATTERN_REPEAT = 10_000


def _invalid(field: str, reason: str, rule: str | None = None) -> ProjectError:
    details = {"field": field, "reason": reason}
    if rule is not None:
        details["rule"] = rule
    return ProjectError("INVALID_PROJECT_DATA", "Invalid project data", 422, details)


def _trimmed_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise _invalid(field, "must be text")
    trimmed = value.strip()
    if not 1 <= len(trimmed) <= 120:
        raise _invalid(field, "must contain 1 to 120 Unicode code points")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in trimmed):
        raise _invalid(field, "must contain valid Unicode scalar values")
    return trimmed


def validate_field(definition: dict[str, Any]) -> FieldWrite:
    if not isinstance(definition, dict) or set(definition) != _FIELD_KEYS:
        raise _invalid("definition", "must contain exactly key, name, type, required, and validation")
    key = _trimmed_text(definition["key"], "key")
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in key):
        raise _invalid("key", "must not contain control characters")
    name = _trimmed_text(definition["name"], "name")
    field_type = definition["type"]
    if not isinstance(field_type, str) or field_type not in _FIELD_TYPES:
        raise _invalid("type", "must be string, number, boolean, or date")
    required = definition["required"]
    if not isinstance(required, bool):
        raise _invalid("required", "must be boolean")
    validation = definition["validation"]
    if not isinstance(validation, dict):
        raise _invalid("validation", "must be an object")

    allowed_rules = _STRING_RULES if field_type == "string" else _NUMBER_RULES if field_type == "number" else set()
    unknown_rules = set(validation) - allowed_rules
    if unknown_rules:
        raise _invalid("validation", f"rules are not supported for {field_type}: {sorted(unknown_rules)}")
    canonical_validation = _validate_rules(field_type, validation)
    return {
        "key": key,
        "name": name,
        "type": field_type,
        "required": required,
        "validation": canonical_validation,
    }


def _validate_rules(field_type: str, validation: dict[str, Any]) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    if field_type == "string":
        for rule in ("minLength", "maxLength"):
            if rule in validation:
                value = validation[rule]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise _invalid("validation", "must be a nonnegative integer", rule)
                canonical[rule] = value
        if canonical.get("minLength", 0) > canonical.get("maxLength", math.inf):
            raise _invalid("validation", "minLength must not exceed maxLength")
        if "pattern" in validation:
            pattern = validation["pattern"]
            if not isinstance(pattern, str):
                raise _invalid("validation", "must be text", "pattern")
            _compile_safe_pattern(pattern)
            canonical["pattern"] = pattern
    elif field_type == "number":
        for rule in ("minimum", "maximum"):
            if rule in validation:
                value = validation[rule]
                if not _is_finite_wire_number(value):
                    raise _invalid("validation", "must be a finite number", rule)
                canonical[rule] = value
        if canonical.get("minimum", -math.inf) > canonical.get("maximum", math.inf):
            raise _invalid("validation", "minimum must not exceed maximum")
    return canonical


def _compile_safe_pattern(pattern: str) -> regex.Pattern[str]:
    """Compile the supported linear-ish regex subset.

    The subset permits literals, anchors, character classes, escapes and simple
    quantifiers. Grouping, alternation, lookaround, backreferences and adjacent
    quantifiers are rejected, preventing nested quantified expressions.
    """
    if len(pattern) > 256:
        raise _invalid("validation", "must contain at most 256 Unicode code points", "pattern")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in pattern):
        raise _invalid("validation", "must contain valid Unicode scalar values", "pattern")
    atoms: list[bool] = []
    total_bounded_expansion = 0
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character in "()|":
            raise _invalid("validation", "grouping and alternation are not supported", "pattern")
        if character == "\\":
            index += 1
            if index >= len(pattern):
                raise _invalid("validation", "pattern is malformed", "pattern")
            if pattern[index].isdigit():
                raise _invalid("validation", "backreferences are not supported", "pattern")
            atoms.append(False)
        elif character == "[":
            index += 1
            escaped_in_class = False
            while index < len(pattern):
                if pattern[index] == "]" and not escaped_in_class:
                    break
                escaped_in_class = pattern[index] == "\\" and not escaped_in_class
                if pattern[index] != "\\":
                    escaped_in_class = False
                index += 1
            if index >= len(pattern):
                raise _invalid("validation", "pattern is malformed", "pattern")
            atoms.append(False)
        elif character in "^$":
            index += 1
            continue
        elif character in "*+?{":
            if not atoms or atoms[-1]:
                raise _invalid("validation", "nested or misplaced quantifiers are not supported", "pattern")
            if character == "{":
                closing = pattern.find("}", index + 1)
                if closing < 0:
                    raise _invalid("validation", "pattern is malformed", "pattern")
                repeat = pattern[index + 1 : closing]
                parts = repeat.split(",")
                if (
                    len(parts) not in {1, 2}
                    or not parts[0].isascii()
                    or not parts[0].isdigit()
                    or (len(parts) == 2 and parts[1] and (not parts[1].isascii() or not parts[1].isdigit()))
                ):
                    raise _invalid("validation", "bounded repeat is malformed", "pattern")
                bounds = [int(bound) for bound in parts if bound]
                if any(bound > _MAX_PATTERN_REPEAT for bound in bounds):
                    raise _invalid("validation", "bounded repeat must not exceed 10000", "pattern")
                total_bounded_expansion += bounds[-1]
                if total_bounded_expansion > _MAX_PATTERN_REPEAT:
                    raise _invalid("validation", "total bounded expansion must not exceed 10000", "pattern")
                index = closing
            atoms[-1] = True
            if len(atoms) >= 2 and atoms[-2]:
                raise _invalid("validation", "adjacent quantified expressions are not supported", "pattern")
        elif character == "}":
            raise _invalid("validation", "pattern is malformed", "pattern")
        else:
            atoms.append(False)
        index += 1
    try:
        return regex.compile(pattern, cache_pattern=False)
    except (regex.error, OverflowError) as error:
        raise _invalid("validation", "pattern is malformed", "pattern") from error


def _is_finite_wire_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, int):
        return abs(value) <= MAX_SAFE_INTEGER
    return math.isfinite(value) and (not value.is_integer() or abs(value) <= MAX_SAFE_INTEGER)


def validate_value(definition: dict[str, Any], value: object) -> object:
    canonical = validate_field(definition)
    if value is None:
        if canonical["required"]:
            raise _invalid(canonical["key"], "required values must not be null", "required")
        return None
    field_type = canonical["type"]
    if field_type == "string":
        return _validate_string(canonical, value)
    if field_type == "number":
        return _validate_number(canonical, value)
    if field_type == "boolean":
        if not isinstance(value, bool):
            raise _invalid(canonical["key"], "must be boolean", "type")
        return value
    return _validate_date(canonical, value)


def _validate_string(definition: FieldWrite, value: object) -> str:
    if not isinstance(value, str):
        raise _invalid(definition["key"], "must be text", "type")
    if definition["required"] and value == "":
        raise _invalid(definition["key"], "required text must not be empty", "required")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise _invalid(definition["key"], "must contain valid Unicode scalar values", "type")
    validation = definition["validation"]
    if len(value) < validation.get("minLength", 0):
        raise _invalid(definition["key"], "is shorter than minLength", "minLength")
    if len(value) > validation.get("maxLength", math.inf):
        raise _invalid(definition["key"], "is longer than maxLength", "maxLength")
    pattern = validation.get("pattern")
    if pattern is not None:
        try:
            matched = _compile_safe_pattern(pattern).search(
                value, timeout=_PATTERN_TIMEOUT_SECONDS
            )
        except TimeoutError as error:
            raise ProjectError(
                "PATTERN_VALIDATION_TIMEOUT",
                "Pattern validation timed out",
                422,
                {
                    "field": definition["key"],
                    "rule": "pattern",
                    "reason": "pattern evaluation exceeded its time limit",
                },
            ) from error
        if matched is None:
            raise _invalid(definition["key"], "does not match pattern", "pattern")
    return value


def _validate_number(definition: FieldWrite, value: object) -> int | float:
    if not _is_finite_wire_number(value):
        raise _invalid(definition["key"], "must be a finite JSON-safe number", "type")
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    validation = definition["validation"]
    if value < validation.get("minimum", -math.inf):
        raise _invalid(definition["key"], "is less than minimum", "minimum")
    if value > validation.get("maximum", math.inf):
        raise _invalid(definition["key"], "is greater than maximum", "maximum")
    return value


def _validate_date(definition: FieldWrite, value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"kind", "precision", "value", "offset"}:
        raise _invalid(definition["key"], "must be a DateScalar object", "type")
    precision = value["precision"]
    if value["kind"] != "date" or not isinstance(precision, str) or precision not in {"date", "datetime"}:
        raise _invalid(definition["key"], "has an invalid date kind or precision", "type")
    raw_value = value["value"]
    offset = value["offset"]
    if not isinstance(raw_value, str) or (offset is not None and not isinstance(offset, str)):
        raise _invalid(definition["key"], "has an invalid date value or offset", "type")
    if any(
        0xD800 <= ord(character) <= 0xDFFF
        for text in (raw_value, offset)
        if isinstance(text, str)
        for character in text
    ):
        raise _invalid(definition["key"], "must contain valid Unicode scalar values", "type")
    try:
        if precision == "date":
            if _DATE_PATTERN.fullmatch(raw_value) is None or offset is not None:
                raise ValueError
            date.fromisoformat(raw_value)
        else:
            if _DATETIME_PATTERN.fullmatch(raw_value) is None:
                raise ValueError
            datetime.fromisoformat(raw_value)
            if offset is not None:
                if _OFFSET_PATTERN.fullmatch(offset) is None:
                    raise ValueError
                datetime.fromisoformat(raw_value + ("+00:00" if offset == "Z" else offset))
    except ValueError as error:
        raise _invalid(definition["key"], "has an invalid calendar value or mismatched offset", "type") from error
    return cast(dict[str, object], value.copy())


def validation_issues(fields: list[dict[str, Any]], values: dict[str, object]) -> list[dict[str, str]]:
    """Derive safe, structured business-format issues from a record snapshot."""
    issues: list[dict[str, str]] = []
    for field in fields:
        field_id = str(field["fieldId"])
        definition = {
            key: field[key]
            for key in ("key", "name", "type", "required", "validation")
        }
        if field_id not in values:
            if field["required"]:
                issues.append({"fieldId": field_id, "code": "REQUIRED_FIELD_MISSING", "rule": "required", "message": "Required field is missing"})
            continue
        try:
            validate_value(definition, values[field_id])
        except ProjectError as error:
            issues.append({"fieldId": field_id, "code": error.code, "rule": str(error.details.get("rule", "type")), "message": error.details.get("reason", error.message)})
    return issues
