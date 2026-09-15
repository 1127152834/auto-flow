import pytest

from autoflow.domain.project_data.identity import RecordKey
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
) -> Candidate:
    return Candidate(
        record_ref(key, table_id=table_id),
        lease_key(key, table_id=table_id),
        value or {"fields": {"name": key.value}},
        available,
    )


def test_selects_the_first_available_candidate_and_keeps_aliases_while_deduplicating_leases():
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
            InputCandidates("recipient", (second_alias,)),
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


@pytest.mark.parametrize(
    "inputs",
    [
        (InputCandidates("only", (candidate(RecordKey("text", "1")),)),),
        (
            InputCandidates("duplicate", (candidate(RecordKey("text", "1")),)),
            InputCandidates("duplicate", (candidate(RecordKey("text", "2")),)),
        ),
    ],
)
def test_v1_requires_exactly_two_distinct_input_aliases(inputs):
    result = select_required_inputs(inputs)

    assert result.status == "configurationError"
    assert result.inputs == ()
    assert result.lease_keys == ()
