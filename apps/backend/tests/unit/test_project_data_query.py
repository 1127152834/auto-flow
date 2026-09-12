import base64
import json

import pytest

from autoflow.domain.project_data.query import (
    decode_query,
    matches,
    validate_filter,
    validate_order,
)
from autoflow.domain.projects.models import ProjectError


def encoded(value):
    return (
        base64.urlsafe_b64encode(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        )
        .decode()
        .rstrip("=")
    )


def test_strict_decode_rejects_padding_duplicates_constants_and_surrogates():
    assert (
        decode_query(encoded({"type": "all", "items": []}), "filter")["type"] == "all"
    )
    bad = [
        encoded({}) + "=",
        base64.urlsafe_b64encode(b'{"x":1,"x":2}').decode().rstrip("="),
        base64.urlsafe_b64encode(b'{"x":NaN}').decode().rstrip("="),
        base64.urlsafe_b64encode(b'"\\ud800"').decode().rstrip("="),
    ]
    for value in bad:
        with pytest.raises(ProjectError):
            decode_query(value, "filter")


def test_filter_tree_types_null_and_empty_groups():
    fields = {"s": "string", "n": "number", "b": "boolean", "d": "date"}
    expression = validate_filter(
        {
            "type": "all",
            "items": [{"type": "compare", "fieldId": "s", "operator": "isNull"}],
        },
        fields,
        set(),
    )
    assert matches(expression, {}, None) and matches(expression, {"s": None}, None)
    assert not matches(expression, {"s": " "}, None)
    assert matches(
        validate_filter({"type": "all", "items": []}, fields, set()), {}, None
    )
    assert not matches(
        validate_filter({"type": "any", "items": []}, fields, set()), {}, None
    )
    with pytest.raises(ProjectError):
        validate_filter(
            {"type": "compare", "fieldId": "b", "operator": "gt", "value": True},
            fields,
            set(),
        )


def test_null_and_incompatible_values_do_not_match_neq():
    node = validate_filter(
        {"type": "compare", "fieldId": "n", "operator": "neq", "value": 2},
        {"n": "number"},
        set(),
    )
    assert (
        not matches(node, {}, None)
        and not matches(node, {"n": None}, None)
        and not matches(node, {"n": "2"}, None)
    )


def test_date_precision_and_awareness_are_not_coerced():
    wanted = {
        "kind": "date",
        "precision": "datetime",
        "value": "2026-01-01T08:00:00",
        "offset": "+08:00",
    }
    node = validate_filter(
        {"type": "compare", "fieldId": "d", "operator": "eq", "value": wanted},
        {"d": "date"},
        set(),
    )
    same_instant = {**wanted, "value": "2026-01-01T00:00:00", "offset": "Z"}
    naive = {**wanted, "offset": None}
    day = {"kind": "date", "precision": "date", "value": "2026-01-01", "offset": None}
    assert matches(node, {"d": same_instant}, None)
    assert not matches(node, {"d": naive}, None) and not matches(node, {"d": day}, None)


def test_order_is_closed_unique_and_bounded():
    assert validate_order([{"fieldId": "x", "direction": "desc"}], {"x": "string"})
    for value in [
        [{"fieldId": "x", "direction": "asc"}] * 2,
        [{"systemField": "bad", "direction": "asc"}],
        [{"systemField": "recordKey", "direction": "asc"}] * 9,
    ]:
        with pytest.raises(ProjectError):
            validate_order(value, {"x": "string"})


@pytest.mark.parametrize(
    "expression",
    [
        {"type": []},
        {"type": "compare", "fieldId": "n", "operator": {}, "value": 1},
    ],
)
def test_unhashable_union_tags_are_validation_errors(expression):
    with pytest.raises(ProjectError) as error:
        validate_filter(expression, {"n": "number"}, set())
    assert error.value.status == 422


def test_unhashable_order_members_are_validation_errors():
    with pytest.raises(ProjectError):
        validate_order([{"fieldId": [], "direction": []}], {"n": "number"})


def test_deep_json_and_huge_integer_are_validation_errors():
    deep = '{"type":"not","item":' * 1100 + '{"type":"all","items":[]}' + "}" * 1100
    value = base64.urlsafe_b64encode(deep.encode()).decode().rstrip("=")
    with pytest.raises(ProjectError):
        decode_query(value, "filter")
    with pytest.raises(ProjectError):
        validate_filter(
            {"type": "compare", "fieldId": "n", "operator": "eq", "value": 10**400},
            {"n": "number"},
            set(),
        )


@pytest.mark.parametrize(
    "value",
    [
        {"kind": "date", "precision": "date", "value": "20260913", "offset": None},
        {
            "kind": "date",
            "precision": "datetime",
            "value": "2026-09-13",
            "offset": None,
        },
        {
            "kind": "date",
            "precision": "datetime",
            "value": "2026-09-13T00:00:00",
            "offset": "",
        },
        {
            "kind": "date",
            "precision": "datetime",
            "value": "2026-09-13T00:00:00",
            "offset": "+00:99",
        },
    ],
)
def test_query_date_uses_authoritative_scalar_format(value):
    with pytest.raises(ProjectError):
        validate_filter(
            {"type": "compare", "fieldId": "d", "operator": "eq", "value": value},
            {"d": "date"},
            set(),
        )


def test_datetime_fraction_comparison_keeps_all_digits():
    first = {
        "kind": "date",
        "precision": "datetime",
        "value": "2026-09-13T00:00:00.1234561",
        "offset": None,
    }
    second = {**first, "value": "2026-09-13T00:00:00.1234569"}
    node = validate_filter(
        {"type": "compare", "fieldId": "d", "operator": "lt", "value": second},
        {"d": "date"},
        set(),
    )
    assert matches(node, {"d": first}, None)


def test_safe_integral_float_and_wide_empty_groups():
    with pytest.raises(ProjectError):
        validate_filter(
            {
                "type": "compare",
                "fieldId": "n",
                "operator": "eq",
                "value": 9007199254740992.0,
            },
            {"n": "number"},
            set(),
        )
    validate_filter(
        {"type": "all", "items": [{"type": "all", "items": []} for _ in range(50)]},
        {},
        set(),
    )


def test_long_fraction_comparison_is_exact():
    first = {
        "kind": "date",
        "precision": "datetime",
        "value": "2026-09-13T00:00:00.1234567890123456781",
        "offset": "+08:00",
    }
    second = {**first, "value": "2026-09-13T00:00:00.1234567890123456789"}
    assert matches(
        validate_filter(
            {"type": "compare", "fieldId": "d", "operator": "lt", "value": second},
            {"d": "date"},
            set(),
        ),
        {"d": first},
        None,
    )
    assert not matches(
        validate_filter(
            {"type": "compare", "fieldId": "d", "operator": "eq", "value": second},
            {"d": "date"},
            set(),
        ),
        {"d": first},
        None,
    )
