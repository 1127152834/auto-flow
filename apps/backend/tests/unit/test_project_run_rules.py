from datetime import UTC, datetime

import pytest

from autoflow.domain.project_automations.models import AutomationRecord
from autoflow.domain.project_runs.models import (
    Batch,
    BatchCounts,
    ProjectRunError,
    Task,
    TaskInputSnapshot,
    batch_to_dict,
)
from autoflow.domain.project_runs.rules import validate_batch_start
from autoflow.domain.workflows.runtime import create_core_run, transition_core_run

P_STRING = "00000000-0000-0000-0000-000000000001"
P_NUMBER = "00000000-0000-0000-0000-000000000002"
P_BOOL = "00000000-0000-0000-0000-000000000003"
P_OPTIONAL = "00000000-0000-0000-0000-000000000004"


def automation(*, inputs=None, revision=3, max_tasks=4):
    now = datetime(2026, 9, 15, tzinfo=UTC)
    return AutomationRecord(
        "automation-1",
        "project-1",
        "workflow-1",
        "自动化",
        "",
        revision,
        {"inputs": inputs or []},
        [
            {
                "parameterId": P_STRING,
                "name": "名称",
                "type": "string",
                "required": True,
            },
            {
                "parameterId": P_NUMBER,
                "name": "数量",
                "type": "number",
                "required": False,
                "defaultValue": 0,
            },
            {
                "parameterId": P_BOOL,
                "name": "启用",
                "type": "boolean",
                "required": False,
                "defaultValue": False,
            },
            {
                "parameterId": P_OPTIONAL,
                "name": "备注",
                "type": "string",
                "required": False,
            },
        ],
        {"source": "newFromProfile"},
        {"maxTasks": max_tasks, "concurrency": 1},
        now,
        now,
    )


def request(parameters=None, **extra):
    return {
        "expectedAutomationRevision": 3,
        "parameters": parameters or {P_STRING: "值"},
        **extra,
    }


def test_parameters_are_bound_by_stable_parameter_id_and_defaults_preserve_types():
    parsed = validate_batch_start(automation(), request())

    assert dict(parsed.parameters) == {P_STRING: "值", P_NUMBER: 0, P_BOOL: False}
    assert P_OPTIONAL not in parsed.parameters
    assert parsed.max_tasks == 4 and parsed.concurrency == 1


def test_explicit_null_false_and_zero_are_not_treated_as_missing():
    parsed = validate_batch_start(
        automation(),
        request({P_STRING: None, P_NUMBER: 0, P_BOOL: False, P_OPTIONAL: ""}),
    )

    assert dict(parsed.parameters) == {
        P_STRING: None,
        P_NUMBER: 0,
        P_BOOL: False,
        P_OPTIONAL: "",
    }


@pytest.mark.parametrize(
    ("parameter_id", "value"),
    [
        (P_STRING, 1),
        (P_NUMBER, True),
        (P_NUMBER, "1"),
        (P_NUMBER, 10**400),
        (P_BOOL, 0),
        (P_BOOL, "false"),
    ],
)
def test_parameter_values_never_coerce_scalar_types(parameter_id, value):
    with pytest.raises(ProjectRunError) as error:
        validate_batch_start(
            automation(), request({P_STRING: "值", parameter_id: value})
        )
    assert f"parameters.{parameter_id}" in error.value.details["fields"]


def test_unknown_and_missing_required_parameters_are_rejected_by_id():
    with pytest.raises(ProjectRunError) as unknown:
        validate_batch_start(automation(), request({P_STRING: "值", "unknown": 1}))
    assert "parameters.unknown" in unknown.value.details["fields"]
    with pytest.raises(ProjectRunError) as missing:
        validate_batch_start(automation(), request({P_NUMBER: 1}))
    assert f"parameters.{P_STRING}" in missing.value.details["fields"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maxTasks", 0),
        ("maxTasks", 101),
        ("maxTasks", True),
        ("concurrency", 2),
        ("concurrency", True),
    ],
)
def test_pm3_limits_are_strict(field, value):
    with pytest.raises(ProjectRunError) as error:
        validate_batch_start(automation(), request(**{field: value}))
    assert field in error.value.details["fields"]


def test_nonempty_project_inputs_are_rejected_even_when_optional():
    with pytest.raises(ProjectRunError) as error:
        validate_batch_start(
            automation(inputs=[{"inputId": "optional", "required": False}]), request()
        )
    assert "inputPlan.inputs" in error.value.details["fields"]


def test_revision_conflict_is_distinct_and_environment_override_is_frozen():
    override = {"source": "newFromProfile", "modelProviderId": None}
    parsed = validate_batch_start(automation(), request(environmentOverride=override))
    override["source"] = "changed"
    assert parsed.environment_override == {
        "source": "newFromProfile",
        "modelProviderId": None,
    }
    with pytest.raises(ProjectRunError) as error:
        validate_batch_start(automation(revision=4), request())
    assert error.value.code == "REVISION_CONFLICT" and error.value.status == 409
    assert error.value.details == {
        "expectedAutomationRevision": 3,
        "currentAutomationRevision": 4,
        "domainCode": "revision_conflict",
        "retryable": False,
    }
    with pytest.raises(ProjectRunError):
        validate_batch_start(
            automation(), request(environmentOverride={"source": "invented"})
        )


def test_start_accepts_fixed_environment_and_rejects_input_source_without_data():
    selected = automation()
    object.__setattr__(
        selected,
        "environment_policy",
        {
            "source": "fixedEnvironment",
            "environmentId": "00000000-0000-0000-0000-000000000010",
        },
    )
    started = validate_batch_start(selected, request())
    assert started.environment_override is None
    with pytest.raises(ProjectRunError) as error:
        validate_batch_start(
            automation(),
            request(
                environmentOverride={
                    "source": "inputEnvironment",
                    "inputId": "00000000-0000-0000-0000-000000000011",
                }
            ),
        )
    assert "environmentOverride.inputId" in error.value.details["fields"]


def test_environment_override_cannot_bypass_the_project_input_gate():
    with pytest.raises(ProjectRunError) as error:
        validate_batch_start(
            automation(inputs=[{"inputId": "input-1", "required": False}]),
            request(environmentOverride={"source": "newFromProfile"}),
        )
    assert error.value.details["fields"] == {
        "inputPlan.inputs": "当前仅支持参数型运行，请移除项目数据输入"
    }


def test_task_status_is_only_a_projection_of_its_matching_core_run():
    now = datetime(2026, 9, 15, tzinfo=UTC)
    task = Task(
        "task-1",
        "project-1",
        "batch-1",
        "run-1",
        "request-1",
        "snapshot-1",
        "queued",
        1,
        now,
    )
    run = create_core_run(
        run_id="run-1",
        run_request_id="request-1",
        request_digest="digest",
        prepared_content_id="prepared-1",
        parameters={},
        input_snapshot_ref=None,
        resource_request={"browser": "none"},
        capability_bindings=[],
        created_at=now,
    )
    running = transition_core_run(
        run,
        target_status="running",
        expected_status_revision=1,
        expected_execution_generation=0,
        now=now,
    )
    projected = task.project(running)
    assert projected.status == "running" and projected.status_revision == 2
    with pytest.raises(ProjectRunError):
        task.project(
            create_core_run(
                run_id="other",
                run_request_id="request-1",
                request_digest="digest",
                prepared_content_id="prepared-1",
                parameters={},
                input_snapshot_ref=None,
                resource_request={"browser": "none"},
                capability_bindings=[],
                created_at=now,
            )
        )


def test_batch_counts_project_tasks_without_inventing_batch_outcome():
    now = datetime(2026, 9, 15, tzinfo=UTC)
    batch = Batch(
        "batch-1",
        "project-1",
        "automation-1",
        "operation-1",
        "running",
        2,
        3,
        7,
        {"maxTasks": 3, "parameters": {P_BOOL: False}, "automation": {"name": "参数运行"}},
        BatchCounts({}),
        now,
    )
    tasks = [
        Task("t1", "project-1", "batch-1", "r1", "q1", "s1", "succeeded", 4, now, now),
        Task("t2", "project-1", "batch-1", "r2", "q2", "s2", "failed", 3, now, now),
        Task("t3", "project-1", "batch-1", "r3", "q3", "s3", "queued", 1, now),
    ]
    projected = batch.project_counts(tasks)
    view = batch_to_dict(projected)
    assert projected.status == "running"
    assert view["managementRevision"] == 3 and view["requestedCount"] == 3
    assert view["createdTaskCount"] == 3 and view["activeTaskCount"] == 1


def test_snapshot_freezes_parameters_and_pm4_data_inputs():
    now = datetime(2026, 9, 15, tzinfo=UTC)
    source = {P_BOOL: False, P_NUMBER: 0}
    snapshot = TaskInputSnapshot("snapshot-1", "task-1", "batch-1", source, (), now)
    source[P_NUMBER] = 9
    assert dict(snapshot.parameters) == {P_BOOL: False, P_NUMBER: 0}
    raw_inputs = ({"inputId": "i1", "values": [{"value": "one"}]},)
    data_snapshot = TaskInputSnapshot(
        "snapshot-2", "task-2", "batch-1", {}, raw_inputs, now
    )
    raw_inputs[0]["values"][0]["value"] = "changed"
    assert data_snapshot.inputs[0]["values"][0]["value"] == "one"


@pytest.mark.parametrize('required', [None, False, True])
def test_unlimited_start_requires_a_required_data_input(required):
    inputs = [] if required is None else [{'inputId': 'input', 'required': required}]
    selected = automation(inputs=inputs)
    if required is True:
        assert validate_batch_start(selected, request(maxTasks=None), allow_data_inputs=True).max_tasks is None
    else:
        with pytest.raises(ProjectRunError) as error:
            validate_batch_start(selected, request(maxTasks=None), allow_data_inputs=True)
        assert error.value.code == 'VALIDATION_ERROR'
        assert 'maxTasks' in error.value.details['fields']
