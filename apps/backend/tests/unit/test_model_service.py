import asyncio
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from functools import partial

import pytest

from autoflow.application.models.service import ModelService
from autoflow.domain.credentials import CredentialStoreUnavailableError
from autoflow.domain.models.errors import ModelError
from autoflow.domain.models.models import LocalModelSpec, ProviderProfile
from autoflow.infrastructure.database.model_providers import (
    model_repository_transaction,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway


class FailingWriteStore(FakeCredentialStore):
    def write(self, key: str, value: bytes) -> None:
        raise CredentialStoreUnavailableError("locked")


class FailingDeleteStore(FakeCredentialStore):
    fail_delete = True

    def delete(self, key: str) -> None:
        if self.fail_delete:
            raise CredentialStoreUnavailableError("locked")
        super().delete(key)


class DelayedGateway(FakeModelGateway):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def discover(self, connection, secret):
        self.started.set()
        await self.release.wait()
        return await super().discover(connection, secret)


def _service(tmp_path, store=None):
    path = tmp_path / "service.db"
    migrate_database(path)
    factory = create_session_factory(path)
    return ModelService(
        partial(model_repository_transaction, factory),
        store or FakeCredentialStore(),
        FakeModelGateway(),
    ), factory


def _profile():
    return ProviderProfile.from_values(
        "Provider", "openai", "openai", None, None, True, ""
    )


class FailOnTransaction:
    def __init__(self, factory, fail_on: int):
        self.factory, self.fail_on, self.calls = factory, fail_on, 0

    @contextmanager
    def __call__(self):
        self.calls += 1
        if self.calls == self.fail_on:
            raise RuntimeError("injected sqlite commit boundary failure")
        with model_repository_transaction(self.factory) as repository:
            yield repository


class DeleteBeforeFinalTransaction:
    def __init__(self, factory, provider_id: str):
        self.factory, self.provider_id, self.calls = factory, provider_id, 0

    @contextmanager
    def __call__(self):
        self.calls += 1
        if self.calls == 2:
            with model_repository_transaction(self.factory) as repository:
                repository.remove_provider(self.provider_id)
        with model_repository_transaction(self.factory) as repository:
            yield repository


class ChangeBeforeFinalConnectionTransaction:
    def __init__(self, factory, provider_id: str):
        self.factory, self.provider_id, self.calls = factory, provider_id, 0

    @contextmanager
    def __call__(self):
        self.calls += 1
        if self.calls == 3:
            with model_repository_transaction(self.factory) as repository:
                current = repository.get_provider(self.provider_id)
                assert current is not None
                changed = replace(
                    current,
                    profile=replace(current.profile, name="Concurrent metadata"),
                    updated_at=current.updated_at + timedelta(seconds=1),
                )
                assert repository.update_provider(changed, current.updated_at)
        with model_repository_transaction(self.factory) as repository:
            yield repository


@pytest.mark.asyncio
async def test_credential_write_failure_keeps_cleanup_intent_and_no_provider(tmp_path):
    service, factory = _service(tmp_path, FailingWriteStore())
    with pytest.raises(ModelError) as captured:
        await service.connect(_profile(), "candidate-secret", [])
    assert captured.value.code == "CREDENTIAL_STORE_UNAVAILABLE"
    with model_repository_transaction(factory) as repository:
        assert repository.list_providers() == []
        refs = repository.list_cleanup()
    assert len(refs) == 1 and refs[0].startswith("model-provider/")


@pytest.mark.asyncio
async def test_connect_checks_final_discovery_membership_before_writes(tmp_path):
    store = FakeCredentialStore()
    service, factory = _service(tmp_path, store)
    with pytest.raises(ModelError) as captured:
        await service.connect(
            _profile(),
            "candidate-secret",
            [LocalModelSpec.from_values("missing", "Missing")],
        )
    assert captured.value.code == "MODEL_PROVIDER_MODEL_NOT_DISCOVERED"
    assert store.values == {}
    with model_repository_transaction(factory) as repository:
        assert repository.list_providers() == [] and repository.list_cleanup() == []


@pytest.mark.asyncio
async def test_final_sqlite_failure_leaves_written_candidate_recoverable(tmp_path):
    path = tmp_path / "commit-failure.db"
    migrate_database(path)
    factory = create_session_factory(path)
    store = FakeCredentialStore()
    transaction = FailOnTransaction(factory, fail_on=3)
    service = ModelService(transaction, store, FakeModelGateway())

    with pytest.raises(RuntimeError, match="commit boundary"):
        await service.connect(_profile(), "candidate-secret", [])

    with model_repository_transaction(factory) as repository:
        assert repository.list_providers() == []
        refs = repository.list_cleanup()
    assert len(refs) == 1
    assert store.values[refs[0]] == b"candidate-secret"


@pytest.mark.asyncio
async def test_late_provider_test_cannot_overwrite_newer_metadata(tmp_path):
    path = tmp_path / "cas.db"
    migrate_database(path)
    factory = create_session_factory(path)
    gateway = FakeModelGateway()
    store = FakeCredentialStore()
    service = ModelService(
        partial(model_repository_transaction, factory), store, gateway
    )
    optional = ProviderProfile.from_values(
        "Local",
        "ollama",
        "openai-compatible",
        "http://localhost:11434/v1",
        None,
        True,
        "",
    )
    provider = await service.connect(optional, "", [])
    delayed = DelayedGateway()
    delayed_service = ModelService(
        partial(model_repository_transaction, factory), store, delayed
    )
    pending = asyncio.create_task(delayed_service.test_provider(provider.id))
    await delayed.started.wait()
    service.update_metadata(provider.id, "Renamed", "newer", False)
    delayed.release.set()
    with pytest.raises(ModelError) as captured:
        await pending
    assert captured.value.code == "MODEL_PROVIDER_CHANGED"
    current = service.get_provider(provider.id)
    assert (current.name, current.enabled, current.connection_status) == (
        "Renamed",
        False,
        "connected",
    )


@pytest.mark.asyncio
async def test_connection_update_cas_failure_keeps_new_key_cleanup_intent(tmp_path):
    path = tmp_path / "connection-cas.db"
    migrate_database(path)
    factory = create_session_factory(path)
    store, gateway = FakeCredentialStore(), FakeModelGateway()
    normal = ModelService(
        partial(model_repository_transaction, factory), store, gateway
    )
    original = await normal.connect(_profile(), "old-secret", [])
    old_ref = original.secret_ref
    assert old_ref is not None
    racing = ModelService(
        ChangeBeforeFinalConnectionTransaction(factory, original.id), store, gateway
    )
    candidate = ProviderProfile.from_values(
        "Candidate",
        "openai",
        "openai",
        "https://candidate.test/v1",
        None,
        False,
        "candidate",
    )

    with pytest.raises(ModelError) as captured:
        await racing.update_connection(original.id, candidate, "new-secret")

    assert captured.value.code == "MODEL_PROVIDER_CHANGED"
    current = normal.get_provider(original.id)
    assert current.name == "Concurrent metadata"
    assert current.base_url == original.base_url
    assert current.secret_ref == old_ref
    assert store.values[old_ref] == b"old-secret"
    new_refs = set(store.values) - {old_ref}
    assert len(new_refs) == 1
    new_ref = new_refs.pop()
    assert store.values[new_ref] == b"new-secret"
    with model_repository_transaction(factory) as repository:
        assert repository.list_cleanup() == [new_ref]


@pytest.mark.asyncio
async def test_late_failed_provider_test_cannot_overwrite_newer_metadata(tmp_path):
    path = tmp_path / "failed-test-cas.db"
    migrate_database(path)
    factory = create_session_factory(path)
    store = FakeCredentialStore()
    normal = ModelService(
        partial(model_repository_transaction, factory), store, FakeModelGateway()
    )
    optional = ProviderProfile.from_values(
        "Local",
        "ollama",
        "openai-compatible",
        "http://localhost:11434/v1",
        None,
        True,
        "",
    )
    provider = await normal.connect(optional, "", [])
    delayed = DelayedGateway()
    delayed.fail = ModelError("MODEL_PROVIDER_RATE_LIMITED", "限流", 409)
    testing = ModelService(
        partial(model_repository_transaction, factory), store, delayed
    )
    pending = asyncio.create_task(testing.test_provider(provider.id))
    await delayed.started.wait()
    normal.update_metadata(provider.id, "New metadata", "newer", False)
    delayed.release.set()

    with pytest.raises(ModelError) as captured:
        await pending

    assert captured.value.code == "MODEL_PROVIDER_CHANGED"
    current = normal.get_provider(provider.id)
    assert (current.name, current.enabled, current.connection_status) == (
        "New metadata",
        False,
        "connected",
    )


@pytest.mark.asyncio
async def test_connection_validation_failure_preserves_old_config_and_secret(tmp_path):
    path = tmp_path / "connection-failure.db"
    migrate_database(path)
    factory = create_session_factory(path)
    store, gateway = FakeCredentialStore(), FakeModelGateway()
    service = ModelService(
        partial(model_repository_transaction, factory), store, gateway
    )
    provider = await service.connect(_profile(), "old-secret", [])
    before = service.get_provider(provider.id)
    gateway.fail = ModelError("MODEL_PROVIDER_AUTH_FAILED", "认证失败", 409)
    changed = ProviderProfile.from_values(
        "Changed", "openai", "openai", "https://other.test/v1", None, False, "new"
    )
    with pytest.raises(ModelError, match="认证失败"):
        await service.update_connection(provider.id, changed, "new-secret")
    after = service.get_provider(provider.id)
    assert after == before
    assert list(store.values.values()) == [b"old-secret"]


@pytest.mark.asyncio
async def test_delete_failure_is_recovered_and_live_refs_are_never_deleted(tmp_path):
    store = FailingDeleteStore()
    service, factory = _service(tmp_path, store)
    provider = await service.connect(_profile(), "secret", [])
    ref = provider.secret_ref
    assert ref is not None
    with model_repository_transaction(factory) as repository:
        repository.add_cleanup(ref)
    service.recover_credentials()
    assert ref in store.values
    with model_repository_transaction(factory) as repository:
        assert repository.list_cleanup() == [ref]
    service.delete_provider(provider.id)
    with model_repository_transaction(factory) as repository:
        assert repository.get_provider(provider.id) is None
        assert repository.list_cleanup() == [ref]
    store.fail_delete = False
    service.recover_credentials()
    assert ref not in store.values
    with model_repository_transaction(factory) as repository:
        assert repository.list_cleanup() == []


@pytest.mark.asyncio
async def test_replaced_credential_cleanup_failure_recovers_without_deleting_new_ref(
    tmp_path,
):
    store = FailingDeleteStore()
    service, factory = _service(tmp_path, store)
    original = await service.connect(_profile(), "old-secret", [])
    old_ref = original.secret_ref
    changed = ProviderProfile.from_values(
        "Provider", "openai", "openai", None, None, True, "changed"
    )
    updated = await service.update_connection(original.id, changed, "new-secret")
    assert (
        old_ref is not None
        and updated.secret_ref is not None
        and updated.secret_ref != old_ref
    )
    assert store.values[old_ref] == b"old-secret"
    assert store.values[updated.secret_ref] == b"new-secret"
    with model_repository_transaction(factory) as repository:
        assert repository.list_cleanup() == [old_ref]
    store.fail_delete = False
    service.recover_credentials()
    assert (
        old_ref not in store.values
        and store.values[updated.secret_ref] == b"new-secret"
    )


@pytest.mark.asyncio
async def test_provider_test_failure_persists_failed_but_discovery_does_not(tmp_path):
    path = tmp_path / "provider-test-failure.db"
    migrate_database(path)
    factory = create_session_factory(path)
    gateway = FakeModelGateway()
    service = ModelService(
        partial(model_repository_transaction, factory), FakeCredentialStore(), gateway
    )
    provider = await service.connect(_profile(), "secret", [])
    gateway.fail = ModelError("MODEL_PROVIDER_RATE_LIMITED", "限流", 409)
    with pytest.raises(ModelError):
        await service.discover(provider.id)
    assert service.get_provider(provider.id).connection_status == "connected"
    with pytest.raises(ModelError):
        await service.test_provider(provider.id)
    failed = service.get_provider(provider.id)
    assert failed.connection_status == "failed" and failed.last_check_latency_ms is None


@pytest.mark.asyncio
async def test_concurrent_provider_delete_maps_to_not_found(tmp_path):
    path = tmp_path / "delete-race.db"
    migrate_database(path)
    factory = create_session_factory(path)
    store, gateway = FakeCredentialStore(), FakeModelGateway()
    service = ModelService(
        partial(model_repository_transaction, factory), store, gateway
    )
    provider = await service.connect(_profile(), "secret", [])
    racing = ModelService(
        DeleteBeforeFinalTransaction(factory, provider.id), store, gateway
    )
    with pytest.raises(ModelError) as captured:
        racing.delete_provider(provider.id)
    assert captured.value.code == "MODEL_PROVIDER_NOT_FOUND"
