import pytest

from autoflow.domain.profiles.errors import ProfileValidationError
from autoflow.domain.profiles.models import ProfileSpec


def test_public_preview_is_rejected(valid_profile_values):
    values = {**valid_profile_values, "browser_edition": "public", "release_channel": "preview"}
    with pytest.raises(ProfileValidationError, match="Stable"):
        ProfileSpec.from_values(values)


def test_profile_spec_normalizes_name_and_proxy_values(valid_profile_values):
    values = {**valid_profile_values, "name": "  Work  ", "proxy_mode": "proxy", "proxy_id": "proxy-1"}
    spec = ProfileSpec.from_values(values)
    assert spec.name == "Work"
    assert spec.proxy_id == "proxy-1"
    assert spec.proxy_pool_id is None


def test_profile_spec_rejects_forbidden_expert_argument(valid_profile_values):
    values = {**valid_profile_values, "expert_args": ["--proxy-server=http://localhost"]}
    with pytest.raises(ProfileValidationError, match="proxy-server"):
        ProfileSpec.from_values(values)
