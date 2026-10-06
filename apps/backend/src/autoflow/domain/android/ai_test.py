from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from .ports import AndroidError

AiTestState = Literal["queued", "running", "succeeded", "failed", "cancelled", "needs_verification"]
AiTestMode = Literal["flash", "pro"]

TERMINAL_STATES: frozenset[AiTestState] = frozenset(["succeeded", "failed", "cancelled"])

# Allowed transitions: (from_state, to_state)
_VALID_TRANSITIONS = {
    ("queued", "running"),
    ("queued", "cancelled"),
    ("queued", "failed"),
    ("running", "succeeded"),
    ("running", "failed"),
    ("running", "cancelled"),
    ("running", "needs_verification"),
}


@dataclass(frozen=True)
class AiTestRequest:
    instruction: str
    mode: AiTestMode
    model_id: str
    max_steps: int
    timeout_seconds: int


def validate_request(raw: dict[str, Any]) -> AiTestRequest:
    """Validate and parse an AI test request from raw dict (camelCase keys)."""
    # Extract and validate instruction
    instruction_raw = raw.get("instruction")
    if not isinstance(instruction_raw, str):
        raise AndroidError(
            "AI_TEST_INSTRUCTION_INVALID",
            "指令必须是文本",
            422,
        )
    instruction = instruction_raw.strip()
    if not instruction or len(instruction) > 4000:
        raise AndroidError(
            "AI_TEST_INSTRUCTION_INVALID",
            "指令不能为空，且长度不能超过 4000 字符",
            422,
        )

    # Extract and validate model_id
    model_id_raw = raw.get("modelId")
    if not isinstance(model_id_raw, str) or not model_id_raw.strip():
        raise AndroidError(
            "AI_TEST_MODEL_REQUIRED",
            "必须指定运行的 AI 模型",
            422,
        )
    model_id = model_id_raw.strip()

    # Extract other fields
    mode = raw.get("mode")
    max_steps = raw.get("maxSteps")
    timeout_seconds = raw.get("timeoutSeconds")

    # Validate mode
    if mode not in ("flash", "pro"):
        raise AndroidError(
            "AI_TEST_MODE_INVALID",
            "运行模式必须是 flash 或 pro",
            422,
        )

    # Validate max_steps (must be int in range 1-200)
    if not isinstance(max_steps, int) or isinstance(max_steps, bool):
        raise AndroidError(
            "AI_TEST_STEPS_INVALID",
            "最大步数必须是 1 到 200 之间的整数",
            422,
        )
    if max_steps < 1 or max_steps > 200:
        raise AndroidError(
            "AI_TEST_STEPS_INVALID",
            "最大步数必须是 1 到 200 之间的整数",
            422,
        )

    # Validate timeout_seconds (must be int in range 30-3600)
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise AndroidError(
            "AI_TEST_TIMEOUT_INVALID",
            "超时时间必须是 30 到 3600 秒之间的整数",
            422,
        )
    if timeout_seconds < 30 or timeout_seconds > 3600:
        raise AndroidError(
            "AI_TEST_TIMEOUT_INVALID",
            "超时时间必须是 30 到 3600 秒之间的整数",
            422,
        )

    return AiTestRequest(
        instruction=instruction,
        mode=mode,
        model_id=model_id,
        max_steps=max_steps,
        timeout_seconds=timeout_seconds,
    )


def transition(current: AiTestState, target: AiTestState) -> AiTestState:
    """Validate and return a state transition."""
    if (current, target) not in _VALID_TRANSITIONS:
        raise AndroidError(
            "AI_TEST_STATE_CONFLICT",
            f"无法从 {current} 转移到 {target}",
            409,
        )
    return target


def redact(text: str, secrets: Iterable[str], max_lines: int = 50) -> str:
    """Take the tail max_lines and replace each secret with ***.

    Secrets are replaced longest-first to avoid substring leakage.
    """
    lines = text.splitlines()
    # Take the last max_lines
    tail_lines = lines[-max_lines:] if len(lines) > max_lines else lines

    result = "\n".join(tail_lines)

    # Replace each secret longest-first (skip empty strings)
    # Sort by length descending to replace longer secrets first
    non_empty_secrets = [s for s in secrets if s]
    sorted_secrets = sorted(non_empty_secrets, key=len, reverse=True)
    for secret in sorted_secrets:
        result = result.replace(secret, "***")

    return result
