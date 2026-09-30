"""Explicit fixture registration; a sibling integration module is not a plugin."""

from pathlib import Path

import pytest

from tests.integration.test_workflow_real_cloakbrowser import real_cloak_page

__all__ = ["real_cloak_page"]


@pytest.fixture(autouse=True)
def worker_imports_this_checkout(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2] / "src"))
