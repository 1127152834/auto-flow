"""Sheets binding, identity and A1 rules with no database and no network.

These are the pure decisions the sync path depends on: what makes two records
the same, which columns a binding may address, and how a remote cell is fitted
to the local field type. They are checked here so a regression is localised
instead of showing up as a mysteriously failing pull.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from autoflow.application.project_sync import bindings, outbound
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.projects.models import ProjectError
from autoflow.providers.data.google_sheets import (
    cell,
    column_letter,
    column_range,
    quoted,
)


def field(
    field_id: str,
    *,
    type: str = "string",
    writable: bool = True,
    formula: bool = False,
) -> Any:
    """The parts of a ``DataFieldRow`` the mapping rules read."""
    return SimpleNamespace(id=field_id, type=type, writable=writable, formula=formula)


def code(error: ProjectError) -> str:
    return error.code


def test_identity_token_keeps_text_and_integer_keys_apart():
    assert bindings._identity_token("001") == "text:001"
    assert bindings._identity_token("1") == "text:1"
    assert bindings._identity_token(1) == "integer:1"
    # A sheet types 1.0 as a number; it is the same key as 1, not as "1".
    assert bindings._identity_token(1.0) == "integer:1"
    assert bindings._identity_token("1") != bindings._identity_token(1)
    assert outbound._identity_token("001") != outbound._identity_token(1)


def test_record_key_keeps_the_remote_cell_type():
    assert outbound._record_key_for("001") == RecordKey("text", "001")
    assert outbound._record_key_for("1") == RecordKey("text", "1")
    assert outbound._record_key_for(1) == RecordKey("integer", "1")
    assert outbound._record_key_for(1.0) == RecordKey("integer", "1")
    assert outbound._marker(RecordKey("integer", "1")) == "integer:1"
    assert outbound._marker(RecordKey("text", "1")) == "text:1"


def test_record_key_type_only_accepts_known_types():
    assert outbound._key_type("integer") == "integer"
    assert outbound._key_type("uuid") == "uuid"
    assert outbound._key_type("text") == "text"
    assert outbound._key_type(None) == "text"
    assert outbound._key_type("number") == "text"


def test_column_letters_round_trip_and_reject_non_a1():
    assert [column_letter(index) for index in (0, 25, 26, 701, 702)] == [
        "A",
        "Z",
        "AA",
        "ZZ",
        "AAA",
    ]
    assert bindings._column_index("A") == 0
    assert bindings._column_index("a") == 0
    assert bindings._column_index("AA") == 26
    assert bindings._column_index("AAA") == 702
    for bad in ("1", "A1", "AAAA", "", "A-"):
        with pytest.raises(ProjectError) as failure:
            bindings._column_index(bad)
        assert code(failure.value) == "INVALID_PROJECT_DATA"


def test_a1_helpers_quote_titles_and_columns():
    assert quoted("O'Brien") == "'O''Brien'"
    assert cell("数据", 2, 5) == "'数据'!$C$5"
    assert column_range("数据", 0) == "'数据'!$A$2:$A"
    assert column_range("数据", 27, first_row=1) == "'数据'!$AB$1:$AB"


def test_spreadsheet_and_sheet_identifiers_are_checked():
    assert bindings._spreadsheet_id("1Abc_-yz") == "1Abc_-yz"
    for bad in ("", "a/b", "x" * 257, None, 7):
        with pytest.raises(ProjectError) as failure:
            bindings._spreadsheet_id(bad)
        assert code(failure.value) == "INVALID_PROJECT_DATA"

    assert bindings._sheet_id(0) == 0
    assert bindings._sheet_id(2**53 - 1) == 2**53 - 1
    for bad in (-1, 2**53, True, "1", 1.0, None):
        with pytest.raises(ProjectError) as failure:
            bindings._sheet_id(bad)
        assert code(failure.value) == "INVALID_PROJECT_DATA"


def test_system_identity_is_refused_instead_of_guessed():
    with pytest.raises(ProjectError) as failure:
        bindings._identity({"kind": "system"})
    assert code(failure.value) == "SYNC_NOT_IMPLEMENTED"
    assert failure.value.details["capability"] == "sheets.systemIdentity"

    with pytest.raises(ProjectError) as missing:
        bindings._identity({"kind": "column"})
    assert code(missing.value) == "INVALID_PROJECT_DATA"

    with pytest.raises(ProjectError) as unknown:
        bindings._identity({"kind": "row"})
    assert code(unknown.value) == "INVALID_PROJECT_DATA"

    assert bindings._identity({"kind": "column", "columnId": "A"}) == {
        "kind": "column",
        "columnId": "A",
    }


def test_mapping_entries_are_normalised_and_unique_per_column():
    field_id = str(uuid4())
    assert bindings._mapping(
        [{"fieldId": field_id, "columnId": "b", "direction": "both", "formula": False}]
    ) == [{"fieldId": field_id, "columnId": "B", "direction": "both", "formula": False}]

    with pytest.raises(ProjectError) as duplicate:
        bindings._mapping(
            [
                {"fieldId": field_id, "columnId": "A", "direction": "both", "formula": False},
                {"fieldId": str(uuid4()), "columnId": "a", "direction": "read", "formula": False},
            ]
        )
    assert code(duplicate.value) == "INVALID_PROJECT_DATA"

    for bad in (
        [],
        [{"fieldId": field_id, "columnId": "A", "direction": "both", "formula": False}]
        * (bindings.MAX_MAPPING_ENTRIES + 1),
        [{"fieldId": field_id, "columnId": "A", "direction": "read", "formula": 0}],
        [{"fieldId": field_id, "columnId": "A", "direction": "append", "formula": False}],
        [{"fieldId": field_id, "columnId": "", "direction": "both", "formula": False}],
        [{"fieldId": field_id, "columnId": "A", "direction": "both"}],
        [{"fieldId": "not-a-uuid", "columnId": "A", "direction": "both", "formula": False}],
    ):
        with pytest.raises(ProjectError) as failure:
            bindings._mapping(bad)
        assert code(failure.value) == "INVALID_PROJECT_DATA"


def test_mapping_must_put_identity_on_a_text_field():
    identity_field, number_field, formula_field = str(uuid4()), str(uuid4()), str(uuid4())
    fields = [
        field(identity_field),
        field(number_field, type="number"),
        field(formula_field, formula=True),
    ]
    request: dict[str, Any] = {
        "identityStrategy": {"kind": "column", "columnId": "A"},
        "mapping": [
            {
                "fieldId": identity_field,
                "columnId": "A",
                "direction": "both",
                "formula": False,
            }
        ],
    }
    assert bindings._validate_mapping(request, fields) == identity_field

    not_text = {
        "identityStrategy": {"kind": "column", "columnId": "A"},
        "mapping": [
            {
                "fieldId": number_field,
                "columnId": "A",
                "direction": "both",
                "formula": False,
            }
        ],
    }
    with pytest.raises(ProjectError) as failure:
        bindings._validate_mapping(not_text, fields)
    assert code(failure.value) == "SHEETS_IDENTITY_NOT_TEXT"

    written_only = {
        "identityStrategy": {"kind": "column", "columnId": "A"},
        "mapping": [
            {
                "fieldId": identity_field,
                "columnId": "A",
                "direction": "write",
                "formula": False,
            }
        ],
    }
    with pytest.raises(ProjectError) as failure:
        bindings._validate_mapping(written_only, fields)
    assert code(failure.value) == "SHEETS_IDENTITY_NOT_MAPPED"

    wrong_column = {
        "identityStrategy": {"kind": "column", "columnId": "B"},
        "mapping": [
            {
                "fieldId": identity_field,
                "columnId": "A",
                "direction": "both",
                "formula": False,
            }
        ],
    }
    with pytest.raises(ProjectError) as failure:
        bindings._validate_mapping(wrong_column, fields)
    assert code(failure.value) == "SHEETS_IDENTITY_NOT_MAPPED"

    unknown_field = {
        "identityStrategy": {"kind": "column", "columnId": "A"},
        "mapping": [
            {
                "fieldId": str(uuid4()),
                "columnId": "A",
                "direction": "both",
                "formula": False,
            }
        ],
    }
    with pytest.raises(ProjectError) as failure:
        bindings._validate_mapping(unknown_field, fields)
    assert code(failure.value) == "SHEETS_MAPPING_UNKNOWN_FIELD"

    read_only_target = {
        "identityStrategy": {"kind": "column", "columnId": "A"},
        "mapping": [
            {
                "fieldId": identity_field,
                "columnId": "A",
                "direction": "both",
                "formula": False,
            },
            {
                "fieldId": formula_field,
                "columnId": "C",
                "direction": "both",
                "formula": True,
            },
        ],
    }
    with pytest.raises(ProjectError) as failure:
        bindings._validate_mapping(read_only_target, fields)
    assert code(failure.value) == "SHEETS_MAPPING_NOT_WRITABLE"


def binding_payload(**extra: Any) -> dict[str, Any]:
    body = {
        "connectionId": str(uuid4()),
        "spreadsheetId": "sheet-1",
        "sheetId": 0,
        "identityStrategy": {"kind": "column", "columnId": "A"},
        "mapping": [
            {
                "fieldId": str(uuid4()),
                "columnId": "A",
                "direction": "both",
                "formula": False,
            }
        ],
        "impactRevision": 9,
        "expectedTableRevision": 4,
    }
    body.update(extra)
    return body


def test_binding_request_needs_a_confirmation_and_a_table_revision():
    request = bindings._binding_request(binding_payload())
    assert request["impactRevision"] == 9
    assert request["expectedTableRevision"] == 4
    assert request["expectedBindingEpoch"] is None

    with_epoch = bindings._binding_request(binding_payload(expectedBindingEpoch=3))
    assert with_epoch["expectedBindingEpoch"] == 3

    assert bindings._inspection_request(
        {
            "connectionId": request["connectionId"],
            "spreadsheetId": request["spreadsheetId"],
            "sheetId": request["sheetId"],
            "identityStrategy": request["identityStrategy"],
            "mapping": request["mapping"],
        }
    )["sheetId"] == 0

    for bad in (
        {key: value for key, value in binding_payload().items() if key != "impactRevision"},
        binding_payload(impactRevision=0),
        binding_payload(expectedTableRevision=0),
        binding_payload(expectedBindingEpoch=0),
        binding_payload(extra="x"),
    ):
        with pytest.raises(ProjectError) as failure:
            bindings._binding_request(bad)
        assert code(failure.value) == "INVALID_PROJECT_DATA"


def test_remote_cells_are_fitted_to_the_local_field_type():
    assert outbound._coerce("string", "001") == "001"
    assert outbound._coerce("string", 1.0) == "1"
    assert outbound._coerce("string", 2.5) == "2.5"
    assert outbound._coerce("string", True) == "true"
    assert outbound._coerce("string", None) is None
    # Numbers and dates keep the remote shape so validation can judge them.
    assert outbound._coerce("number", 1) == 1
    assert outbound._coerce("boolean", True) is True

    assert outbound._cell_value([["a"]], 0, 0) == "a"
    assert outbound._cell_value([["a"]], 0, 4) == ""
    assert outbound._cell_value([["a"]], 3, 0) == ""
    assert outbound._cell_value([[None]], 0, 0) == ""


def test_verification_keeps_the_written_type_and_value():
    """A confirmed write must hold the same fact, not merely the same digits.

    Identity in this project is typed: the text ``"2"`` and the number ``2``
    are different records, so a cell that comes back with the wrong shape is
    not a confirmation. ``RAW`` writes preserve the shape, so the two sides of
    the check can be compared strictly, and the check must not depend on which
    side the caller put first.
    """
    assert outbound._same(2, 2)
    assert outbound._same(2.0, 2)
    assert outbound._same("", "")
    assert not outbound._same(2, "2")
    assert not outbound._same("2", 2)
    assert not outbound._same("001", 1)
    assert not outbound._same("2.5", 2.5)
    assert not outbound._same(2.5, "2.5")
    assert not outbound._same(2, "2.5")
    assert outbound._same("文本", "文本")
    assert not outbound._same("文本", "另一个")
    assert not outbound._same(None, "")
    assert not outbound._same("", None)
    assert outbound._same(None, None)
    assert outbound._same(True, True)
    assert not outbound._same(True, False)
    # A boolean cell never comes back as text, and the number 1 is not `true`.
    assert not outbound._same(True, "TRUE")
    assert not outbound._same(True, 1)


def test_outbound_identity_column_refuses_a_system_strategy():
    with pytest.raises(ProjectError) as failure:
        outbound._identity_column({"kind": "system"}, ["A"])
    assert code(failure.value) == "SYNC_NOT_IMPLEMENTED"

    assert outbound._identity_column({"kind": "column", "columnId": "B"}, ["A", "B"]) == 1
