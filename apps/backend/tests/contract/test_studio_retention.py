"""Retention wire contracts preserve snake-case limits and explicit cleanup totals."""

import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioRetentionCleanup,
    StudioRetentionConfig,
    StudioRetentionLoaded,
)

CONFIG = {
    "enabled": False,
    "recordings_max_days": 30,
    "recordings_max_total_mb": 0,
    "data_max_days": 30,
    "data_max_total_mb": 0,
    "cleanup_interval_hours": 24,
}


@pytest.mark.parametrize(
    "patch",
    [
        {"enabled": "true"},
        {"data_max_days": -1},
        {"data_max_days": 1.5},
        {"data_max_days": True},
        {"cleanup_interval_hours": 0},
        {"data_max_days": 9007199254740992},
        {"extra": 1},
    ],
)
def test_invalid_configuration(patch):
    with pytest.raises(ValidationError):
        StudioRetentionConfig.model_validate(CONFIG | patch)


def test_config_roundtrip_and_usage_aliases():
    payload = {
        "success": True,
        "mock": True,
        "config": CONFIG,
        "usage": {
            "recordings": {"count": 0, "sizeMB": 0.5},
            "data": {"count": 1, "sizeMB": 2},
        },
    }
    assert (
        StudioRetentionLoaded.model_validate(payload).model_dump(by_alias=True)
        == payload
    )


@pytest.mark.parametrize("value", [-1, 1.5, "1", True])
def test_invalid_removed(value):
    with pytest.raises(ValidationError):
        StudioRetentionCleanup.model_validate(
            {
                "success": True,
                "recordings": {"removed": value, "freedMB": 0},
                "data": {"removed": 0, "freedMB": 0},
            }
        )


@pytest.mark.parametrize("value", [float("inf"), float("nan"), -1])
def test_invalid_freed_size(value):
    with pytest.raises(ValidationError):
        StudioRetentionCleanup.model_validate(
            {
                "success": True,
                "recordings": {"removed": 0, "freedMB": value},
                "data": {"removed": 0, "freedMB": 0},
            }
        )


@pytest.mark.parametrize("value", [1, "true", False])
def test_explicit_confirmation(value):
    with pytest.raises(ValidationError):
        StudioRetentionCleanup.model_validate(
            {
                "success": value,
                "recordings": {"removed": 0, "freedMB": 0},
                "data": {"removed": 0, "freedMB": 0},
            }
        )


def test_partial_update_preserves_wire_names_and_nulls():
    from autoflow.adapters.http.workflow_studio_schemas import StudioRetentionUpdate

    value = StudioRetentionUpdate.model_validate(
        {"recordings_max_days": 7, "cleanup_interval_hours": None}
    )
    assert value.model_dump(by_alias=True, exclude_unset=True) == {
        "recordings_max_days": 7,
        "cleanup_interval_hours": None,
    }


@pytest.mark.parametrize("patch", [{"enabled": "true"}, {"cleanup_interval_hours": 0}])
def test_partial_update_rejects_invalid_explicit_values(patch):
    from autoflow.adapters.http.workflow_studio_schemas import StudioRetentionUpdate

    with pytest.raises(ValidationError):
        StudioRetentionUpdate.model_validate(patch)
