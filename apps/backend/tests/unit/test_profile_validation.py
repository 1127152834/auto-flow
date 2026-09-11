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


@pytest.mark.parametrize(
    ("argument", "expected"),
    [
        ("--proxy-server=http://localhost", "proxy-server"),
        ("--proxy-server http://localhost", "proxy-server"),
        ("--user-data-dir /tmp/profile", "user-data-dir"),
    ],
)
def test_profile_spec_rejects_forbidden_expert_argument(valid_profile_values, argument, expected):
    values = {**valid_profile_values, "expert_args": [argument]}
    with pytest.raises(ProfileValidationError, match=expected):
        ProfileSpec.from_values(values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start_url", "http:"),
        ("locale", "en--US"),
        ("timezone", "Mars/Olympus"),
        ("viewport", {"width": "wide", "height": 720}),
        ("browser_version", ""),
        ("browser_edition", "wat"),
        ("release_channel", "nightly"),
        ("human_preset", "fast"),
        ("color_scheme", "sepia"),
    ],
)
def test_profile_spec_rejects_invalid_contract_values(valid_profile_values, field, value):
    with pytest.raises(ProfileValidationError):
        ProfileSpec.from_values({**valid_profile_values, field: value})


@pytest.mark.parametrize("locale", ["en", "en-US", "zh-Hans-CN"])
def test_profile_spec_accepts_bcp47_locale_shapes(valid_profile_values, locale):
    assert ProfileSpec.from_values({**valid_profile_values, "locale": locale}).locale == locale
