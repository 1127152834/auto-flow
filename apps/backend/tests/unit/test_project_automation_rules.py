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


def test_pm3_run_policy_is_finite_and_single_concurrency():
    for field, value in (
        ("maxTasks", 101),
        ("maxTasks", True),
        ("concurrency", 2),
        ("maxLiveInstances", 2),
    ):
        candidate = payload()
        candidate["runPolicy"][field] = value
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
