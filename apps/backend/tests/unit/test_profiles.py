from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from autoflow.application.profiles.service import ProfileService
from autoflow.domain.profiles.errors import ProfileDirectoryBusy
from autoflow.domain.profiles.models import Profile, ProfileSpec


class FakeRepository:
    def __init__(self, profiles: list[Profile]) -> None:
        self.profiles = profiles

    def add(self, profile: Profile) -> None:
        self.profiles.append(profile)

    def get(self, profile_id: str) -> Profile | None:
        return next((profile for profile in self.profiles if profile.id == profile_id), None)

    def list(self) -> list[Profile]:
        return list(self.profiles)

    def update(self, profile: Profile) -> None:
        self.remove(profile.id)
        self.profiles.append(profile)

    def remove(self, profile_id: str) -> None:
        self.profiles[:] = [profile for profile in self.profiles if profile.id != profile_id]


class FakeKernels:
    def is_installed(self, edition: str, version: str) -> bool:
        return True


class FakeProxies:
    def proxy_is_available(self, proxy_id: str) -> bool:
        return True

    def pool_exists(self, pool_id: str) -> bool:
        return True


class FakeDataStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.stage_error: Exception | None = None
        self.purge_error: Exception | None = None

    def stage(self, profile_id: str) -> str | None:
        self.calls.append(("stage", profile_id))
        if self.stage_error:
            raise self.stage_error
        return f"{profile_id}-staged"

    def restore(self, profile_id: str, token: str) -> None:
        self.calls.append(("restore", profile_id, token))

    def purge(self, token: str) -> None:
        self.calls.append(("purge", token))
        if self.purge_error:
            raise self.purge_error

    def retry_pending(self, profile_exists) -> None:
        self.calls.append(("retry_pending",))


class FakeUsageGuard:
    def __init__(self, busy: bool = False) -> None:
        self.busy = busy

    @contextmanager
    def guard(self, profile_id: str) -> Iterator[None]:
        if self.busy:
            raise ProfileDirectoryBusy
        yield


def _profile(valid_profile_values: dict[str, object]) -> Profile:
    now = datetime.now(UTC)
    return Profile("00000000-0000-0000-0000-000000000001", ProfileSpec.from_values(valid_profile_values), 12345, now, now)


def _service(
    repository: FakeRepository,
    data_store: FakeDataStore,
    *, fail_commit: bool = False,
) -> ProfileService:
    @contextmanager
    def transaction() -> Iterator[FakeRepository]:
        snapshot = list(repository.profiles)
        try:
            yield repository
            if fail_commit:
                raise RuntimeError("database unavailable: /private/database.sqlite3")
        except Exception:
            repository.profiles[:] = snapshot
            raise

    return ProfileService(transaction, FakeKernels(), FakeProxies(), FakeUsageGuard(), data_store)


def test_remove_rejects_active_profile_before_staging(valid_profile_values) -> None:
    profile = _profile(valid_profile_values)
    repository = FakeRepository([profile])
    data_store = FakeDataStore()
    service = _service(repository, data_store)
    service.profile_usage = FakeUsageGuard(busy=True)

    with pytest.raises(ProfileDirectoryBusy):
        service.remove(profile.id)

    assert repository.get(profile.id) == profile
    assert data_store.calls == []


def test_remove_keeps_database_when_directory_is_busy(valid_profile_values) -> None:
    profile = _profile(valid_profile_values)
    repository = FakeRepository([profile])
    data_store = FakeDataStore()
    data_store.stage_error = ProfileDirectoryBusy()

    with pytest.raises(ProfileDirectoryBusy):
        _service(repository, data_store).remove(profile.id)

    assert repository.get(profile.id) == profile


def test_remove_restores_directory_when_database_commit_fails(valid_profile_values) -> None:
    profile = _profile(valid_profile_values)
    repository = FakeRepository([profile])
    data_store = FakeDataStore()

    with pytest.raises(RuntimeError, match="database unavailable"):
        _service(repository, data_store, fail_commit=True).remove(profile.id)

    token = f"{profile.id}-staged"
    assert repository.get(profile.id) == profile
    assert data_store.calls == [("stage", profile.id), ("restore", profile.id, token)]


def test_remove_commits_when_post_commit_cleanup_fails(valid_profile_values) -> None:
    profile = _profile(valid_profile_values)
    repository = FakeRepository([profile])
    data_store = FakeDataStore()
    data_store.purge_error = OSError("private path")

    _service(repository, data_store).remove(profile.id)

    assert repository.get(profile.id) is None
    assert data_store.calls[-1][0] == "purge"


def test_regeneration_never_reuses_previous_seed(monkeypatch, valid_profile_values) -> None:
    profile = _profile(valid_profile_values)
    repository = FakeRepository([profile])
    values = iter([profile.fingerprint_seed - 10000, 7])
    monkeypatch.setattr("autoflow.application.profiles.service.secrets.randbelow", lambda _: next(values))

    regenerated = _service(repository, FakeDataStore()).regenerate(profile.id)

    assert regenerated.fingerprint_seed == 10007
    assert regenerated.spec == replace(profile.spec)
