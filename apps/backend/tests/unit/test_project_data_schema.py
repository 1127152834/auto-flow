from copy import deepcopy

import pytest
from pydantic import ValidationError

from autoflow.adapters.http.project_data_schema_schemas import (
    DataSchemaCandidate,
    DataSchemaCommit,
    DataSchemaImpact,
    DataSchemaResult,
)
from autoflow.domain.project_data.schema import (
    SchemaBackfillLimit,
    backfill_budget,
    canonical_bytes,
    validate_candidate,
)
from autoflow.domain.projects.models import ProjectError

GEN = "11111111-1111-4111-8111-111111111111"
FIELD = "22222222-2222-4222-8222-222222222222"
CLIENT = "33333333-3333-4333-8333-333333333333"


def definition(**changes):
    return {
        "key": "name",
        "name": "Name",
        "type": "string",
        "required": False,
        "validation": {},
        **changes,
    }


def current(**changes):
    return {
        **definition(),
        "ref": {"fieldId": FIELD, "datasetGeneration": GEN},
        "fieldRevision": 2,
        "writable": True,
        "formula": False,
        **changes,
    }


def candidate(*fields):
    return {
        "datasetGeneration": GEN,
        "expectedTableRevision": 3,
        "fields": list(fields),
    }


def existing(**changes):
    return {
        "kind": "existing",
        "fieldId": FIELD,
        "expectedFieldRevision": 2,
        "definition": definition(),
        **changes,
    }


def new(**changes):
    return {
        "kind": "new",
        "clientId": CLIENT,
        "definition": definition(key="other"),
        "sourceColumnPolicy": "localOnly",
        **changes,
    }


def test_normalization_preserves_input_and_default_presence():
    source = candidate(existing(definition=definition(name="  改名  ")), new())
    original = deepcopy(source)
    result = validate_candidate(source, [current()])
    assert source == original
    assert result["fields"][0]["definition"]["name"] == "改名"
    assert "existingRecordDefault" not in result["fields"][1]
    explicit = validate_candidate(candidate(new(existingRecordDefault=None)), [])
    assert explicit["fields"][0]["existingRecordDefault"] is None
    assert validate_candidate(candidate(), []) == candidate()


@pytest.mark.parametrize(
    "fields", [[], [existing(), existing()], [existing(fieldId=CLIENT)]]
)
def test_existing_set_must_match_exactly(fields):
    with pytest.raises(ProjectError):
        validate_candidate(candidate(*fields), [current()])


@pytest.mark.parametrize("value", [True, 0, -1, 1.0, "1", 9007199254740992])
def test_revision_is_strict_safe_positive_integer(value):
    with pytest.raises(ProjectError):
        validate_candidate({**candidate(), "expectedTableRevision": value}, [])
    with pytest.raises(ProjectError):
        validate_candidate(
            candidate(existing(expectedFieldRevision=value)), [current()]
        )


@pytest.mark.parametrize(
    "change",
    [
        {"clientId": "invalid"},
        {"clientId": CLIENT.upper().replace("3", "A", 1)},
        {"sourceColumnPolicy": "mapped"},
        {"unknown": False},
    ],
)
def test_new_shape_is_strict(change):
    with pytest.raises(ProjectError):
        validate_candidate(candidate(new(**change)), [])


def test_duplicate_client_and_keys_and_unknown_shape_rejected():
    for source in [
        candidate(new(), new()),
        candidate(existing(), new(definition=definition())),
        {**candidate(), "extra": 1},
        {"datasetGeneration": GEN, "expectedTableRevision": 1},
        candidate({**existing(), "existingRecordDefault": None}),
    ]:
        with pytest.raises(ProjectError):
            validate_candidate(
                source,
                [current()]
                if source.get("fields")
                and source["fields"][0].get("kind") == "existing"
                else [],
            )


def test_protected_fields_and_revision():
    with pytest.raises(ProjectError):
        validate_candidate(
            candidate(existing(definition=definition(key="renamed"))), [current()]
        )
    for flags in [{"formula": True}, {"writable": False}]:
        assert validate_candidate(candidate(existing()), [current(**flags)])
        with pytest.raises(ProjectError):
            validate_candidate(
                candidate(existing(definition=definition(name="new"))),
                [current(**flags)],
            )
    with pytest.raises(ProjectError):
        validate_candidate(
            candidate(existing(definition=definition(type="number"))),
            [current()],
            FIELD,
        )
    assert validate_candidate(
        candidate(existing(definition=definition(name="new", required=True))),
        [current()],
        FIELD,
    )
    with pytest.raises(ProjectError) as caught:
        validate_candidate(candidate(existing(expectedFieldRevision=1)), [current()])
    assert caught.value.code == "REVISION_CONFLICT"


@pytest.mark.parametrize(
    ("kind", "value"),
    [("boolean", False), ("number", 0), ("string", ""), ("string", None)],
)
def test_scalar_defaults_do_not_coerce(kind, value):
    result = validate_candidate(
        candidate(new(definition=definition(type=kind), existingRecordDefault=value)),
        [],
    )
    actual = result["fields"][0]["existingRecordDefault"]
    assert actual == value and type(actual) is type(value)


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("number", False),
        ("number", "0"),
        ("number", float("nan")),
        ("number", float("inf")),
        ("string", "\ud800"),
        ("boolean", 0),
    ],
)
def test_invalid_defaults_are_rejected(kind, value):
    with pytest.raises(ProjectError):
        validate_candidate(
            candidate(
                new(definition=definition(type=kind), existingRecordDefault=value)
            ),
            [],
        )


def test_required_missing_allowed_for_empty_table_but_explicit_null_invalid():
    assert validate_candidate(candidate(new(definition=definition(required=True))), [])
    with pytest.raises(ProjectError):
        validate_candidate(
            candidate(
                new(definition=definition(required=True), existingRecordDefault=None)
            ),
            [],
        )


def test_date_default_survives_http_to_domain_without_string_conversion():
    date = {"kind": "date", "precision": "date", "value": "0001-01-01", "offset": None}
    dto = DataSchemaCandidate.model_validate(
        candidate(new(definition=definition(type="date"), existingRecordDefault=date))
    )
    normalized = validate_candidate(
        dto.model_dump(by_alias=True, exclude_unset=True), []
    )
    assert normalized["fields"][0]["existingRecordDefault"] == date
    for invalid in [
        {**date, "value": "2026-02-30"},
        {**date, "offset": "Z"},
        "2026-01-01",
    ]:
        with pytest.raises(ProjectError):
            validate_candidate(
                candidate(
                    new(
                        definition=definition(type="date"),
                        existingRecordDefault=invalid,
                    )
                ),
                [],
            )


@pytest.mark.parametrize(
    "source",
    [
        None,
        [],
        {**candidate(), "fields": {}},
        candidate(None),
        candidate({"kind": []}),
        candidate(new(definition=[])),
        {**candidate(), "datasetGeneration": True},
        candidate(existing(fieldId="bad")),
    ],
)
def test_malformed_structures_raise_domain_errors(source):
    with pytest.raises(ProjectError):
        validate_candidate(source)


def test_service_structural_validation_does_not_require_snapshot():
    assert validate_candidate(candidate(existing())) == candidate(existing())
    with pytest.raises(ProjectError):
        validate_candidate(candidate(existing()), [])


def test_canonical_bytes_are_utf8_sorted_and_strict():
    assert canonical_bytes({"z": False, "a": "中"}) == '{"a":"中","z":false}'.encode()
    for value in [float("nan"), float("inf"), "\ud800", {"x": "\udfff"}]:
        with pytest.raises((ValueError, UnicodeError)):
            canonical_bytes(value)


def test_backfill_limits_use_whole_rows_and_utf8():
    assert backfill_budget([{}] * 1000) == (1000, 2000)
    with pytest.raises(SchemaBackfillLimit):
        backfill_budget([{}] * 1001)
    limit = 4 * 1024 * 1024
    assert backfill_budget([{"x": "a" * (limit - 8)}]) == (1, limit)
    with pytest.raises(SchemaBackfillLimit):
        backfill_budget([{"x": "a" * (limit - 7)}])
    row = {"old": "中文", "a": False, "b": 0, "c": None}
    assert backfill_budget([row]) == (1, len(canonical_bytes(row)))
    assert len(canonical_bytes({"x": "中"})) - len(canonical_bytes({"x": "a"})) == 2


def test_http_shapes_preserve_null_vs_omission_and_require_candidate_fields():
    dto = DataSchemaCandidate.model_validate(candidate(new()))
    assert (
        "existingRecordDefault"
        not in dto.model_dump(by_alias=True, exclude_unset=True)["fields"][0]
    )
    dto = DataSchemaCandidate.model_validate(candidate(new(existingRecordDefault=None)))
    assert (
        dto.model_dump(by_alias=True, exclude_unset=True)["fields"][0][
            "existingRecordDefault"
        ]
        is None
    )
    with pytest.raises(ValidationError):
        DataSchemaCandidate.model_validate(
            {"datasetGeneration": GEN, "expectedTableRevision": 1}
        )
    with pytest.raises(ValidationError):
        DataSchemaCommit.model_validate(
            {"candidate": candidate(), "impactRevision": True}
        )
    assert DataSchemaImpact.model_json_schema()["properties"]["referenceAvailability"]
    assert DataSchemaResult.model_json_schema()["properties"]["createdFieldIds"]
