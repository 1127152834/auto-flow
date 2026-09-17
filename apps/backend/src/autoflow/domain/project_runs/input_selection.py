from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

from autoflow.domain.project_data.identity import RecordKey

SelectionStatus = Literal[
    "ready",
    "noMatch",
    "temporarilyBusy",
    "ambiguous",
    "configurationError",
    "scanBudgetExceeded",
]
InputMode = Literal["independent", "fixedRecord", "related"]
UnavailableReason = Literal["no_match", "busy"]
MAX_CANDIDATE_EVALUATIONS = 10_000


@dataclass(frozen=True)
class RecordRef:
    project_id: str
    table_id: str
    dataset_generation: str
    record_key: RecordKey


@dataclass(frozen=True)
class LeaseKey:
    source: Literal["local"]
    project_id: str
    table_id: str
    dataset_generation: str
    record_key: RecordKey


@dataclass(frozen=True)
class RecordSlotRelation:
    source_input_id: str
    slot_id: str


@dataclass(frozen=True)
class FieldEqualsRelation:
    source_input_id: str
    source_field_id: str
    target_field_id: str


@dataclass(frozen=True)
class SameRecordRelation:
    source_input_id: str


InputRelation = RecordSlotRelation | FieldEqualsRelation | SameRecordRelation


@dataclass(frozen=True)
class Candidate:
    record_ref: RecordRef
    lease_key: LeaseKey
    value: Mapping[str, Any]
    available: bool = True
    field_values: Mapping[str, Any] = field(default_factory=dict)
    record_slots: Mapping[str, RecordRef | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze_mapping(self.value))
        object.__setattr__(self, "field_values", _freeze_mapping(self.field_values))
        object.__setattr__(self, "record_slots", _freeze_mapping(self.record_slots))


@dataclass(frozen=True)
class InputCandidates:
    input_id: str
    candidates: tuple[Candidate, ...]
    configuration_error: str | None = None
    required: bool = True
    mode: InputMode = "independent"
    fixed_record: RecordRef | None = None
    relation: InputRelation | None = None
    scan_budget_exceeded: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))


@dataclass(frozen=True)
class SelectedInput:
    input_id: str
    record_ref: RecordRef
    lease_key: LeaseKey
    value: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze_mapping(self.value))


@dataclass(frozen=True)
class UnavailableInput:
    input_id: str
    reason: UnavailableReason


@dataclass(frozen=True)
class InputSelection:
    status: SelectionStatus
    inputs: tuple[SelectedInput, ...] = ()
    lease_keys: tuple[LeaseKey, ...] = ()
    unavailable_inputs: tuple[UnavailableInput, ...] = ()
    evaluated_candidate_bindings: int = 0
    issue_input_ids: tuple[str, ...] = ()
    issue_details: tuple[tuple[str, str], ...] = ()
    effective_required_input_ids: tuple[str, ...] = ()
    continuation_status: SelectionStatus | None = None
    continuation_input_ids: tuple[str, ...] = ()


def select_required_inputs(
    inputs: Sequence[InputCandidates],
    *,
    candidate_evaluation_budget: int = MAX_CANDIDATE_EVALUATIONS,
) -> InputSelection:
    sources = tuple(inputs)
    if (
        not sources
        or len({source.input_id for source in sources}) != len(sources)
        or type(candidate_evaluation_budget) is not int
        or candidate_evaluation_budget <= 0
    ):
        return InputSelection("configurationError")
    by_id = {source.input_id: source for source in sources}
    dependencies: dict[str, str | None] = {}
    for source in sources:
        relation = source.relation
        if (
            source.configuration_error is None
            and not source.scan_budget_exceeded
            and not _valid_shape(source, relation)
        ):
            return InputSelection(
                "configurationError", issue_input_ids=(source.input_id,)
            )
        dependency = relation.source_input_id if relation is not None else None
        if dependency == source.input_id or (
            dependency is not None and dependency not in by_id
        ):
            return InputSelection(
                "configurationError", issue_input_ids=(source.input_id,)
            )
        dependencies[source.input_id] = dependency

    ordered_ids = _topological_order(tuple(by_id), dependencies)
    if ordered_ids is None:
        return InputSelection(
            "configurationError",
            issue_input_ids=_dependency_cycle(tuple(by_id), dependencies),
        )

    effectively_required = {source.input_id for source in sources if source.required}
    pending = list(effectively_required)
    while pending:
        dependency = dependencies[pending.pop()]
        if dependency is not None and dependency not in effectively_required:
            effectively_required.add(dependency)
            pending.append(dependency)
    effective_required_ids = tuple(
        input_id for input_id in by_id if input_id in effectively_required
    )
    invalid_sources = tuple(
        source.input_id for source in sources if source.configuration_error is not None
    )
    if invalid_sources:
        return InputSelection(
            "configurationError",
            issue_input_ids=invalid_sources,
            issue_details=tuple(
                (source.input_id, source.configuration_error or "输入配置无效")
                for source in sources
                if source.input_id in invalid_sources
            ),
            effective_required_input_ids=effective_required_ids,
        )
    scan_limited_sources = tuple(
        source.input_id
        for source in sources
        if source.scan_budget_exceeded and not source.candidates
    )
    if scan_limited_sources:
        return InputSelection(
            "scanBudgetExceeded",
            evaluated_candidate_bindings=MAX_CANDIDATE_EVALUATIONS,
            issue_input_ids=scan_limited_sources,
            issue_details=tuple(
                (input_id, "record scan budget exceeded")
                for input_id in scan_limited_sources
            ),
            effective_required_input_ids=effective_required_ids,
            continuation_input_ids=scan_limited_sources,
        )

    # An empty independent/fixed required source makes every possible group
    # impossible, even if an earlier source is temporarily busy.
    for input_id in effectively_required:
        source = by_id[input_id]
        if source.mode == "independent" and not source.candidates:
            return InputSelection(
                "noMatch",
                issue_input_ids=(input_id,),
                effective_required_input_ids=effective_required_ids,
            )
        if source.mode == "fixedRecord" and not any(
            item.record_ref == source.fixed_record for item in source.candidates
        ):
            return InputSelection(
                "noMatch",
                issue_input_ids=(input_id,),
                effective_required_input_ids=effective_required_ids,
            )

    budget = _EvaluationBudget(candidate_evaluation_budget)
    try:
        outcome = _search(
            ordered_ids,
            by_id,
            effectively_required,
            selected={},
            unavailable={},
            budget=budget,
        )
    except _BudgetExceeded:
        return InputSelection(
            "scanBudgetExceeded",
            evaluated_candidate_bindings=budget.evaluated,
            issue_input_ids=(ordered_ids[-1],),
            issue_details=((ordered_ids[-1], "candidate binding budget exceeded"),),
            effective_required_input_ids=effective_required_ids,
        )

    if isinstance(outcome, _SearchFailure):
        continuation_ids = tuple(
            source.input_id for source in sources if source.scan_budget_exceeded
        )
        if continuation_ids and outcome.status in {"noMatch", "temporarilyBusy"}:
            return InputSelection(
                "scanBudgetExceeded",
                evaluated_candidate_bindings=budget.evaluated,
                issue_input_ids=continuation_ids,
                issue_details=tuple(
                    (input_id, "candidate scan has a continuation")
                    for input_id in continuation_ids
                ),
                effective_required_input_ids=effective_required_ids,
                continuation_status=outcome.status,
                continuation_input_ids=continuation_ids,
            )
        return InputSelection(
            outcome.status,
            evaluated_candidate_bindings=budget.evaluated,
            issue_input_ids=outcome.issue_input_ids,
            issue_details=outcome.issue_details,
            effective_required_input_ids=effective_required_ids,
        )
    chosen, unavailable = outcome
    selected_inputs = tuple(
        SelectedInput(
            input_id,
            chosen[input_id].record_ref,
            chosen[input_id].lease_key,
            chosen[input_id].value,
        )
        for input_id in by_id
        if input_id in chosen
    )
    lease_keys = tuple(dict.fromkeys(item.lease_key for item in selected_inputs))
    unavailable_inputs = tuple(
        UnavailableInput(input_id, unavailable[input_id])
        for input_id in by_id
        if input_id in unavailable
    )
    return InputSelection(
        "ready",
        selected_inputs,
        lease_keys,
        unavailable_inputs,
        budget.evaluated,
        effective_required_input_ids=effective_required_ids,
    )


SearchFailureStatus = Literal[
    "noMatch", "temporarilyBusy", "ambiguous", "configurationError"
]


@dataclass(frozen=True)
class _SearchFailure:
    status: SearchFailureStatus
    issue_input_ids: tuple[str, ...]
    issue_details: tuple[tuple[str, str], ...] = ()


SearchOutcome = (
    tuple[dict[str, Candidate], dict[str, UnavailableReason]] | _SearchFailure
)


@dataclass
class _EvaluationBudget:
    limit: int
    evaluated: int = 0

    def consume(self) -> None:
        if self.evaluated >= self.limit:
            raise _BudgetExceeded
        self.evaluated += 1


class _BudgetExceeded(Exception):
    pass


def _search(
    ordered_ids: tuple[str, ...],
    sources: Mapping[str, InputCandidates],
    effectively_required: set[str],
    *,
    selected: dict[str, Candidate],
    unavailable: dict[str, UnavailableReason],
    budget: _EvaluationBudget,
    index: int = 0,
) -> SearchOutcome:
    if index == len(ordered_ids):
        return selected, unavailable

    input_id = ordered_ids[index]
    source = sources[input_id]
    relation = source.relation
    if relation is not None and relation.source_input_id in unavailable:
        if input_id in effectively_required:
            return _SearchFailure(
                _reason_status(unavailable[relation.source_input_id]), (input_id,)
            )
        next_unavailable = dict(unavailable)
        next_unavailable[input_id] = unavailable[relation.source_input_id]
        return _search(
            ordered_ids,
            sources,
            effectively_required,
            selected=selected,
            unavailable=next_unavailable,
            budget=budget,
            index=index + 1,
        )

    matches, ambiguity_detail = _matching_candidates(source, selected, budget)
    if ambiguity_detail is not None:
        return _SearchFailure("ambiguous", (input_id,), ((input_id, ambiguity_detail),))

    failures: list[_SearchFailure] = []
    saw_busy = False
    for candidate in matches:
        if source.mode == "independent":
            budget.consume()
        if not candidate.available:
            saw_busy = True
            continue
        if candidate.lease_key in {chosen.lease_key for chosen in selected.values()}:
            shared_with_source = (
                isinstance(relation, SameRecordRelation)
                and relation.source_input_id in selected
                and selected[relation.source_input_id].lease_key == candidate.lease_key
            )
            if not shared_with_source:
                continue
        next_selected = dict(selected)
        next_selected[input_id] = candidate
        outcome = _search(
            ordered_ids,
            sources,
            effectively_required,
            selected=next_selected,
            unavailable=unavailable,
            budget=budget,
            index=index + 1,
        )
        if isinstance(outcome, tuple):
            return outcome
        if outcome.status == "configurationError":
            return outcome
        failures.append(outcome)

    if input_id not in effectively_required:
        reason: UnavailableReason = "busy" if saw_busy else "no_match"
        next_unavailable = dict(unavailable)
        next_unavailable[input_id] = reason
        return _search(
            ordered_ids,
            sources,
            effectively_required,
            selected=selected,
            unavailable=next_unavailable,
            budget=budget,
            index=index + 1,
        )

    return _strongest_failure(failures, saw_busy, input_id)


def _matching_candidates(
    source: InputCandidates,
    selected: Mapping[str, Candidate],
    budget: _EvaluationBudget,
) -> tuple[tuple[Candidate, ...], str | None]:
    if source.mode == "independent":
        return source.candidates, None
    if source.mode == "fixedRecord":
        matches = _evaluated_matches(
            source.candidates,
            budget,
            lambda item: item.record_ref == source.fixed_record,
        )
        return matches, _ambiguity_detail(None, matches) if len(matches) > 1 else None

    relation = source.relation
    if relation is None or relation.source_input_id not in selected:
        return (), None
    origin = selected[relation.source_input_id]
    if isinstance(relation, SameRecordRelation):
        predicate = lambda item: item.record_ref == origin.record_ref
    elif isinstance(relation, RecordSlotRelation):
        target = origin.record_slots.get(relation.slot_id)
        if target is None:
            return (), None
        predicate = lambda item: item.record_ref == target
    elif isinstance(relation, FieldEqualsRelation):
        if relation.source_field_id not in origin.field_values:
            return (), None
        expected = origin.field_values[relation.source_field_id]
        if expected is None:
            return (), None
        predicate = lambda item: (
            relation.target_field_id in item.field_values
            and _scalar_equal(expected, item.field_values[relation.target_field_id])
        )
    else:
        return (), None
    matches = _evaluated_matches(source.candidates, budget, predicate)
    expected_value = (
        origin.field_values.get(relation.source_field_id)
        if isinstance(relation, FieldEqualsRelation)
        else None
    )
    return (
        matches,
        _ambiguity_detail(expected_value, matches) if len(matches) > 1 else None,
    )


def _ambiguity_detail(value: Any, matches: tuple[Candidate, ...]) -> str:
    shown = ", ".join(
        f"{item.record_ref.record_key.type}:{item.record_ref.record_key.value}"
        for item in matches[:5]
    )
    value_text = repr(value)[:120] if value is not None else "当前关联条件"
    suffix = "…" if len(matches) > 5 else ""
    return f"ambiguous value {value_text}; records {shown}{suffix}"


def _evaluated_matches(
    candidates: tuple[Candidate, ...],
    budget: _EvaluationBudget,
    predicate,
) -> tuple[Candidate, ...]:
    matches: list[Candidate] = []
    for candidate in candidates:
        budget.consume()
        if predicate(candidate):
            matches.append(candidate)
    return tuple(matches)


def _valid_shape(source: InputCandidates, relation: InputRelation | None) -> bool:
    if type(source.required) is not bool:
        return False
    if source.mode == "independent":
        return source.fixed_record is None and relation is None
    if source.mode == "fixedRecord":
        return source.fixed_record is not None and relation is None
    if source.mode == "related":
        return source.fixed_record is None and isinstance(
            relation, RecordSlotRelation | FieldEqualsRelation | SameRecordRelation
        )
    return False


def _topological_order(
    input_ids: tuple[str, ...], dependencies: Mapping[str, str | None]
) -> tuple[str, ...] | None:
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(input_id: str) -> bool:
        if input_id in visited:
            return True
        if input_id in visiting:
            return False
        visiting.add(input_id)
        dependency = dependencies[input_id]
        if dependency is not None and not visit(dependency):
            return False
        visiting.remove(input_id)
        visited.add(input_id)
        ordered.append(input_id)
        return True

    if not all(visit(input_id) for input_id in input_ids):
        return None
    return tuple(ordered)


def _dependency_cycle(
    input_ids: tuple[str, ...], dependencies: Mapping[str, str | None]
) -> tuple[str, ...]:
    for origin in input_ids:
        path: list[str] = []
        positions: dict[str, int] = {}
        current: str | None = origin
        while current is not None:
            if current in positions:
                cycle = set(path[positions[current] :])
                return tuple(input_id for input_id in input_ids if input_id in cycle)
            positions[current] = len(path)
            path.append(current)
            current = dependencies[current]
    return ()


def _scalar_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return left == right
    return type(left) is type(right) and left == right


def _reason_status(reason: UnavailableReason) -> SearchFailureStatus:
    return "temporarilyBusy" if reason == "busy" else "noMatch"


def _strongest_failure(
    failures: Sequence[_SearchFailure], saw_busy: bool, input_id: str
) -> _SearchFailure:
    for status in ("ambiguous", "temporarilyBusy"):
        match = next(
            (failure for failure in failures if failure.status == status), None
        )
        if match is not None:
            return match
    if saw_busy:
        return _SearchFailure("temporarilyBusy", (input_id,))
    match = next((failure for failure in failures if failure.status == "noMatch"), None)
    return match or _SearchFailure("noMatch", (input_id,))


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze(item) for key, item in value.items()})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value
