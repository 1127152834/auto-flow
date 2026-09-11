from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.infrastructure.database.profiles import SqlAlchemyProfileRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def _profile(name="Stored", profile_id="profile-1"):
    spec = ProfileSpec.from_values({
        "name": name, "description": "desc", "start_url": "https://example.com/start", "locale": "zh-CN",
        "timezone": "Asia/Shanghai", "geoip": True, "headless": True, "humanize": True,
        "human_preset": "careful", "user_agent": "AutoFlow Test", "viewport": {"width": 1280, "height": 720},
        "color_scheme": "dark", "extension_paths": ["/tmp/ext"], "expert_args": ["--lang=en"],
        "browser_version": "146.0.1", "browser_edition": "licensed", "release_channel": "preview",
        "proxy_mode": "proxy", "proxy_id": "proxy-1", "proxy_pool_id": None,
    })
    now = datetime.now(UTC)
    return Profile(id=profile_id, spec=spec, fingerprint_seed=12345, created_at=now, updated_at=now)


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
    assert loaded == profile


def test_independent_transactions_enforce_unique_profile_names(tmp_path: Path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    first = factory()
    second = factory()
    try:
        SqlAlchemyProfileRepository(first).add(_profile(profile_id="profile-1"))
        SqlAlchemyProfileRepository(second).add(_profile(profile_id="profile-2"))
        first.commit()
        with pytest.raises(IntegrityError):
            second.commit()
        second.rollback()
        assert SqlAlchemyProfileRepository(second).get("profile-1") is not None
    finally:
        first.close()
        second.close()
        factory.dispose()
