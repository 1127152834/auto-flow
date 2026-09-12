from __future__ import annotations

import base64
import math
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.domain.project_data import (
    RecordKey,
    decode_record_key,
    encode_record_key,
    record_key,
    system_record_key,
    validate_field,
    validate_value,
)
from autoflow.domain.projects.models import ProjectError


def assert_invalid(call: object, *args: object) -> ProjectError:
    with pytest.raises(ProjectError) as caught:
        call(*args)  # type: ignore[operator]
    assert caught.value.status == 422
    assert caught.value.code in {"INVALID_PROJECT_DATA", "PATTERN_VALIDATION_TIMEOUT"}
    assert caught.value.details["reason"]
    return caught.value


def test_record_keys_preserve_type_text_and_unicode() -> None:
    zero_padded = record_key("001")
    text_one = record_key("1")
    integer_one = record_key(1)

    assert zero_padded == RecordKey(type="text", value="001")
    assert len({zero_padded, text_one, integer_one}) == 3
    assert decode_record_key(encode_record_key(record_key("a/b%中文")), "text") == record_key(
        "a/b%中文"
    )


@pytest.mark.parametrize(
    "value",
    ["", True, 1.0, date(2026, 9, 13), 2**53, -(2**53)],
)
def test_record_key_rejects_values_outside_the_wire_scalar_contract(value: object) -> None:
    assert_invalid(record_key, value)


def test_record_key_rejects_surrogates_and_overlong_text() -> None:
    assert_invalid(record_key, "bad\ud800")
    assert_invalid(record_key, "x" * 8001)


def test_decode_record_key_rejects_an_integer_too_large_to_parse_safely() -> None:
    oversized = base64.urlsafe_b64encode(("9" * 5000).encode()).decode().rstrip("=")
    assert_invalid(decode_record_key, oversized, "integer")


def test_system_record_keys_are_canonical_uuid4_values() -> None:
    first = system_record_key()
    second = system_record_key()

    assert first.type == "uuid"
    assert first != second
    assert decode_record_key(encode_record_key(first), "uuid") == first
    assert first.value == first.value.lower()


@pytest.mark.parametrize(
    ("encoded", "key_type"),
    [
        ("MDE", "integer"),  # 01
        ("LTE", "integer"),  # -1 is canonical, but this is deliberately checked below
        ("LTA", "integer"),  # -0
        ("KzE", "integer"),  # +1
        ("YQ==", "text"),  # padding is not canonical
        ("YQ%3D%3D", "text"),  # URL percent-encoding must not be decoded again
        ("_w", "text"),  # decoded byte is not UTF-8
        ("QTlFNDhGMzAtNUQyQi00RjZELUI1Q0ItN0E2QjgyNTE2RTVG", "uuid"),
    ],
)
def test_decode_record_key_rejects_noncanonical_or_wrongly_encoded_paths(
    encoded: str, key_type: str
) -> None:
    if encoded == "LTE":
        assert decode_record_key(encoded, key_type) == RecordKey("integer", "-1")
    else:
        assert_invalid(decode_record_key, encoded, key_type)


def test_validate_field_returns_a_trimmed_canonical_definition() -> None:
    definition = validate_field(
        {
            "key": "  客户.email  ",
            "name": "  客户邮箱  ",
            "type": "string",
            "required": True,
            "validation": {
                "minLength": 3,
                "maxLength": 120,
                "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            },
        }
    )

    assert definition == {
        "key": "客户.email",
        "name": "客户邮箱",
        "type": "string",
        "required": True,
        "validation": {
            "minLength": 3,
            "maxLength": 120,
            "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        },
    }


@pytest.mark.parametrize(
    "definition",
    [
        {},
        {"key": "x", "name": "X", "type": "string", "required": False},
        {"key": "x", "name": "X", "type": "string", "required": False, "validation": {}, "extra": 1},
        {"key": "bad\x00key", "name": "X", "type": "string", "required": False, "validation": {}},
        {"key": "x", "name": "X", "type": "integer", "required": False, "validation": {}},
        {"key": "x", "name": "X", "type": "string", "required": 1, "validation": {}},
        {"key": "x", "name": "X", "type": "string", "required": False, "validation": {"minimum": 1}},
        {"key": "x", "name": "X", "type": "number", "required": False, "validation": {"minLength": 1}},
        {"key": "x", "name": "X", "type": "string", "required": False, "validation": {"minLength": True}},
        {"key": "x", "name": "X", "type": "string", "required": False, "validation": {"minLength": 2, "maxLength": 1}},
        {"key": "x", "name": "X", "type": "number", "required": False, "validation": {"minimum": 2, "maximum": 1}},
        {"key": "x", "name": "X", "type": "number", "required": False, "validation": {"minimum": math.nan}},
    ],
)
def test_validate_field_rejects_invalid_shapes_and_rule_combinations(definition: dict[str, object]) -> None:
    assert_invalid(validate_field, definition)


@pytest.mark.parametrize(
    "pattern",
    [
        "(a+)+$",
        "(a|aa)+$",
        r"^(a)\1$",
        "(?=a)a",
        "^[a-z]+[a-z]+$",
        "^.*.*Z$",
        "a" * 257,
    ],
)
def test_validate_field_rejects_unsafe_or_unsupported_regex(pattern: str) -> None:
    assert_invalid(
        validate_field,
        {"key": "x", "name": "X", "type": "string", "required": False, "validation": {"pattern": pattern}},
    )


def test_validate_field_rejects_excessive_bounded_repeat() -> None:
    assert_invalid(
        validate_field,
        {"key": "x", "name": "X", "type": "string", "required": False, "validation": {"pattern": "^[A-Z]{10001}$"}},
    )


def test_validate_field_limits_total_bounded_pattern_expansion() -> None:
    assert_invalid(
        validate_field,
        {"key": "x", "name": "X", "type": "string", "required": False, "validation": {"pattern": "^a{6000}ba{6000}$"}},
    )


def test_pattern_evaluation_times_out_instead_of_blocking() -> None:
    pattern = "^" + ("[a]+a" * 20) + "Z$"
    definition = validate_field(
        {"key": "x", "name": "X", "type": "string", "required": False, "validation": {"pattern": pattern}}
    )

    error = assert_invalid(validate_value, definition, "a" * 1000 + "!")
    assert error.code == "PATTERN_VALIDATION_TIMEOUT"


def test_string_rules_use_unicode_code_points_and_full_pattern_match() -> None:
    definition = validate_field(
        {
            "key": "code",
            "name": "Code",
            "type": "string",
            "required": True,
            "validation": {"minLength": 2, "maxLength": 2, "pattern": "^[A-Z]+$"},
        }
    )
    assert validate_value(definition, "AB") == "AB"
    assert_invalid(validate_value, definition, "A")
    assert_invalid(validate_value, definition, "ABx")


def test_optional_null_is_allowed_but_required_null_and_empty_text_are_rejected() -> None:
    optional = validate_field({"key": "x", "name": "X", "type": "string", "required": False, "validation": {}})
    required = validate_field({**optional, "required": True})

    assert validate_value(optional, None) is None
    assert validate_value(optional, "") == ""
    assert_invalid(validate_value, required, None)
    assert_invalid(validate_value, required, "")


def test_number_rules_reject_coercion_nonfinite_and_unsafe_integers() -> None:
    definition = validate_field(
        {"key": "score", "name": "Score", "type": "number", "required": True, "validation": {"minimum": 1.5, "maximum": 3}}
    )
    assert validate_value(definition, 2) == 2
    assert validate_value(definition, 2.5) == 2.5
    for invalid in (True, "2", math.nan, math.inf, 2**53, 10**1000):
        assert_invalid(validate_value, definition, invalid)


def test_field_number_rules_reject_huge_integers_as_project_errors() -> None:
    assert_invalid(
        validate_field,
        {"key": "x", "name": "X", "type": "number", "required": False, "validation": {"minimum": 10**1000}},
    )


@pytest.mark.parametrize(
    "value",
    [
        {"kind": "date", "precision": "date", "value": "2026-02-29", "offset": None},
        {"kind": "date", "precision": "date", "value": "2026-01-01T00:00:00", "offset": None},
        {"kind": "date", "precision": "datetime", "value": "2026-09-13T10:30:00+08:00", "offset": "+08:00"},
        {"kind": "date", "precision": "datetime", "value": "2026-09-13T10:30:00Z", "offset": "Z"},
        {"kind": "date", "precision": "datetime", "value": "2026-09-13T10:30:00", "offset": "+24:00"},
        {"kind": "date", "precision": "datetime", "value": "2026-09-13T10:30:00", "offset": "+00:99"},
        {"kind": "date", "precision": "datetime", "value": "2026-09-13T10:30:00", "offset": "-01:60"},
        {"kind": "date", "precision": "datetime", "value": "2026-09-13 10:30:00", "offset": None},
        {"kind": "date", "precision": "datetime", "value": "2026-09-13T25:00:00", "offset": None},
        {"kind": "date", "precision": "datetime", "value": "2026-09-13T10:30:00Z", "offset": "+00:00", "extra": True},
        {"kind": "date", "precision": ["datetime"], "value": "2026-09-13T10:30:00", "offset": None},
    ],
)
def test_date_values_reject_invalid_calendar_shape_and_offset_mismatches(value: dict[str, object]) -> None:
    definition = validate_field({"key": "when", "name": "When", "type": "date", "required": True, "validation": {}})
    assert_invalid(validate_value, definition, value)


def test_date_values_preserve_precision_and_original_offset() -> None:
    definition = validate_field({"key": "when", "name": "When", "type": "date", "required": True, "validation": {}})
    day = {"kind": "date", "precision": "date", "value": "2024-02-29", "offset": None}
    instant = {"kind": "date", "precision": "datetime", "value": "2026-09-13T10:30:00.1234567", "offset": "+08:00"}
    utc = {"kind": "date", "precision": "datetime", "value": "2026-09-13T02:30:00", "offset": "Z"}
    latest_offset = {"kind": "date", "precision": "datetime", "value": "2026-09-13T10:30:00", "offset": "+23:59"}

    assert validate_value(definition, day) == day
    assert validate_value(definition, instant) == instant
    assert validate_value(definition, utc) == utc
    assert validate_value(definition, latest_offset) == latest_offset


@pytest.mark.parametrize(
    ("field_type", "value"),
    [("string", 1), ("boolean", 1), ("boolean", "true"), ("date", "2026-09-13")],
)
def test_values_are_not_implicitly_converted(field_type: str, value: object) -> None:
    definition = validate_field({"key": "x", "name": "X", "type": field_type, "required": False, "validation": {}})
    assert_invalid(validate_value, definition, value)


def test_string_value_rejects_surrogates_as_a_project_error() -> None:
    definition = validate_field({"key": "x", "name": "X", "type": "string", "required": False, "validation": {}})
    assert_invalid(validate_value, definition, "bad\ud800")


def test_project_data_error_codes_project_through_the_real_http_handler() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/invalid")
    def invalid() -> None:
        record_key(2**53)

    response = TestClient(app, raise_server_exceptions=False).get("/invalid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PROJECT_DATA"
    assert response.json()["error"]["details"]["domainCode"] == "invalid_project_data"
