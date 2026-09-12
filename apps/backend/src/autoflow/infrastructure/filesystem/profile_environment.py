from pathlib import Path

from pydantic import TypeAdapter

from autoflow.domain.profiles.ports import ProfileEnvironmentOptions

CATALOG_PATH = Path(__file__).with_name("profile_environment.json")
_catalog_adapter = TypeAdapter(ProfileEnvironmentOptions)


def read_profile_environment_options() -> ProfileEnvironmentOptions:
    """Read the shipped catalog on each request; never substitute demo options."""
    catalog = _catalog_adapter.validate_json(CATALOG_PATH.read_bytes(), strict=True)
    for options in (catalog.locales, catalog.timezones):
        if not options or any(not item.value.strip() or not item.label.strip() for item in options):
            raise ValueError("Environment catalog must contain non-empty options")
        if len({item.value for item in options}) != len(options):
            raise ValueError("Environment catalog contains duplicate values")
    return catalog
