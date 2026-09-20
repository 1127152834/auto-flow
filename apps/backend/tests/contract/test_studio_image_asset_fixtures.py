import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from autoflow.adapters.http.workflow_studio_schemas import StudioImageAsset

CASES = json.loads((Path(__file__).parents[1] / 'fixtures' / 'studio-image-assets.json').read_text(encoding="utf-8"))


@pytest.mark.parametrize('case', CASES, ids=[case['id'] for case in CASES])
def test_image_asset_shared_contract(case):
    adapter = TypeAdapter(list[StudioImageAsset])
    if case['expected'] is None:
        with pytest.raises(ValidationError):
            adapter.validate_python(case['value'])
    else:
        assets = adapter.validate_python(case['value'])
        assert [asset.model_dump(by_alias=True) for asset in assets] == case['expected']
