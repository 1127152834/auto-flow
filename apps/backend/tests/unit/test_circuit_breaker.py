"""Remediation M2 R2-15: when a batch pauses instead of burning through rows."""

from autoflow.domain.project_runs.circuit_breaker import FinishedTask, evaluate


def done(kind, code=None, task="t"):
    return FinishedTask(task, kind, code)


def many(count, kind, code=None):
    return [done(kind, code, f"{kind}-{index}") for index in range(count)]


def test_healthy_or_short_histories_do_not_pause():
    assert evaluate([]) is None
    assert evaluate(many(20, "succeeded")) is None
    assert evaluate(many(9, "page", "TIMEOUT")) is None  # too few to judge the rate, codes alternate below


def test_more_than_half_page_failures_in_the_last_twenty_pauses():
    history = many(9, "succeeded") + [done("page", f"C{index}", f"p{index}") for index in range(11)]
    reason = evaluate(history)
    assert reason is not None and reason.kind == "pageFailureRate"
    assert len(reason.sample_task_ids) == 5


def test_exactly_half_does_not_pause():
    history = many(10, "succeeded") + [done("page", f"C{index}", f"p{index}") for index in range(10)]
    assert evaluate(history) is None


def test_five_consecutive_infrastructure_failures_pause():
    reason = evaluate(many(3, "succeeded") + many(5, "infrastructure", "PROXY_UNAVAILABLE"))
    assert reason is not None and reason.kind == "infrastructureStreak"
    assert evaluate(many(4, "infrastructure", "X") + many(1, "succeeded")) is None


def test_ten_consecutive_same_technical_code_pause_and_success_breaks_the_streak():
    reason = evaluate(many(10, "page", "SELECTOR_MISSING"))
    assert reason is not None and reason.kind == "sameErrorStreak" and reason.code == "SELECTOR_MISSING"
    broken = many(5, "page", "A") + many(10, "succeeded") + many(5, "page", "A")  # 50%: rate not exceeded
    assert evaluate(broken) is None


def test_business_and_unknown_do_not_count_toward_technical_thresholds():
    history = many(9, "page", "A") + many(3, "business") + many(4, "unknown", "WORKFLOW_RESULT_UNKNOWN") + many(1, "page", "A")
    reason = evaluate(history)
    assert reason is not None and reason.kind == "sameErrorStreak"  # 10 page "A" with non-technical outcomes skipped
    assert evaluate(many(20, "business")) is None
    assert evaluate(many(20, "unknown", "X")) is None
