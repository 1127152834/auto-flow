"""Remediation M4 S8-4 (R4-12): End of a perIdentity task holds the work copy instead of saving and closing it.

The worker still closes its browser before End (the protocol is unchanged), so the copy is quiet when it is
held. What the End asked for — save the login — is remembered and carried out once, at the identity's release.
A task that failed or was cancelled with a confirmed clean worker returns the copy to the identity too, so the
login changes of the tasks before it are not lost; anything less certain discards the copy without saving.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select

from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.environment_models import (
    ProjectEndOperationRow,
    ProjectEnvironmentInstanceRow,
    ProjectEnvironmentRow,
)
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.project_run_models import ProjectTaskRow
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.fixtures.workflow_runs import SyntheticResources
from tests.integration.test_project_capability_fencing import (
    capability_context as capability_context,  # noqa: PLC0414 -- pytest fixture
)
from tests.integration.test_project_end_recovery import _accept_end, _environments
from tests.integration.test_workflow_dispatch import SyntheticWorker, make_dispatcher


def _perIdentity_task(factory, project_id, task, environments, *, session_mode="perIdentity"):
    """An instance for the context's task, working as an identity, in a run that says perIdentity."""
    identity = SqlAlchemyIdentities(factory).create(project_id, "账号", template_profile_id=str(uuid4()))
    resolved = environments.resolve(project_id, {"source": "newFromProfile", "profileId": str(uuid4())})
    instance = environments.reserve(
        project_id, replace(resolved, identity={"identityId": identity.identity_id, "seed": identity.seed, "region": {}}),
        task_id=task.task_id, run_id=task.run_id, holder_kind="task", holder_id=task.task_id,
    )
    environments.environments.set_instance_state(instance.instance_id, "active")
    (environments.instance_path(instance.instance_id) / "login.txt").write_text("logged in", encoding="utf-8")
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.resource_request = {**dict(run.resource_request or {}), "sessionMode": session_mode}
    return identity, instance


def _instance(factory, instance_id):
    with factory() as session:
        return session.get(ProjectEnvironmentInstanceRow, instance_id)


def _saved_environments(factory, project_id):
    with factory() as session:
        return session.scalars(select(ProjectEnvironmentRow).where(ProjectEnvironmentRow.project_id == project_id)).all()


@pytest.mark.asyncio
@pytest.mark.parametrize("retain", [True, False])
async def test_a_perIdentity_end_holds_the_copy_and_remembers_whether_to_save(capability_context, tmp_path, retain):
    factory, project_id, task, *_rest = capability_context
    environments = _environments(factory, tmp_path / "environments")
    _identity, instance = _perIdentity_task(factory, project_id, task, environments)
    end = await _accept_end(factory, environments, task, retain_environment=retain)

    business, outcome, error = end.finalize(task.run_id)
    assert (business, outcome["phase"], outcome["complete"], error) == ("succeeded", "completed", True, None)
    held = _instance(factory, instance.instance_id)
    assert held.state == "identity_held" and held.active_run_id is None and held.retain_on_release is retain
    with factory() as session:
        batch_id = session.get(ProjectTaskRow, task.task_id).batch_id
        ledger = session.scalar(select(ProjectEndOperationRow).where(ProjectEndOperationRow.run_id == task.run_id))
    assert held.held_batch_id == batch_id
    assert ledger.phase == "completed" and ledger.targets == [], "an identity carries its own login; no record is linked"
    assert (environments.instance_path(instance.instance_id) / "login.txt").read_text(encoding="utf-8") == "logged in"
    assert _saved_environments(factory, project_id) == [], "nothing is saved until the identity is released"


@pytest.mark.asyncio
async def test_replaying_a_held_end_changes_nothing(capability_context, tmp_path):
    factory, project_id, task, *_rest = capability_context
    environments = _environments(factory, tmp_path / "environments")
    _identity, instance = _perIdentity_task(factory, project_id, task, environments)
    end = await _accept_end(factory, environments, task, retain_environment=True)
    first = end.finalize(task.run_id)
    again = end.finalize(task.run_id)
    assert again == first
    row = _instance(factory, instance.instance_id)
    assert row.state == "identity_held" and row.instance_use_generation == 1


@pytest.mark.asyncio
async def test_other_session_modes_keep_the_old_end(capability_context, tmp_path):
    factory, project_id, task, *_rest = capability_context
    environments = _environments(factory, tmp_path / "environments")
    _identity, instance = _perIdentity_task(factory, project_id, task, environments, session_mode="perTask")
    end = await _accept_end(factory, environments, task, retain_environment=False)
    end.finalize(task.run_id)
    assert _instance(factory, instance.instance_id).state == "cleaned"


# --- a run that ends without reaching End ---------------------------------------------------------------------


def _finish_run(factory, task, status):
    with factory.begin() as session:
        session.get(WorkflowRunRow, task.run_id).status = status


@pytest.mark.parametrize("status, returns_to_identity", [
    ("failed", True), ("cancelled", True),
    # The worker's clean-up is only inferred for these, so the copy is not trusted to be intact.
    ("timed_out", False), ("interrupted", False),
])
def test_only_a_failed_or_cancelled_run_gives_the_copy_back_to_its_identity(capability_context, tmp_path, status, returns_to_identity):
    factory, project_id, task, *_rest = capability_context
    environments = _environments(factory, tmp_path / "environments")
    _identity, instance = _perIdentity_task(factory, project_id, task, environments)
    _finish_run(factory, task, status)
    environments.cleanup_terminal_tasks()
    row = _instance(factory, instance.instance_id)
    if returns_to_identity:
        assert row.state == "identity_held" and row.active_run_id is None and not row.retain_on_release
        assert (environments.store.root / "instances" / instance.instance_id / "login.txt").exists()
    else:
        assert row.state == "cleaned" and not (environments.store.root / "instances" / instance.instance_id).exists()
    assert _saved_environments(factory, project_id) == []


def test_a_copy_that_cannot_be_confirmed_closed_waits_instead_of_being_given_back(capability_context, tmp_path):
    factory, project_id, task, *_rest = capability_context
    environments = _environments(factory, tmp_path / "environments")
    _identity, instance = _perIdentity_task(factory, project_id, task, environments)
    _finish_run(factory, task, "failed")

    def still_open(_service, _instance):
        raise ProjectError("INSTANCE_NOT_QUIESCENT", "浏览器仍占用目录", 409)

    environments._closer = still_open
    environments.cleanup_terminal_tasks()
    assert _instance(factory, instance.instance_id).state == "active", "retried on the next tick; the identity stays taken"
    environments._closer = lambda _service, _instance: None
    environments.cleanup_terminal_tasks()
    assert _instance(factory, instance.instance_id).state == "identity_held"


def test_the_scheduler_cleanup_gives_a_failed_run_s_copy_back_too(capability_context, tmp_path):
    factory, project_id, task, *_rest = capability_context
    environments = _environments(factory, tmp_path / "environments")
    _identity, instance = _perIdentity_task(factory, project_id, task, environments)
    _finish_run(factory, task, "failed")
    with factory() as session:
        batch_id = session.get(ProjectTaskRow, task.task_id).batch_id
    dispatcher = make_dispatcher(factory, SyntheticWorker(), SyntheticResources())
    scheduler = ProjectBatchScheduler(factory, dispatcher, QuiesceGate(), environments)
    asyncio.run(scheduler._cleanup_terminal_instances(project_id, batch_id))
    assert _instance(factory, instance.instance_id).state == "identity_held"
    assert not scheduler._environments.environments.disposable_task_instances()


def test_the_run_state_of_a_held_copy_never_makes_it_disposable(capability_context, tmp_path):
    factory, project_id, task, *_rest = capability_context
    environments = _environments(factory, tmp_path / "environments")
    _identity, instance = _perIdentity_task(factory, project_id, task, environments)
    _finish_run(factory, task, "failed")
    environments.cleanup_terminal_tasks()
    for _ in range(3):
        environments.cleanup_terminal_tasks()
    assert _instance(factory, instance.instance_id).state == "identity_held"
