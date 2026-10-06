from __future__ import annotations

from typing import Any

import pytest

from autoflow.domain.android.ai_test import (
    TERMINAL_STATES,
    redact,
    transition,
    validate_request,
)
from autoflow.domain.android.ports import AndroidError


def ok(**overrides: Any) -> dict[str, Any]:
    """Test helper: returns a valid AI test request dict with defaults."""
    defaults = {
        "instruction": "打开设置",
        "mode": "flash",
        "modelId": "m1",
        "maxSteps": 30,
        "timeoutSeconds": 600,
    }
    defaults.update(overrides)
    return defaults


def test_instruction_trimmed_and_bounded() -> None:
    assert validate_request(ok(instruction="  打开设置  ")).instruction == "打开设置"
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(instruction="   "))
    assert excinfo.value.code == "AI_TEST_INSTRUCTION_INVALID"
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(instruction="a" * 4001))
    assert excinfo.value.code == "AI_TEST_INSTRUCTION_INVALID"


@pytest.mark.parametrize("steps,valid", [(0, False), (1, True), (200, True), (201, False)])
def test_max_steps_bounds(steps: int, valid: bool) -> None:
    if valid:
        result = validate_request(ok(maxSteps=steps))
        assert result.max_steps == steps
    else:
        with pytest.raises(AndroidError) as excinfo:
            validate_request(ok(maxSteps=steps))
        assert excinfo.value.code == "AI_TEST_STEPS_INVALID"


@pytest.mark.parametrize("seconds,valid", [(29, False), (30, True), (3600, True), (3601, False)])
def test_timeout_bounds(seconds: int, valid: bool) -> None:
    if valid:
        result = validate_request(ok(timeoutSeconds=seconds))
        assert result.timeout_seconds == seconds
    else:
        with pytest.raises(AndroidError) as excinfo:
            validate_request(ok(timeoutSeconds=seconds))
        assert excinfo.value.code == "AI_TEST_TIMEOUT_INVALID"


def test_transitions() -> None:
    assert transition("queued", "running") == "running"
    assert transition("running", "needs_verification") == "needs_verification"
    for terminal in TERMINAL_STATES:
        with pytest.raises(AndroidError) as excinfo:
            transition(terminal, "running")
        assert excinfo.value.code == "AI_TEST_STATE_CONFLICT"


def test_redact_tail_and_secret() -> None:
    text = "\n".join(f"line{i}" for i in range(60)) + "\nkey=sk-123"
    out = redact(text, ["sk-123", ""])
    assert "sk-123" not in out
    assert "***" in out
    assert "line0" not in out
    assert len(out.splitlines()) == 50


def test_mode_validation() -> None:
    # Valid modes
    validate_request(ok(mode="flash"))
    validate_request(ok(mode="pro"))
    # Invalid mode
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(mode="invalid"))
    assert excinfo.value.code == "AI_TEST_MODE_INVALID"


def test_model_id_required() -> None:
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(modelId=""))
    assert excinfo.value.code == "AI_TEST_MODEL_REQUIRED"
    with pytest.raises(AndroidError) as excinfo:
        request_dict = ok()
        del request_dict["modelId"]
        validate_request(request_dict)
    assert excinfo.value.code == "AI_TEST_MODEL_REQUIRED"


def test_max_steps_must_be_int() -> None:
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(maxSteps="30"))
    assert excinfo.value.code == "AI_TEST_STEPS_INVALID"
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(maxSteps=30.5))
    assert excinfo.value.code == "AI_TEST_STEPS_INVALID"


def test_timeout_seconds_must_be_int() -> None:
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(timeoutSeconds="600"))
    assert excinfo.value.code == "AI_TEST_TIMEOUT_INVALID"
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(timeoutSeconds=600.5))
    assert excinfo.value.code == "AI_TEST_TIMEOUT_INVALID"


def test_terminal_states() -> None:
    assert "succeeded" in TERMINAL_STATES
    assert "failed" in TERMINAL_STATES
    assert "cancelled" in TERMINAL_STATES
    assert "running" not in TERMINAL_STATES
    assert "queued" not in TERMINAL_STATES


def test_valid_transitions_from_queued() -> None:
    assert transition("queued", "running") == "running"
    assert transition("queued", "cancelled") == "cancelled"
    assert transition("queued", "failed") == "failed"
    with pytest.raises(AndroidError):
        transition("queued", "succeeded")
    with pytest.raises(AndroidError):
        transition("queued", "needs_verification")


def test_valid_transitions_from_running() -> None:
    assert transition("running", "succeeded") == "succeeded"
    assert transition("running", "failed") == "failed"
    assert transition("running", "cancelled") == "cancelled"
    assert transition("running", "needs_verification") == "needs_verification"
    with pytest.raises(AndroidError):
        transition("running", "queued")


def test_invalid_transitions_from_terminal_states() -> None:
    for state in TERMINAL_STATES:
        for target in ["queued", "running"]:
            with pytest.raises(AndroidError) as excinfo:
                transition(state, target)
            assert excinfo.value.code == "AI_TEST_STATE_CONFLICT"


def test_ai_test_request_is_frozen() -> None:
    req = validate_request(ok())
    with pytest.raises(AttributeError):
        req.instruction = "新指令"


def test_redact_with_empty_secrets_list() -> None:
    text = "line1\nline2\nkey=secret"
    out = redact(text, [])
    assert out == text


def test_redact_custom_max_lines() -> None:
    text = "\n".join(f"line{i}" for i in range(100))
    out = redact(text, [], max_lines=10)
    assert len(out.splitlines()) == 10
    assert "line90" in out
    assert "line0" not in out


def test_instruction_must_be_string() -> None:
    """null instruction raises AI_TEST_INSTRUCTION_INVALID, not AttributeError."""
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(instruction=None))
    assert excinfo.value.code == "AI_TEST_INSTRUCTION_INVALID"

    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(instruction=123))
    assert excinfo.value.code == "AI_TEST_INSTRUCTION_INVALID"


def test_model_id_must_be_string() -> None:
    """null modelId raises AI_TEST_MODEL_REQUIRED, not AttributeError."""
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(modelId=None))
    assert excinfo.value.code == "AI_TEST_MODEL_REQUIRED"

    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(modelId=123))
    assert excinfo.value.code == "AI_TEST_MODEL_REQUIRED"


def test_bool_max_steps_rejected() -> None:
    """bool maxSteps raises AI_TEST_STEPS_INVALID."""
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(maxSteps=True))
    assert excinfo.value.code == "AI_TEST_STEPS_INVALID"

    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(maxSteps=False))
    assert excinfo.value.code == "AI_TEST_STEPS_INVALID"


def test_bool_timeout_rejected() -> None:
    """bool timeoutSeconds raises AI_TEST_TIMEOUT_INVALID."""
    with pytest.raises(AndroidError) as excinfo:
        validate_request(ok(timeoutSeconds=True))
    assert excinfo.value.code == "AI_TEST_TIMEOUT_INVALID"


def test_redact_longest_secret_first() -> None:
    """Substring secrets are replaced longest-first to avoid leakage."""
    # If we replace "abc" before "abcdef", we'd get "***def"
    text = "abcdef is secret"
    out = redact(text, ["abc", "abcdef"])
    assert "abcdef" not in out
    assert "abc" not in out
    assert "def" not in out  # No substring leakage
    assert out == "*** is secret"
