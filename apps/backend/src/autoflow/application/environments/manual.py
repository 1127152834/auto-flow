from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from autoflow.application.environments.retention import _jsonable, end_task
from autoflow.domain.environments.rules import environment_error
from autoflow.domain.projects.models import ProjectError


def open_manual(service, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    service._writable(project_id)
    now = datetime.now(UTC)
    instance_id = payload.get("instanceId")
    if instance_id:
        instance = service.environments.get_instance(project_id, instance_id)
        service.environments.set_instance_state(instance.instance_id, "waiting_manual")
    expires = payload.get("expiresAt") or now + timedelta(minutes=30)
    item = service.environments.create_manual_item(
        {
            "manualItemId": str(uuid4()),
            "projectId": project_id,
            "taskId": payload["taskId"],
            "runId": payload["runId"],
            "instanceId": instance_id,
            "checkpointRevision": payload.get("checkpointRevision") or 1,
            "status": "waiting",
            "statusRevision": 1,
            "expiresAt": expires,
            "allowedTargets": payload.get("allowedTargets") or [],
            "resumeStarted": False,
            "reason": payload.get("reason") or "等待人工处理",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    return _jsonable(item)


def resume_manual(service, project_id: str, key: str, manual_item_id: str, payload: dict[str, Any]):
    service._writable(project_id)
    now = datetime.now(UTC)
    current = service.environments.get_manual_item(project_id, manual_item_id)
    _reject_expired(current, now)
    canonical = {
        "scope": "resumeManual",
        "projectId": project_id,
        "manualItemId": manual_item_id,
        "request": payload,
    }
    operation = service._command(
        key, "resumeManual", project_id, current.get("instanceId"), canonical, now
    )
    accepted, replayed = service.environments.accept_operation(operation)
    if replayed:
        return accepted.result, accepted, True
    try:
        item = service.environments.transition_manual(
            project_id,
            manual_item_id,
            "resume_requested",
            expected_status_revision=payload["expectedStatusRevision"],
            expected_checkpoint_revision=payload["checkpointRevision"],
        )
    except ProjectError as error:
        service.environments.complete_operation(
            accepted,
            None,
            {"code": error.code, "message": error.message, "details": error.details},
            datetime.now(UTC),
        )
        raise
    outcome = _jsonable({"item": item, "run": {"runId": item["runId"], "status": "resume_queued"}})
    done = service.environments.complete_operation(accepted, outcome, None, datetime.now(UTC))
    return outcome, done, False


def begin_resume(service, project_id: str, manual_item_id: str, expected_status_revision: int):
    """Mark resume as actually started. Isolated executor calls this as a simulated start."""
    item = service.environments.transition_manual(
        project_id,
        manual_item_id,
        "resolved",
        expected_status_revision=expected_status_revision,
        resume_started=True,
    )
    if item.get("instanceId"):
        service.environments.set_instance_state(item["instanceId"], "active")
    return _jsonable(item)


def finish_manual(service, project_id: str, key: str, manual_item_id: str, payload: dict[str, Any]):
    service._writable(project_id)
    now = datetime.now(UTC)
    current = service.environments.get_manual_item(project_id, manual_item_id)
    _reject_expired(current, now)
    canonical = {
        "scope": "finishManual",
        "projectId": project_id,
        "manualItemId": manual_item_id,
        "request": payload,
    }
    operation = service._command(
        key, "finishManual", project_id, current.get("instanceId"), canonical, now
    )
    accepted, replayed = service.environments.accept_operation(operation)
    if replayed:
        return accepted.result, accepted, True
    try:
        item = service.environments.transition_manual(
            project_id,
            manual_item_id,
            "resolved",
            expected_status_revision=payload["expectedStatusRevision"],
            expected_checkpoint_revision=payload["expectedCheckpointRevision"],
        )
    except ProjectError as error:
        service.environments.complete_operation(
            accepted,
            None,
            {"code": error.code, "message": error.message, "details": error.details},
            datetime.now(UTC),
        )
        raise
    retain = payload.get("retainEnvironment") or {"enabled": False}
    end_outcome = None
    if retain.get("enabled") and current.get("instanceId"):
        instance = service.environments.get_instance(project_id, current["instanceId"])
        end_outcome, _save, _replayed = end_task(
            service,
            project_id,
            str(uuid4()),
            {
                "taskId": current["taskId"],
                "runId": current["runId"],
                "instanceId": instance.instance_id,
                "expectedUseGeneration": instance.instance_use_generation,
                "executionGeneration": payload.get("executionGeneration") or 1,
                "retainEnvironment": retain,
            },
        )
    elif current.get("instanceId"):
        instance = service.environments.get_instance(project_id, current["instanceId"])
        service.close_instance(project_id, instance.instance_id, instance.environment_id)
    outcome = _jsonable(
        {
            "item": item,
            "run": {"runId": item["runId"], "status": payload.get("outcome") or "failed"},
            "end": end_outcome,
        }
    )
    done = service.environments.complete_operation(accepted, outcome, None, datetime.now(UTC))
    return outcome, done, False


def expire_manual(service, project_id: str, manual_item_id: str, expected_status_revision: int):
    item = service.environments.transition_manual(
        project_id,
        manual_item_id,
        "expired",
        expected_status_revision=expected_status_revision,
    )
    if item.get("instanceId") and not item.get("resumeStarted"):
        instance = service.environments.get_instance(project_id, item["instanceId"])
        service.close_instance(project_id, instance.instance_id, instance.environment_id)
    return _jsonable(item)


def cancel_manual(service, project_id: str, manual_item_id: str, expected_status_revision: int):
    item = service.environments.transition_manual(
        project_id,
        manual_item_id,
        "cancelled",
        expected_status_revision=expected_status_revision,
    )
    return _jsonable(item)


def _reject_expired(item: dict[str, Any], now: datetime) -> None:
    expires = item.get("expiresAt")
    if expires is None or item["status"] != "waiting":
        return
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    current = now if now.tzinfo else now.replace(tzinfo=UTC)
    if expires <= current:
        raise environment_error(
            "MANUAL_ALREADY_RESOLVED",
            "Manual item already has an authoritative result",
            409,
            {"domainCode": "manual_already_resolved", "status": "expired"},
        )
