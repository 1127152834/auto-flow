from datetime import UTC, datetime

import pytest

from autoflow.domain.environments.models import (
    BindTarget,
    EnvironmentRef,
    PersistentEnvironment,
)
from autoflow.domain.environments.rules import (
    bind_targets,
    check_live_capacity,
    occupy_environment,
    resolve_environment_source,
    validate_end_phase,
    validate_manual_transition,
    validate_metadata,
    validate_open_instance,
    validate_save,
)
from autoflow.domain.projects.models import ProjectError

PROJECT = "11111111-1111-1111-1111-111111111111"
ENV = "22222222-2222-2222-2222-222222222222"
PROFILE = "33333333-3333-3333-3333-333333333333"
INPUT = "44444444-4444-4444-4444-444444444444"


def environment(**overrides) -> PersistentEnvironment:
    now = datetime(2026, 9, 17, tzinfo=UTC)
    values = {
        "ref": EnvironmentRef(PROJECT, ENV, 2, 1),
        "name": "账号登录",
        "notes": "",
        "state": "ready",
        "profile_id": PROFILE,
        "unavailable_reason": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return PersistentEnvironment(**values)


def test_metadata_trims_and_limits_name_and_notes():
    assert validate_metadata(name="  登录环境  ", notes="  备注  ") == {
        "name": "登录环境",
        "notes": "备注",
    }
    with pytest.raises(ProjectError) as error:
        validate_metadata(name="")
    assert error.value.status == 422


def test_new_from_profile_uses_project_default():
    resolved = resolve_environment_source(
        {"source": "newFromProfile"},
        project_id=PROJECT,
        project_default_profile_id=PROFILE,
    )
    assert resolved.environment_ref is None
    assert resolved.profile_id == PROFILE
    assert resolved.identity_package["source"] == "newFromProfile"


def test_fixed_and_input_sources_pin_current_generation():
    saved = {ENV: environment()}
    fixed = resolve_environment_source(
        {"source": "fixedEnvironment", "environmentId": ENV},
        project_id=PROJECT,
        project_default_profile_id=None,
        environments=saved,
    )
    assert fixed.environment_ref.content_generation == 2
    linked = resolve_environment_source(
        {"source": "inputEnvironment", "inputId": INPUT},
        project_id=PROJECT,
        project_default_profile_id=None,
        inputs={INPUT: {"currentEnvironmentId": ENV}},
        environments=saved,
    )
    assert linked.environment_ref.environment_id == ENV
    assert linked.identity_package == {}  # Missing historical identity must not be invented.


def test_two_linked_inputs_without_choice_are_ambiguous():
    other_input = "55555555-5555-5555-5555-555555555555"
    other_env = "66666666-6666-6666-6666-666666666666"
    with pytest.raises(ProjectError) as error:
        resolve_environment_source(
            {"source": "inputEnvironment"},
            project_id=PROJECT,
            project_default_profile_id=None,
            inputs={
                INPUT: {"currentEnvironmentId": ENV},
                other_input: {"currentEnvironmentId": other_env},
            },
            environments={
                ENV: environment(),
                other_env: environment(ref=EnvironmentRef(PROJECT, other_env, 1, 1)),
            },
        )
    assert error.value.code == "ENVIRONMENT_SOURCE_AMBIGUOUS"


def test_occupancy_is_exclusive_for_task_and_maintenance():
    held = occupy_environment(ENV, "instance-1", "task", "task-1", None)
    again = occupy_environment(ENV, "instance-1", "task", "task-1", held)
    assert again is held
    with pytest.raises(ProjectError) as error:
        occupy_environment(ENV, "instance-2", "maintenance", "op-1", held)
    assert error.value.status == 423


def test_save_rejects_stale_generation_and_busy_instance():
    source = EnvironmentRef(PROJECT, ENV, 3, 1)
    validate_save(
        mode="update",
        instance_state="closed",
        instance_use_generation=1,
        expected_use_generation=1,
        execution_generation=2,
        current_execution_generation=2,
        source=source,
        expected_content_generation=3,
    )
    with pytest.raises(ProjectError) as stale:
        validate_save(
            mode="update",
            instance_state="closed",
            instance_use_generation=1,
            expected_use_generation=1,
            execution_generation=1,
            current_execution_generation=2,
            source=source,
            expected_content_generation=3,
        )
    assert stale.value.code == "EXECUTION_GENERATION_REVOKED"
    with pytest.raises(ProjectError) as conflict:
        validate_save(
            mode="update",
            instance_state="closed",
            instance_use_generation=1,
            expected_use_generation=1,
            execution_generation=2,
            current_execution_generation=2,
            source=source,
            expected_content_generation=2,
        )
    assert conflict.value.code == "SAVE_GENERATION_CONFLICT"


def test_bind_same_environment_is_idempotent_and_replace_needs_authorization():
    record = {
        "projectId": PROJECT,
        "tableId": "66666666-6666-6666-6666-666666666666",
        "datasetGeneration": "77777777-7777-7777-7777-777777777777",
        "recordKey": {"type": "text", "value": "A-01"},
    }
    same = bind_targets(
        ENV,
        [BindTarget(record, 4, False, ENV, 4)],
    )
    assert same[0].changed is False
    assert same[0].link_revision == 4
    with pytest.raises(ProjectError) as error:
        bind_targets(
            ENV,
            [BindTarget(record, 4, False, "88888888-8888-8888-8888-888888888888", 4)],
        )
    assert error.value.status == 403
    replaced = bind_targets(
        ENV,
        [BindTarget(record, 4, True, "88888888-8888-8888-8888-888888888888", 4)],
    )
    assert replaced[0].changed is True
    assert replaced[0].link_revision == 5


def test_live_capacity_and_open_instance_are_distinct_from_busy():
    check_live_capacity(0, 1)
    with pytest.raises(ProjectError) as exhausted:
        check_live_capacity(1, 1)
    assert exhausted.value.code == "CAPACITY_EXHAUSTED"
    assert exhausted.value.status == 429
    assert exhausted.value.details["retryable"] is True
    validate_open_instance(
        instance_state="active",
        instance_use_generation=1,
        expected_use_generation=1,
    )
    with pytest.raises(ProjectError) as closed:
        validate_open_instance(
            instance_state="closed",
            instance_use_generation=1,
            expected_use_generation=1,
        )
    assert closed.value.code == "ENVIRONMENT_UNAVAILABLE"


def test_end_and_manual_transitions_have_one_winner():
    assert validate_end_phase("saving", "linking") == "linking"
    assert validate_end_phase("saving", "saved_unlinked") == "saved_unlinked"
    with pytest.raises(ProjectError):
        validate_end_phase("completed", "saving")
    assert validate_manual_transition("waiting", "resume_requested", resume_started=False) == "resume_requested"
    assert validate_manual_transition("resume_requested", "expired", resume_started=False) == "expired"
    with pytest.raises(ProjectError) as error:
        validate_manual_transition("resume_requested", "expired", resume_started=True)
    assert error.value.code == "MANUAL_TRANSITION_LOST"
    with pytest.raises(ProjectError) as resolved:
        validate_manual_transition("resolved", "expired", resume_started=True)
    assert resolved.value.code == "MANUAL_ALREADY_RESOLVED"
