"""Two real SQLite stores and one unique temporary native Keychain entry.

Never reads or changes an existing named user credential. Output is booleans only.
"""
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from autoflow.application.workflows.credentials import StudioCredentialService
from autoflow.infrastructure.credentials.system import SystemCredentialStore
from autoflow.infrastructure.database.session import create_session_factory, migrate_database
from autoflow.infrastructure.database.studio_credentials import SqlAlchemyStudioCredentials


def main():
    store = SystemCredentialStore()
    name = "AutoFlow-QA-isolation-" + uuid4().hex
    key = StudioCredentialService._key(name)
    assert store.read(key) is None, "Unexpected UUID collision; do not alter existing entry"
    factories = []
    try:
        with tempfile.TemporaryDirectory(prefix="autoflow-security-credentials-") as directory:
            services = []
            for workspace in ("workspace-a", "workspace-b"):
                database = Path(directory) / workspace / "autoflow.sqlite"
                migrate_database(database)
                factory = create_session_factory(database)
                factories.append(factory)
                services.append(StudioCredentialService(SqlAlchemyStudioCredentials(factory), store))
            first, second = services
            first_value = uuid4().hex
            second_value = uuid4().hex
            first.upsert(name, {"password": first_value}, "QA isolation A")
            second_empty_before = second.list_items() == []
            second.upsert(name, {"password": second_value}, "QA isolation B")
            first_was_overwritten = first.resolve(name)["password"] == second_value
            second.delete(name)
            first_metadata_remains = any(item["name"] == name for item in first.list_items())
            first_secret_missing = first.resolve(name) == {}
            report = {
                "native_keychain": True,
                "real_independent_sqlite_databases": True,
                "workspace_b_initial_metadata_empty": second_empty_before,
                "workspace_a_secret_overwritten_by_workspace_b": first_was_overwritten,
                "workspace_a_metadata_remains_after_b_delete": first_metadata_remains,
                "workspace_a_secret_missing_after_b_delete": first_secret_missing,
            }
            assert all(report.values())
    finally:
        for factory in factories:
            factory.dispose()
        store.delete(key)
    report["unique_test_key_removed"] = store.read(key) is None
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
