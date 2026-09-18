"""Production wiring for environment ownership and run execution generation."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway


class _Instance:
    def __init__(self, run_id: str | None) -> None:
        self.active_run_id = run_id


def test_application_owns_environment_browsers_and_reads_run_generations(tmp_path: Path):
    app = create_app(
        Settings(data_dir=str(tmp_path), instance_id="pm5-wiring"),
        credential_store=FakeCredentialStore(),
        model_gateway=FakeModelGateway(),
    )
    with TestClient(app):
        service = app.state.environment_service
        assert app.state.environment_browser is app.state.environment_service._opener.__self__
        assert callable(service._opener)
        assert callable(service._closer)
        assert callable(service._execution_generation_lookup)
        assert service.execution_generation_of(_Instance("unknown-run")) is None
