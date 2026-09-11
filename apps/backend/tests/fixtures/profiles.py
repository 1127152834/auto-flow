import pytest


@pytest.fixture
def valid_profile_values():
    return {
        "name": "Default profile",
        "description": "",
        "start_url": "about:blank",
        "locale": None,
        "timezone": None,
        "geoip": False,
        "headless": False,
        "humanize": False,
        "human_preset": "default",
        "user_agent": None,
        "viewport": None,
        "color_scheme": None,
        "extension_paths": [],
        "expert_args": [],
        "browser_version": "146.0.1",
        "browser_edition": "public",
        "release_channel": "stable",
        "proxy_mode": "none",
        "proxy_id": None,
        "proxy_pool_id": None,
    }
