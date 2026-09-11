from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from autoflow.application.proxies.facade import ProxyApplication
from autoflow.domain.proxies.models import (
    Connection,
    ProviderPage,
    unavailable_capabilities,
)


class MemoryCredentials:
    def __init__(self):
        self.values = {"old-ref": b"old-key"}

    def read(self, key):
        return self.values.get(key)

    def write(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


class VerifiedProvider:
    async def verify(self, api_key):
        return ProviderPage((), "unknown")

    async def list_proxies(self, api_key):
        return ProviderPage((), "unknown")


class FailingUnitOfWork:
    def __init__(self, repository):
        self.repository = repository

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self):
        raise RuntimeError("database commit failed")

    def rollback(self):
        pass


@pytest.mark.asyncio
async def test_api_key_replacement_commit_failure_keeps_old_secret_and_cleans_new_secret():
    now = datetime.now(UTC)
    connection = Connection(
        id="connection-1",
        name="Main",
        secret_ref="old-ref",
        status="connected",
        revision=0,
        generation=0,
        sync_token=None,
        sync_started_at=None,
        last_verified_at=now,
        last_synced_at=None,
        last_error=None,
        capabilities=unavailable_capabilities(),
        created_at=now,
        updated_at=now,
    )
    repository = Mock()
    repository.get_connection.return_value = connection
    credentials = MemoryCredentials()
    application = ProxyApplication(
        lambda: FailingUnitOfWork(repository), credentials, VerifiedProvider()  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await application.replace_api_key(connection.id, 0, "new-key")

    assert credentials.values == {"old-ref": b"old-key"}
