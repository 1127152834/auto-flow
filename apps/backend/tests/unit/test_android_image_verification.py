from autoflow.domain.android.image_verification import summarize_verification


def test_no_observations_cannot_mean_passed() -> None:
    assert summarize_verification([]).status == "not_tested"


def test_failure_wins_over_blocked_and_passed() -> None:
    result = summarize_verification([
        {"checkId": "boot", "status": "passed"},
        {"checkId": "login", "status": "blocked", "reason": "无账号"},
        {"checkId": "download", "status": "failed", "reason": "安装失败"},
    ])
    assert result.status == "failed"


def test_missing_required_check_cannot_pass() -> None:
    result = summarize_verification([{"checkId": "boot", "status": "passed"}])
    assert result.status == "not_tested"
