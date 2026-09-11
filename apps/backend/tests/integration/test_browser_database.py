from datetime import UTC, datetime
from pathlib import Path

from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.infrastructure.database.profiles import SqlAlchemyProfileRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def _profile(name="Stored"):
    spec = ProfileSpec.from_values({
        "name": name, "description": "desc", "start_url": "about:blank", "locale": None,
        "timezone": None, "geoip": False, "headless": False, "humanize": False,
        "human_preset": "default", "user_agent": None, "viewport": {"width": 1280, "height": 720},
        "color_scheme": "dark", "extension_paths": ["/tmp/ext"], "expert_args": ["--lang=en"],
        "browser_version": "146.0.1", "browser_edition": "public", "release_channel": "stable",
        "proxy_mode": "none", "proxy_id": None, "proxy_pool_id": None,
    })
    now = datetime.now(UTC)
    return Profile(id="profile-1", spec=spec, fingerprint_seed=12345, created_at=now, updated_at=now)


def test_empty_database_migrates_idempotently_and_roundtrips(tmp_path: Path):
    database = tmp_path / "nested" / "autoflow.sqlite3"
    migrate_database(database)
    migrate_database(database)
    factory = create_session_factory(database)
    profile = _profile()
    with factory.begin() as session:
        SqlAlchemyProfileRepository(session).add(profile)
    factory.dispose()
    factory = create_session_factory(database)
    with factory() as session:
        loaded = SqlAlchemyProfileRepository(session).get("profile-1")
    assert loaded is not None
    assert loaded.spec.viewport == {"width": 1280, "height": 720}
    assert loaded.spec.extension_paths == ["/tmp/ext"]
