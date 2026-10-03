"""Remediation M2 R2-10/R2-13: side-effect declarations and failure categories."""

import pytest

from autoflow.domain.project_runs.failure_category import AttemptFact, classify
from autoflow.domain.workflows.side_effects import node_side_effect


@pytest.mark.parametrize(
    "module_type",
    ["open_page", "get_element_info", "wait_element", "string_concat", "set_variable", "condition", "loop",
     "subflow", "screenshot", "extract_table_data", "firecrawl_scrape", "print_log", "wait"],
)
def test_read_only_and_control_nodes_have_no_side_effect(module_type):
    assert node_side_effect(module_type, {}) == "none"


@pytest.mark.parametrize(
    "module_type",
    ["click_element", "input_text", "press_key", "select_dropdown", "api_request", "send_email",
     "js_script", "run_command", "refresh_page", "handle_dialog", "project_end", "project_manual",
     "ssh_execute_command", "notify_webhook", "never_heard_of_this"],
)
def test_acting_and_unknown_nodes_may_have_side_effects(module_type):
    assert node_side_effect(module_type, {}) == "possible"


@pytest.mark.parametrize(
    ("operation", "expected"),
    [("inputs", "none"), ("readRecord", "none"), ("queryRecords", "none"), ("queryTableSchema", "none"),
     ("updateRecord", "possible"), ("createRecord", "possible"), ("setRecordStatus", "possible"),
     ("deleteRecord", "possible"), (None, "possible")],
)
def test_project_data_depends_on_the_operation(operation, expected):
    config = {} if operation is None else {"operation": operation}
    assert node_side_effect("project_data", config) == expected


def started(visit, effect="none"):
    return AttemptFact(visit, "started", effect)


def finished(visit, status="succeeded", effect="none"):
    return AttemptFact(visit, status, effect)


UNKNOWN = {"code": "WORKFLOW_RESULT_UNKNOWN"}


def test_success_has_no_category():
    assert classify("succeeded", None, [started("a"), finished("a")]) is None


@pytest.mark.parametrize("status", ["failed", "timed_out", "interrupted", "cancelled"])
def test_nothing_started_is_infrastructure(status):
    assert classify(status, {"code": "BROWSER_START_FAILED"}, []) == "infrastructure"


def test_read_only_failure_is_page():
    facts = [started("a"), finished("a"), started("b"), finished("b", "failed")]
    assert classify("failed", {"code": "WORKFLOW_NODE_TIMEOUT"}, facts) == "page"
    assert classify("timed_out", None, facts) == "page"


@pytest.mark.parametrize("status", ["failed", "timed_out", "interrupted"])
def test_any_started_side_effect_makes_a_failure_unknown(status):
    facts = [started("a"), finished("a"), started("click", "possible"), finished("click", "succeeded", "possible"),
             started("read"), finished("read", "failed")]
    assert classify(status, UNKNOWN if status == "interrupted" else None, facts) == "unknown"


def test_unknown_result_after_only_reads_is_page():
    assert classify("interrupted", UNKNOWN, [started("a"), finished("a"), started("b")]) == "page"


def test_cancel_with_a_side_effect_in_flight_is_unknown():
    assert classify("cancelled", None, [started("a"), finished("a"), started("click", "possible")]) == "unknown"


def test_cancel_after_completed_side_effects_stays_cancelled():
    facts = [started("click", "possible"), finished("click", "succeeded", "possible"), started("read")]
    assert classify("cancelled", None, facts) == "cancelled"


def test_events_without_a_declaration_count_as_possible():
    assert classify("failed", None, [AttemptFact("old", "started", None)]) == "unknown"
