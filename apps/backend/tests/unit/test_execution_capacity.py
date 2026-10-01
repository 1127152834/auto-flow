"""Remediation M1 R1-07: the machine-sized default and strict override rules."""

import pytest

from autoflow.domain.settings.execution_capacity import (
    GIB,
    HardwareProfile,
    recommended_capacity,
    resolve_capacity,
    validate_configured,
)


@pytest.mark.parametrize(
    "cpus,memory_gib,expected",
    [(8, 16, 6), (4, 8, 3), (2, 4, 1), (16, 8, 5), (1, 1, 1), (128, 512, 64)],
)
def test_recommendation_is_bounded_by_cpu_and_memory(cpus, memory_gib, expected):
    assert recommended_capacity(HardwareProfile(cpus, memory_gib * GIB)) == expected


def test_resolve_uses_the_override_and_doubles_it_for_live_browsers():
    hardware = HardwareProfile(8, 16 * GIB)
    default = resolve_capacity(None, hardware)
    assert (default.configured, default.effective, default.live) == (None, 6, 12)
    chosen = resolve_capacity(7, hardware)
    assert (chosen.configured, chosen.recommended, chosen.effective, chosen.live) == (7, 6, 7, 14)


@pytest.mark.parametrize("value", [0, 65, -1, "3", 3.0, True, False, [], {}])
def test_invalid_overrides_are_rejected(value):
    with pytest.raises(ValueError):
        validate_configured(value)


def test_null_restores_the_recommendation_and_bounds_are_inclusive():
    assert validate_configured(None) is None
    assert validate_configured(1) == 1
    assert validate_configured(64) == 64
