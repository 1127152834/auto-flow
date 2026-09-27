"""Native-store acceptance. Only accesses freshly generated UUID test names."""
from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from autoflow.application.workflows.credentials import StudioCredentialService
from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.credentials.system import SystemCredentialStore
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.studio_credentials import (
    SqlAlchemyStudioCredentials,
)


def main():
    store = SystemCredentialStore()
    name, renamed = "AutoFlow-QA-" + uuid4().hex, "AutoFlow-QA-" + uuid4().hex
    legacy_name = "AutoFlow-QA-legacy-" + uuid4().hex
    legacy_key = "studio-credential:" + hashlib.sha256(legacy_name.encode()).hexdigest()
    owned, factories, checks = set(), [], {}
    try:
        with tempfile.TemporaryDirectory(prefix="autoflow-credential-fix-") as directory:
            services, metadata = [], []
            for workspace in ("a", "b"):
                database = Path(directory) / workspace / "data.sqlite"
                migrate_database(database)
                factory = create_session_factory(database)
                factories.append(factory)
                repository = SqlAlchemyStudioCredentials(factory)
                service = StudioCredentialService(repository, store)
                services.append(service)
                metadata.append(repository)
                for item in (name, renamed, legacy_name):
                    key = service._key(item)
                    assert store.read(key) is None, "UUID collision; existing entry untouched"
                    owned.add(key)
            assert store.read(legacy_key) is None, "UUID collision; existing entry untouched"
            owned.add(legacy_key)
            first, second = services
            a, b = uuid4().hex, uuid4().hex
            first.upsert(name, {"password": a, "owner": "a"}, None)
            second.upsert(name, {"password": b}, None)
            checks["distinct_keys"] = first._key(name) != second._key(name)
            checks["same_name_isolation"] = first.resolve(name) == {"password": a, "owner": "a"} and second.resolve(name) == {"password": b}
            second.rename(name, renamed)
            checks["rename_isolation"] = first.resolve(name)["password"] == a and second.resolve(renamed)["password"] == b
            second.delete(renamed)
            checks["delete_isolation"] = first.resolve(name)["password"] == a
            checks["restart_persistence"] = StudioCredentialService(metadata[0], store).resolve(name)["password"] == a
            metadata[0].upsert(legacy_name, "QA legacy", ["password"], datetime.now(UTC))
            legacy = json.dumps({"password": uuid4().hex}).encode()
            store.write(legacy_key, legacy)
            try:
                first.resolve(legacy_name)
            except WorkflowError as error:
                checks["legacy_reentry_required"] = error.code == "CREDENTIAL_REENTRY_REQUIRED"
            else:
                checks["legacy_reentry_required"] = False
            first.upsert(legacy_name, {"password": a}, None)
            checks["explicit_reentry_restores"] = first.resolve(legacy_name) == {"password": a}
            first.delete(legacy_name)
            checks["legacy_preserved"] = store.read(legacy_key) == legacy
            first.delete(name)
    finally:
        for factory in factories:
            factory.dispose()
        for key in owned:
            store.delete(key)
        checks["owned_entries_removed"] = all(store.read(key) is None for key in owned)
    print(json.dumps({"native_store": True, "real_sqlite": True, "checks": checks}, indent=2))
    assert len(checks) == 9 and all(checks.values())


if __name__ == "__main__":
    main()
