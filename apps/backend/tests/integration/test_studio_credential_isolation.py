from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from autoflow.application.workflows.credentials import StudioCredentialService
from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.studio_credentials import (
    SqlAlchemyStudioCredentials,
)
from tests.fixtures.model_management import FakeCredentialStore


@pytest.fixture
def workspaces(tmp_path):
    store = FakeCredentialStore()
    factories = []

    def create(name):
        path = tmp_path / name / "data.sqlite"
        migrate_database(path)
        factory = create_session_factory(path)
        factories.append(factory)
        metadata = SqlAlchemyStudioCredentials(factory)
        return StudioCredentialService(metadata, store), metadata, path

    yield create, store
    for factory in factories:
        factory.dispose()


def test_two_databases_never_share_same_named_secret(workspaces):
    create, _ = workspaces
    first, _, _ = create("a")
    second, _, _ = create("b")
    first.upsert("account", {"password": "workspace-a", "a": "only-a"}, None)
    second.upsert("account", {"password": "workspace-b"}, None)
    assert first.resolve("account") == {"password": "workspace-a", "a": "only-a"}
    assert second.resolve("account") == {"password": "workspace-b"}
    second.rename("account", "renamed")
    assert first.resolve("account")["password"] == "workspace-a"
    second.delete("renamed")
    assert first.resolve("account")["password"] == "workspace-a"


def test_identity_survives_service_restart_and_directory_move(workspaces):
    create, store = workspaces
    service, metadata, path = create("original")
    service.upsert("account", {"password": "retained"}, None)
    assert StudioCredentialService(metadata, store).resolve("account") == {"password": "retained"}
    # Close SQLite before physically moving the workspace.
    metadata._session_factory.dispose()
    moved = path.parent.with_name("moved")
    path.parent.rename(moved)
    factory = create_session_factory(moved / path.name)
    try:
        assert StudioCredentialService(SqlAlchemyStudioCredentials(factory), store).resolve("account") == {"password": "retained"}
    finally:
        factory.dispose()


def test_ambiguous_legacy_secret_requires_complete_reentry_and_is_never_deleted(workspaces):
    create, store = workspaces
    service, metadata, _ = create("legacy")
    metadata.upsert("account", "legacy", ["user", "password"], datetime.now(UTC))
    old_key = "studio-credential:" + hashlib.sha256(b"account").hexdigest()
    old_value = b'{"user":"unknown-owner","password":"do-not-read"}'
    store.write(old_key, old_value)
    with pytest.raises(WorkflowError, match="重新录入"):
        service.resolve("account")
    with pytest.raises(WorkflowError, match="重新录入"):
        service.upsert("account", {"password": "partial"}, None)
    service.upsert("account", {"user": "known-owner", "password": "new"}, None)
    assert service.resolve("account") == {"user": "known-owner", "password": "new"}
    service.delete("account")
    assert store.read(old_key) == old_value


def test_missing_scoped_secret_cannot_fall_back_to_legacy_key(workspaces):
    create, store = workspaces
    service, _, _ = create("a")
    service.upsert("account", {"password": "scoped"}, None)
    for key in list(store.values):
        store.delete(key)
    store.write("studio-credential:" + hashlib.sha256(b"account").hexdigest(), b'{"password":"foreign"}')
    with pytest.raises(WorkflowError, match="重新录入"):
        service.resolve("account")
