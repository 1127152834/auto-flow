from datetime import UTC, datetime
from uuid import uuid4

import pytest

from autoflow.domain.workflows.runtime import (
    WorkflowRuntimeError,
    create_run_artifact,
)

NOW = datetime(2026, 9, 15, tzinfo=UTC)


def artifact(**overrides):
    run_id = overrides.pop("run_id", str(uuid4()))
    generation = overrides.pop("execution_generation", 2)
    return create_run_artifact(
        artifact_id=overrides.pop("artifact_id", str(uuid4())),
        run_id=run_id,
        ordinal=overrides.pop("ordinal", 1),
        node_id=overrides.pop("node_id", "open"),
        node_visit_id=overrides.pop("node_visit_id", "visit-1"),
        purpose="error",
        event_sequence=overrides.pop("event_sequence", 4),
        execution_generation=generation,
        kind="screenshot",
        availability=overrides.pop("availability", "available"),
        relative_path=overrides.pop(
            "relative_path",
            f"runs/{run_id}/generation-{generation}/failure.png",
        ),
        media_type=overrides.pop("media_type", "image/png"),
        byte_size=overrides.pop("byte_size", 3),
        sha256=overrides.pop("sha256", "a" * 64),
        created_at=NOW,
        unavailable_reason=overrides.pop("unavailable_reason", None),
        **overrides,
    )


def test_available_artifact_keeps_only_controlled_relative_file_metadata() -> None:
    value = artifact()

    assert value.relative_path.startswith("runs/")
    assert value.media_type == "image/png"
    assert value.byte_size == 3
    assert value.sha256 == "a" * 64


@pytest.mark.parametrize(
    "relative_path",
    [
        "../secret.png",
        "/tmp/secret.png",
        "runs/id/../../secret.png",
        "runs\\secret.png",
        "runs/run/generation-2/artifacts//capture.png",
        "runs/run/generation-2/artifacts/./capture.png",
    ],
)
def test_available_artifact_rejects_directory_escape(relative_path: str) -> None:
    with pytest.raises(WorkflowRuntimeError) as caught:
        artifact(relative_path=relative_path)

    assert caught.value.code == "RUN_ARTIFACT_INVALID"


def test_unavailable_artifact_has_no_file_claim() -> None:
    value = artifact(
        availability="unavailable",
        relative_path=None,
        media_type=None,
        byte_size=None,
        sha256=None,
        unavailable_reason="SCREENSHOT_CAPTURE_FAILED",
    )

    assert value.relative_path is None
    assert value.unavailable_reason == "SCREENSHOT_CAPTURE_FAILED"
