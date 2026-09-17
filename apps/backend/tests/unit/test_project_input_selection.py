import pytest

from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs import input_selection as selection
from autoflow.domain.project_runs.input_selection import (
    Candidate,
    InputCandidates,
    LeaseKey,
    RecordRef,
    select_required_inputs,
)


def record_ref(key: RecordKey, *, table_id: str = "table-1") -> RecordRef:
    return RecordRef("project-1", table_id, "generation-1", key)


def lease_key(key: RecordKey, *, table_id: str = "table-1") -> LeaseKey:
    return LeaseKey("local", "project-1", table_id, "generation-1", key)


def candidate(
    key: RecordKey,
    *,
    table_id: str = "table-1",
    available: bool = True,
    value=None,
    field_values=None,
    record_slots=None,
) -> Candidate:
    return Candidate(
        record_ref(key, table_id=table_id),
        lease_key(key, table_id=table_id),
        value or {"fields": {"name": key.value}},
        available,
        field_values or {},
        record_slots or {},
    )


def test_explicit_same_record_keeps_aliases_while_deduplicating_leases():
    mutable_value = {
        "fields": {"email": "chosen@example.com"},
        "tags": ["ready"],
    }
    busy = candidate(RecordKey("text", "busy"), available=False)
    shared_key = RecordKey("text", "shared")
    first_alias = candidate(shared_key, value=mutable_value)
    second_alias = candidate(shared_key, value={"fields": {"role": "recipient"}})

    result = select_required_inputs(
        (
            InputCandidates("sender", (busy, first_alias)),
            InputCandidates(
                "recipient",
                (second_alias,),
                mode="related",
                relation=selection.SameRecordRelation("sender"),
            ),
        )
    )
    mutable_value["fields"]["email"] = "mutated@example.com"
    mutable_value["tags"].append("mutated")

    assert result.status == "ready"
    assert tuple(item.input_id for item in result.inputs) == ("sender", "recipient")
    assert result.inputs[0].record_ref == result.inputs[1].record_ref
    assert result.inputs[0].value == {
        "fields": {"email": "chosen@example.com"},
        "tags": ("ready",),
    }
    assert result.lease_keys == (lease_key(shared_key),)
    with pytest.raises(TypeError):
        result.inputs[0].value["fields"]["email"] = "cannot mutate"


def test_typed_record_identity_is_not_collapsed_to_its_string_value():
    text_key = RecordKey("text", "1")
    integer_key = RecordKey("integer", "1")

    result = select_required_inputs(
        (
            InputCandidates("text", (candidate(text_key),)),
            InputCandidates("integer", (candidate(integer_key),)),
        )
    )

    assert result.status == "ready"
    assert result.lease_keys == (lease_key(text_key), lease_key(integer_key))
    assert result.inputs[0].record_ref != result.inputs[1].record_ref


@pytest.mark.parametrize(
    ("inputs", "expected_status"),
    [
        (
            (
                InputCandidates("missing", ()),
                InputCandidates(
                    "busy",
                    (candidate(RecordKey("text", "2"), available=False),),
                ),
            ),
            "noMatch",
        ),
        (
            (
                InputCandidates(
                    "busy",
                    (candidate(RecordKey("text", "3"), available=False),),
                ),
                InputCandidates(
                    "ready",
                    (candidate(RecordKey("text", "4"), table_id="table-2"),),
                ),
            ),
            "temporarilyBusy",
        ),
        (
            (
                InputCandidates(
                    "invalid",
                    (),
                    configuration_error="field no longer exists",
                ),
                InputCandidates("missing", ()),
            ),
            "configurationError",
        ),
    ],
)
def test_required_input_failures_are_classified_without_partial_results(
    inputs, expected_status
):
    result = select_required_inputs(inputs)

    assert result.status == expected_status
    assert result.inputs == ()
    assert result.lease_keys == ()


def test_input_aliases_must_be_distinct():
    inputs = (
        InputCandidates("duplicate", (candidate(RecordKey("text", "1")),)),
        InputCandidates("duplicate", (candidate(RecordKey("text", "2")),)),
    )
    result = select_required_inputs(inputs)

    assert result.status == "configurationError"
    assert result.inputs == ()
    assert result.lease_keys == ()


def test_independent_same_table_roles_backtrack_to_distinct_records():
    r1 = RecordKey("text", "R01")
    r2 = RecordKey("text", "R02")

    result = select_required_inputs(
        (
            InputCandidates("x", (candidate(r1), candidate(r2))),
            InputCandidates("y", (candidate(r1),)),
        )
    )

    assert result.status == "ready"
    assert [item.record_ref.record_key for item in result.inputs] == [r2, r1]


def test_only_an_explicit_same_record_alias_may_share_an_existing_lease():
    r1 = candidate(
        RecordKey("text", "R01"),
        field_values={"join": "shared"},
    )
    r2 = candidate(
        RecordKey("text", "R02"),
        field_values={"join": "shared"},
    )

    result = select_required_inputs(
        (
            InputCandidates("unrelated", (r1,)),
            InputCandidates("source", (r2,)),
            InputCandidates(
                "related",
                (r1,),
                mode="related",
                relation=selection.FieldEqualsRelation("source", "join", "join"),
            ),
        )
    )

    assert result.status == "noMatch"
    assert result.inputs == ()


def test_fixed_record_selects_only_the_frozen_typed_reference():
    text_one = candidate(RecordKey("text", "1"))
    integer_one = candidate(RecordKey("integer", "1"))
    other = candidate(RecordKey("text", "other"), table_id="table-2")

    result = select_required_inputs(
        (
            InputCandidates(
                "fixed",
                (integer_one, text_one),
                mode="fixedRecord",
                fixed_record=text_one.record_ref,
            ),
            InputCandidates("other", (other,)),
        )
    )

    assert result.status == "ready"
    assert result.inputs[0].record_ref == text_one.record_ref


def test_field_equals_uses_typed_exact_values_and_dependency_order():
    source = candidate(
        RecordKey("text", "source"),
        table_id="people",
        field_values={"email_ref": "001"},
    )
    numeric = candidate(
        RecordKey("text", "numeric"),
        table_id="emails",
        field_values={"identity": 1},
    )
    exact = candidate(
        RecordKey("text", "exact"),
        table_id="emails",
        field_values={"identity": "001"},
    )

    result = select_required_inputs(
        (
            InputCandidates(
                "email",
                (numeric, exact),
                mode="related",
                relation=selection.FieldEqualsRelation(
                    "person", "email_ref", "identity"
                ),
            ),
            InputCandidates("person", (source,)),
        )
    )

    assert result.status == "ready"
    assert [item.input_id for item in result.inputs] == ["email", "person"]
    assert result.inputs[0].record_ref == exact.record_ref


def test_field_equals_does_not_match_null_source_to_null_targets():
    source = candidate(
        RecordKey("text", "source"),
        table_id="people",
        field_values={"email_ref": None},
    )
    target = candidate(
        RecordKey("text", "target"),
        table_id="emails",
        field_values={"identity": None},
    )

    result = select_required_inputs(
        (
            InputCandidates("person", (source,)),
            InputCandidates(
                "email",
                (target,),
                mode="related",
                relation=selection.FieldEqualsRelation(
                    "person", "email_ref", "identity"
                ),
            ),
        )
    )

    assert result.status == "noMatch"


def test_record_slot_follows_the_frozen_record_reference():
    manager = candidate(RecordKey("text", "R02"))
    sender = candidate(
        RecordKey("text", "R01"),
        record_slots={"managerRef": manager.record_ref},
    )

    result = select_required_inputs(
        (
            InputCandidates("sender", (sender,)),
            InputCandidates(
                "manager",
                (candidate(RecordKey("text", "R03")), manager),
                mode="related",
                relation=selection.RecordSlotRelation("sender", "managerRef"),
            ),
        )
    )

    assert result.status == "ready"
    assert result.inputs[1].record_ref == manager.record_ref


def test_related_multiple_exact_matches_are_ambiguous_instead_of_picking_first():
    source = candidate(
        RecordKey("text", "source"),
        table_id="source",
        field_values={"join": "duplicate"},
    )
    targets = tuple(
        candidate(
            RecordKey("text", key),
            table_id="target",
            field_values={"join": "duplicate"},
        )
        for key in ("one", "two")
    )

    result = select_required_inputs(
        (
            InputCandidates("source", (source,)),
            InputCandidates(
                "target",
                targets,
                mode="related",
                relation=selection.FieldEqualsRelation("source", "join", "join"),
            ),
        )
    )

    assert result.status == "ambiguous"
    assert result.inputs == ()


@pytest.mark.parametrize(
    ("available", "reason"),
    [(True, "no_match"), (False, "busy")],
)
def test_optional_input_freezes_a_reason_instead_of_failing_the_group(
    available, reason
):
    optional_candidates = (
        ()
        if available
        else (candidate(RecordKey("text", "busy"), available=False),)
    )
    required = candidate(RecordKey("text", "required"), table_id="required")

    result = select_required_inputs(
        (
            InputCandidates("required", (required,)),
            InputCandidates("optional", optional_candidates, required=False),
        )
    )

    assert result.status == "ready"
    assert [item.input_id for item in result.inputs] == ["required"]
    assert result.unavailable_inputs == (
        selection.UnavailableInput("optional", reason),
    )


def test_required_descendant_makes_its_optional_ancestor_effectively_required():
    target = candidate(RecordKey("text", "target"), table_id="target")

    result = select_required_inputs(
        (
            InputCandidates("optional-source", (), required=False),
            InputCandidates(
                "required-target",
                (target,),
                mode="related",
                relation=selection.SameRecordRelation("optional-source"),
            ),
        )
    )

    assert result.status == "noMatch"
    assert result.inputs == ()
    assert result.effective_required_input_ids == (
        "optional-source",
        "required-target",
    )
    assert result.issue_input_ids == ("optional-source",)


@pytest.mark.parametrize(
    "inputs",
    [
        (
            InputCandidates(
                "orphan",
                (),
                mode="related",
                relation=None,
            ),
        ),
        (
            InputCandidates(
                "a",
                (),
                mode="related",
                relation=lambda: None,
            ),
        ),
    ],
)
def test_invalid_relation_configuration_never_becomes_optional_empty(inputs):
    result = select_required_inputs(inputs)

    assert result.status == "configurationError"


def test_missing_dependency_and_dependency_cycle_are_configuration_errors():
    missing = select_required_inputs(
        (
            InputCandidates(
                "target",
                (),
                mode="related",
                relation=selection.SameRecordRelation("missing"),
            ),
        )
    )
    cycle = select_required_inputs(
        (
            InputCandidates(
                "a",
                (),
                mode="related",
                relation=selection.SameRecordRelation("b"),
            ),
            InputCandidates(
                "b",
                (),
                mode="related",
                relation=selection.SameRecordRelation("a"),
            ),
        )
    )

    assert missing.status == "configurationError"
    assert cycle.status == "configurationError"
    assert missing.issue_input_ids == ("target",)
    assert cycle.issue_input_ids == ("a", "b")


def test_configuration_error_on_optional_input_is_not_treated_as_missing():
    result = select_required_inputs(
        (
            InputCandidates(
                "optional",
                (),
                configuration_error="field no longer exists",
                required=False,
            ),
        )
    )

    assert result.status == "configurationError"
    assert result.unavailable_inputs == ()
    assert result.issue_input_ids == ("optional",)
    assert result.issue_details == (("optional", "field no longer exists"),)


def test_invalid_optional_source_is_still_effectively_required_by_its_descendant():
    result = select_required_inputs(
        (
            InputCandidates(
                "optional-source",
                (),
                configuration_error="table generation is no longer current",
                required=False,
            ),
            InputCandidates(
                "required-target",
                (),
                mode="related",
                relation=selection.SameRecordRelation("optional-source"),
            ),
        )
    )

    assert result.status == "configurationError"
    assert result.issue_input_ids == ("optional-source",)
    assert result.effective_required_input_ids == (
        "optional-source",
        "required-target",
    )


def test_scan_limited_optional_source_is_still_required_by_its_descendant():
    result = select_required_inputs(
        (
            InputCandidates(
                "optional-source", (), required=False, scan_budget_exceeded=True
            ),
            InputCandidates(
                "required-target",
                (),
                mode="related",
                relation=selection.SameRecordRelation("optional-source"),
            ),
        )
    )

    assert result.status == "scanBudgetExceeded"
    assert result.effective_required_input_ids == (
        "optional-source",
        "required-target",
    )


def test_candidate_evaluation_budget_is_explicit_and_exhaustion_is_not_no_match():
    assert selection.MAX_CANDIDATE_EVALUATIONS == 10_000
    busy = tuple(
        candidate(RecordKey("text", str(index)), available=False)
        for index in range(3)
    )

    result = select_required_inputs(
        (InputCandidates("input", busy),), candidate_evaluation_budget=2
    )

    assert result.status == "scanBudgetExceeded"
    assert result.evaluated_candidate_bindings == 2


def test_repository_scan_budget_exhaustion_is_not_configuration_or_no_match():
    result = select_required_inputs(
        (InputCandidates("input", (), scan_budget_exceeded=True),)
    )

    assert result.status == "scanBudgetExceeded"
    assert result.issue_input_ids == ("input",)


def test_configuration_error_takes_priority_over_scan_budget_exhaustion():
    result = select_required_inputs(
        (
            InputCandidates("scan", (), scan_budget_exceeded=True),
            InputCandidates("bad", (), configuration_error="field no longer exists"),
        )
    )

    assert result.status == "configurationError"
    assert result.issue_input_ids == ("bad",)
