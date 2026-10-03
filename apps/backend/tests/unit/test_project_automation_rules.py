import pytest

from autoflow.domain.project_automations.rules import validate_write
from autoflow.domain.projects.models import ProjectError


def payload():
    return {
        "name": " 自动化 α ",
        "description": "",
        "workflowId": "00000000-0000-0000-0000-000000000001",
        "inputPlan": {"inputs": []},
        "parameterSchema": [
            {
                "parameterId": "00000000-0000-0000-0000-000000000002",
                "name": "数量",
                "type": "number",
                "required": False,
                "defaultValue": 1,
            }
        ],
        "environmentPolicy": {"source": "newFromProfile"},
        "runPolicy": {
            "maxTasks": 1,
            "concurrency": 1,
            "maxLiveInstances": 1,
            "continueAfterFailure": False,
            "automaticExecutionTimeoutSeconds": 60,
            "manualDeadlineSeconds": 300,
        },
    }


def test_preserves_studio_nanoid_without_weakening_other_identity_validation():
    candidate = payload()
    candidate["workflowId"] = "V1StGXR8_Z5jdHi6B-myT"
    assert validate_write(candidate)["workflowId"] == candidate["workflowId"]
    candidate["parameterSchema"][0]["parameterId"] = candidate["workflowId"]
    with pytest.raises(ProjectError):
        validate_write(candidate)


@pytest.mark.parametrize("workflow_id", ["", "not-a-uuid", "../" + "a" * 18, "界" * 21, None, 123])
def test_rejects_invalid_workflow_identity(workflow_id):
    candidate = payload()
    candidate["workflowId"] = workflow_id
    with pytest.raises(ProjectError):
        validate_write(candidate)


def data_input(input_id: str, table_id: str, generation: str) -> dict:
    return {
        "inputId": input_id,
        "alias": input_id,
        "tableId": table_id,
        "datasetGeneration": generation,
        "mode": "independent",
        "required": True,
        "fieldBindings": [],
        "filter": {"type": "all", "items": []},
        "orderBy": [],
    }


def test_unicode_names_stable_ids_and_strict_parameter_values():
    value = validate_write(payload())
    assert value["name"] == "自动化 α"
    assert (
        value["parameterSchema"][0]["parameterId"]
        == payload()["parameterSchema"][0]["parameterId"]
    )
    for bad in ("1", True):
        candidate = payload()
        candidate["parameterSchema"][0]["defaultValue"] = bad
        with pytest.raises(ProjectError):
            validate_write(candidate)


def test_name_and_description_use_unicode_code_point_limits_after_trim():
    candidate = payload()
    candidate["name"] = f" {'界' * 80} "
    candidate["description"] = "说" * 1000
    assert len(validate_write(candidate)["name"]) == 80
    for field, value in (("name", "界" * 81), ("description", "说" * 1001)):
        candidate = payload()
        candidate[field] = value
        with pytest.raises(ProjectError):
            validate_write(candidate)


def test_run_policy_has_bounded_integer_limits():
    for field, value in (
        ("maxTasks", 101),
        ("maxTasks", True),
        ("concurrency", 101),
        ("concurrency", 0),
        ("concurrency", 1.5),
        ("maxLiveInstances", 101),
    ):
        candidate = payload()
        candidate["runPolicy"][field] = value
        with pytest.raises(ProjectError):
            validate_write(candidate)


def test_data_automation_accepts_bounded_concurrency_policy():
    candidate = payload()
    candidate["inputPlan"]["inputs"] = [
        data_input(
            "00000000-0000-0000-0000-000000000010",
            "00000000-0000-0000-0000-000000000011",
            "00000000-0000-0000-0000-000000000012",
        )
    ]
    candidate["runPolicy"].update({"concurrency": 4, "maxLiveInstances": 3})
    assert validate_write(candidate)["runPolicy"] == candidate["runPolicy"]
    candidate["runPolicy"]["concurrency"] = 101
    with pytest.raises(ProjectError):
        validate_write(candidate)


def test_run_timeouts_accept_finite_positive_fractional_seconds():
    candidate = payload()
    candidate["runPolicy"]["automaticExecutionTimeoutSeconds"] = 0.5
    candidate["runPolicy"]["manualDeadlineSeconds"] = 90.25
    assert validate_write(candidate)["runPolicy"] == candidate["runPolicy"]
    for invalid in (0, -0.5, True, float("inf"), float("nan")):
        candidate = payload()
        candidate["runPolicy"]["automaticExecutionTimeoutSeconds"] = invalid
        with pytest.raises(ProjectError):
            validate_write(candidate)


def test_omitted_null_and_empty_string_are_not_interchangeable():
    candidate = payload()
    del candidate["parameterSchema"][0]["defaultValue"]
    assert "defaultValue" not in validate_write(candidate)["parameterSchema"][0]
    candidate["parameterSchema"][0]["defaultValue"] = None
    assert validate_write(candidate)["parameterSchema"][0]["defaultValue"] is None
    candidate["parameterSchema"][0]["defaultValue"] = ""
    with pytest.raises(ProjectError):
        validate_write(candidate)


def test_parameter_description_is_trimmed_optional_and_names_are_exactly_unique():
    candidate = payload()
    candidate["parameterSchema"][0]["description"] = "  给运行者的说明  "
    assert (
        validate_write(candidate)["parameterSchema"][0]["description"]
        == "给运行者的说明"
    )
    del candidate["parameterSchema"][0]["description"]
    assert "description" not in validate_write(candidate)["parameterSchema"][0]
    candidate["parameterSchema"][0]["description"] = "说" * 1001
    with pytest.raises(ProjectError):
        validate_write(candidate)

    duplicate = payload()
    duplicate["parameterSchema"].append(
        {
            "parameterId": "00000000-0000-0000-0000-000000000003",
            "name": " 数量 ",
            "type": "string",
            "required": False,
        }
    )
    with pytest.raises(ProjectError) as error:
        validate_write(duplicate)
    assert "parameterSchema.1.name" in error.value.details["fields"]


def test_environment_model_provider_preserves_inherit_none_and_uuid_states():
    omitted = payload()
    assert "modelProviderId" not in validate_write(omitted)["environmentPolicy"]
    explicit_none = payload()
    explicit_none["environmentPolicy"]["modelProviderId"] = None
    assert validate_write(explicit_none)["environmentPolicy"]["modelProviderId"] is None
    selected = payload()
    selected["environmentPolicy"]["modelProviderId"] = (
        "00000000-0000-0000-0000-000000000004"
    )
    assert (
        validate_write(selected)["environmentPolicy"]["modelProviderId"]
        == selected["environmentPolicy"]["modelProviderId"]
    )
    selected["environmentPolicy"]["modelProviderId"] = "not-a-uuid"
    with pytest.raises(ProjectError):
        validate_write(selected)


def test_input_relation_graph_rejects_cycles_but_accepts_forward_dag_references():
    first_id = "00000000-0000-0000-0000-000000000011"
    second_id = "00000000-0000-0000-0000-000000000012"
    table_id = "00000000-0000-0000-0000-000000000013"
    generation = "00000000-0000-0000-0000-000000000014"

    forward = payload()
    first = data_input(first_id, table_id, generation)
    first.update(
        {
            "mode": "related",
            "relation": {"type": "sameRecord", "sourceInputId": second_id},
        }
    )
    forward["inputPlan"] = {
        "inputs": [first, data_input(second_id, table_id, generation)]
    }
    assert validate_write(forward)["inputPlan"] == forward["inputPlan"]

    cyclic = payload()
    second = data_input(second_id, table_id, generation)
    second.update(
        {
            "mode": "related",
            "relation": {"type": "sameRecord", "sourceInputId": first_id},
        }
    )
    cyclic["inputPlan"] = {"inputs": [first, second]}
    with pytest.raises(ProjectError) as error:
        validate_write(cyclic)
    assert error.value.details["fields"] == {
        "inputPlan.inputs": "Input dependencies contain a cycle"
    }


@pytest.mark.parametrize("limit", [1, 2, 100])
def test_parameter_automation_accepts_bounded_concurrency(limit):
    candidate = payload()
    candidate["runPolicy"].update(concurrency=limit, maxLiveInstances=limit)
    assert validate_write(candidate)["runPolicy"] == candidate["runPolicy"]


# Remediation M2 R2-01/§2: the primary processing input.
IN_A = "00000000-0000-0000-0000-0000000000a1"
IN_B = "00000000-0000-0000-0000-0000000000b1"
TABLE = "00000000-0000-0000-0000-0000000000c1"
GEN = "00000000-0000-0000-0000-0000000000d1"


def plan_with(*inputs, **extra):
    return {"inputs": list(inputs), **extra}


def test_processing_input_must_reference_a_required_input():
    candidate = payload()
    optional = data_input(IN_B, TABLE, GEN) | {"required": False}
    candidate["inputPlan"] = plan_with(data_input(IN_A, TABLE, GEN), optional, processingInputId=IN_A)
    assert validate_write(candidate)["inputPlan"]["processingInputId"] == IN_A
    for bad in (IN_B, "00000000-0000-0000-0000-0000000000ff", "", None):
        candidate = payload()
        candidate["inputPlan"] = plan_with(data_input(IN_A, TABLE, GEN), optional, processingInputId=bad)
        with pytest.raises(ProjectError):
            validate_write(candidate)


def test_parameter_only_automation_cannot_name_a_processing_input():
    candidate = payload()
    candidate["inputPlan"] = plan_with(processingInputId=IN_A)
    with pytest.raises(ProjectError):
        validate_write(candidate)


def test_processing_input_resolution():
    from autoflow.domain.project_automations.rules import AMBIGUOUS, processing_input

    one = data_input(IN_A, TABLE, GEN)
    two = data_input(IN_B, TABLE, GEN)
    assert processing_input(plan_with()) is None
    assert processing_input(plan_with(one)) == IN_A
    assert processing_input(plan_with(one, two | {"required": False})) == IN_A
    assert processing_input(plan_with(one, two)) is AMBIGUOUS
    assert processing_input(plan_with(one, two, processingInputId=IN_B)) == IN_B


@pytest.mark.parametrize(
    ("extra", "valid"),
    [
        ({}, True),
        ({"claimMode": "unprocessed"}, True), ({"claimMode": "cycle"}, True), ({"claimMode": "retryFailed"}, True),
        ({"claimMode": "all"}, False),
        ({"retryBudget": 1}, True), ({"retryBudget": 0}, False), ({"retryBudget": True}, False),
        ({"retryBackoffSeconds": [60, 300]}, True), ({"retryBackoffSeconds": []}, False),
        ({"retryBackoffSeconds": [0]}, False), ({"retryBackoffSeconds": [1.5]}, False),
    ],
)
def test_run_policy_accepts_explicit_claim_settings(extra, valid):
    candidate = payload()
    candidate["runPolicy"] = {**candidate["runPolicy"], **extra}
    if valid:
        assert validate_write(candidate)["runPolicy"] == candidate["runPolicy"]
    else:
        with pytest.raises(ProjectError):
            validate_write(candidate)
