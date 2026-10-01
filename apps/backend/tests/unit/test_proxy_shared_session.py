"""Remediation M1 AC1-11: proxy management shares the application's session factory."""

import asyncio

import pytest
from fastapi import FastAPI

from autoflow.bootstrap import proxies
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "proxy.sqlite3"
    migrate_database(path)
    return path


def test_a_supplied_factory_is_used_and_never_disposed_by_the_proxy_module(database, monkeypatch):
    shared = create_session_factory(database)
    disposed = []
    monkeypatch.setattr(shared, "dispose", lambda: disposed.append("shared"), raising=False)

    def forbidden(_path):
        raise AssertionError("proxy management must not open a second engine")

    monkeypatch.setattr(proxies, "create_session_factory", forbidden)
    runtime = proxies.configure_proxy_management(FastAPI(), database, session_factory=shared)
    asyncio.run(runtime.close())
    assert disposed == []


def test_without_a_factory_the_module_owns_and_disposes_its_own(database, monkeypatch):
    created = []
    real = proxies.create_session_factory

    def tracked(path):
        factory = real(path)
        created.append(factory)
        monkeypatch.setattr(factory, "dispose", lambda: created.append("disposed"), raising=False)
        return factory

    monkeypatch.setattr(proxies, "create_session_factory", tracked)
    runtime = proxies.configure_proxy_management(FastAPI(), database)
    asyncio.run(runtime.close())
    assert "disposed" in created
