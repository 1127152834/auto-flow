"""Remediation M4 S1 (R4-01, R4-02; AC4-06): identities own unique seeds; old duplicates are kept explicitly."""

from __future__ import annotations

import random
import threading
from datetime import UTC, datetime

import pytest

from autoflow.domain.identities.seeds import SEED_MAX, SEED_MIN
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.providers.browser.worker import browser_launch_options

PROJECT = "00000000-0000-4000-8000-0000000000aa"


@pytest.fixture
def identities(tmp_path):
    database = tmp_path / "identities.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    now = datetime.now(UTC)
    with factory() as session:
        session.add(ProjectRow(
            id=PROJECT, name="P", name_key="p", description="", search_text="p",
            default_resources={"profileId": None, "proxy": {"mode": "sourceDefault"}, "modelProviderId": None},
            management_revision=1, lifecycle_state="active", created_at=now, updated_at=now,
        ))
        session.commit()
    yield SqlAlchemyIdentities(factory)
    factory.dispose()


def test_a_thousand_new_identities_get_distinct_seeds_in_range(identities):
    seeds = [identities.create(PROJECT, f"账号{index}").seed for index in range(1000)]
    assert len(set(seeds)) == 1000
    assert all(SEED_MIN <= seed <= SEED_MAX for seed in seeds)


def test_concurrent_allocation_never_repeats_even_when_the_random_source_collides(identities):
    # A tiny random space forces real collisions; the unique registry must still win.
    created: list[int] = []
    lock = threading.Lock()

    def make(worker: int) -> None:
        rng = random.Random(worker)
        for index in range(10):
            seed = identities.create(PROJECT, f"w{worker}-{index}", randint=lambda low, high, r=rng: r.randint(SEED_MIN, SEED_MIN + 200)).seed
            with lock:
                created.append(seed)

    threads = [threading.Thread(target=make, args=(worker,)) for worker in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(created) == 80 and len(set(created)) == 80


def test_migration_may_share_an_old_seed_and_new_allocation_never_reuses_it(identities):
    first = identities.adopt_legacy_seed(PROJECT, "旧环境A", 42424)
    second = identities.adopt_legacy_seed(PROJECT, "旧环境B", 42424)
    assert first.seed == second.seed == 42424 and first.identity_id != second.identity_id
    assert identities.seed_report(PROJECT) == [{"seed": 42424, "legacyShared": True, "identities": sorted([first.identity_id, second.identity_id])}]
    draws = iter([42424, 50000])  # the random source offers the old shared value first
    fresh = identities.create(PROJECT, "新账号", randint=lambda low, high: next(draws))
    assert fresh.seed == 50000


def test_the_public_create_cannot_choose_a_seed(identities):
    with pytest.raises(TypeError):
        identities.create(PROJECT, "指定种子", seed=12345)  # type: ignore[call-arg]


def test_launch_accepts_the_identity_seed_range():
    base = {"humanPreset": "default", "browserVersion": "146", "releaseChannel": "stable", "geoip": False, "humanize": False,
            "expertArgs": [], "extensionPaths": []}
    assert f"--fingerprint={SEED_MAX}" in browser_launch_options({**base, "fingerprintSeed": SEED_MAX}, headless=True)["args"]
    with pytest.raises(ValueError):
        browser_launch_options({**base, "fingerprintSeed": SEED_MAX + 1}, headless=True)


def test_concurrent_first_runs_bind_the_proxy_member_once(identities):
    identity = identities.create(PROJECT, "代理账号")
    results: list[bool] = []
    lock = threading.Lock()

    def bind(member: str) -> None:
        stored = identities.swap_proxy_binding(identity.identity_id, None, {"poolId": "p", "memberId": member, "region": "上海", "policy": "sameRegion"})
        with lock:
            results.append(stored)

    threads = [threading.Thread(target=bind, args=(f"m{index}",)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count(True) == 1
    stored = identities.proxy_binding(identity.identity_id)
    assert stored["poolId"] == "p" and stored["memberId"].startswith("m")
    # Replacing needs the binding the caller saw; a stale view is refused.
    assert not identities.swap_proxy_binding(identity.identity_id, None, {"poolId": "p", "memberId": "late"})
    assert identities.swap_proxy_binding(identity.identity_id, stored, {**stored, "memberId": "next"})
