"""Remediation M4 S7 (R4-07; AC4-02): unhealthy identities wait; business failures count, successes clear."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from autoflow.application.project_runs.outcomes import _record_identity_health
from autoflow.application.projects.service import ProjectService
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.identity_models import IdentityRow
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import create_session_factory, migrate_database
from tests.integration.test_project_input_groups import _add_record, _empty_table, _input, uid


@pytest.fixture
def world(tmp_path):
    path = tmp_path / "health.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(uid(), {"name": "身份健康"})[0].project_id
    yield factory, project_id, SqlAlchemyIdentities(factory)
    factory.dispose()


def _link(factory, record, identity_id):
    ref = record["ref"]
    with factory() as session:
        row = session.get(DataRecordRow, (ref["datasetGeneration"], ref["recordKey"]["type"], ref["recordKey"]["value"]))
        row.current_identity_id = identity_id
        session.commit()


def _health(factory, identity_id, **health):
    with factory() as session:
        row = session.get(IdentityRow, identity_id)
        row.health = {**row.health, **health}
        session.commit()


@pytest.mark.parametrize("trouble", [{"banned": True}, {"consecutiveFailures": 3}])
def test_rows_of_an_unhealthy_identity_are_skipped_only_when_running_as_identities(world, trouble):
    factory, project_id, identities = world
    table, field = _empty_table(factory, project_id, "账号")
    sick, well = _add_record(factory, project_id, table, field, "a"), _add_record(factory, project_id, table, field, "b")
    sick_identity, well_identity = identities.create(project_id, "账号A"), identities.create(project_id, "账号B")
    _link(factory, sick, sick_identity.identity_id)
    _link(factory, well, well_identity.identity_id)
    _health(factory, sick_identity.identity_id, **trouble)
    plan = {"inputs": [_input(project_id, table, field, "账号")]}
    input_id = plan["inputs"][0]["inputId"]

    def chosen(**options):
        with factory() as session:
            result = SqlAlchemyProjectInputGroups(session).select_required(project_id, plan, **options)
        return {item.record_ref.record_key.value for item in result.inputs}

    keys = {sick["ref"]["recordKey"]["value"], well["ref"]["recordKey"]["value"]}
    assert chosen(identity_input_id=input_id) == {well["ref"]["recordKey"]["value"]}
    assert chosen() & keys  # an automation not running as identities is unaffected
    _health(factory, sick_identity.identity_id, banned=False, consecutiveFailures=0)  # "恢复正常"
    assert len(chosen(identity_input_id=input_id)) == 1


def test_business_failures_count_and_a_success_clears_them(world):
    factory, project_id, identities = world
    identity = identities.create(project_id, "账号C")
    run = SimpleNamespace(resource_request={"identity": {"identityId": identity.identity_id}})
    now = datetime.now(UTC)
    with factory() as session:
        for kind in ("business", "business", "page", "infrastructure"):
            _record_identity_health(session, run, kind, now)
        session.commit()
        assert session.get(IdentityRow, identity.identity_id).health["consecutiveFailures"] == 2
        _record_identity_health(session, run, "succeeded", now)
        session.commit()
        health = session.get(IdentityRow, identity.identity_id).health
    assert health["consecutiveFailures"] == 0 and health["lastLoginSuccessAt"] == now.isoformat()
