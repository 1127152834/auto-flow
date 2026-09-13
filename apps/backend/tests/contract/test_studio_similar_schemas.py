import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import StudioSimilarPickerResult

SIMILAR = {"pattern": ".item:nth-child({index})", "count": 4, "minIndex": 1, "maxIndex": 4}


def test_selected_result_roundtrip():
    value = StudioSimilarPickerResult.model_validate({
        "selected": True, "active": True, "similar": SIMILAR,
    })
    assert StudioSimilarPickerResult.model_validate(value.model_dump(by_alias=True)) == value


@pytest.mark.parametrize("active", [False, True])
def test_empty_picker_states(active):
    assert not StudioSimilarPickerResult.model_validate({"selected": False, "active": active}).selected


@pytest.mark.parametrize("changes", [
    {"pattern": "div"}, {"pattern": 2}, {"count": 0}, {"count": 1.5},
    {"minIndex": -1}, {"maxIndex": 0}, {"indices": [1, 5]}, {"indices": [True]},
])
def test_invalid_patterns_and_ranges(changes):
    with pytest.raises(ValidationError):
        StudioSimilarPickerResult.model_validate({
            "selected": True, "active": True, "similar": {**SIMILAR, **changes},
        })


def test_selected_requires_result():
    with pytest.raises(ValidationError):
        StudioSimilarPickerResult.model_validate({"selected": True, "active": True})
