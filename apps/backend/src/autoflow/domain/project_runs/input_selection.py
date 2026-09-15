from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from autoflow.domain.project_data.identity import RecordKey

SelectionStatus = Literal[
    "ready", "noMatch", "temporarilyBusy", "configurationError"
]


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
class Candidate:
    record_ref: RecordRef
    lease_key: LeaseKey
    value: Mapping[str, Any]
    available: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze_mapping(self.value))


@dataclass(frozen=True)
class InputCandidates:
    input_id: str
    candidates: tuple[Candidate, ...]
    configuration_error: str | None = None

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
class InputSelection:
    status: SelectionStatus
    inputs: tuple[SelectedInput, ...] = ()
    lease_keys: tuple[LeaseKey, ...] = ()


def select_required_inputs(inputs: Sequence[InputCandidates]) -> InputSelection:
    sources = tuple(inputs)
    if len(sources) != 2 or len({source.input_id for source in sources}) != 2:
        return InputSelection("configurationError")
    if any(source.configuration_error is not None for source in sources):
        return InputSelection("configurationError")
    if any(not source.candidates for source in sources):
        return InputSelection("noMatch")

    selected: list[SelectedInput] = []
    for source in sources:
        candidate = next(
            (candidate for candidate in source.candidates if candidate.available), None
        )
        if candidate is None:
            return InputSelection("temporarilyBusy")
        selected.append(
            SelectedInput(
                source.input_id,
                candidate.record_ref,
                candidate.lease_key,
                candidate.value,
            )
        )

    lease_keys = tuple(dict.fromkeys(item.lease_key for item in selected))
    return InputSelection("ready", tuple(selected), lease_keys)


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
