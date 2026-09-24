from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

_SAVE_NAMESPACE = uuid5(NAMESPACE_URL, "autoflow.environment.save")


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value

from autoflow.domain.environments.models import EnvironmentRef, PersistentEnvironment
from autoflow.domain.environments.rules import (
    bind_targets,
    environment_error,
    validate_end_phase,
    validate_metadata,
    validate_save,
)
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.runtime import WorkflowRuntimeError

END_TERMINAL_PHASES = frozenset({"completed", "saved_unlinked", "failed"})


def save_environment(service, project_id: str, key: str, payload: dict[str, Any], *, parent_end=None):
    now = datetime.now(UTC)
    instance_id = payload["instanceId"]
    mode = payload["mode"]
    instance = service.environments.get_instance(project_id, instance_id)
    source = None
    environment = None
    if instance.environment_id:
        environment, _active = service.environments.get_with_instance(
            project_id, instance.environment_id
        )
        source = environment.ref
    canonical = {
        "scope": "environmentSave",
        "projectId": project_id,
        "instanceId": instance_id,
        "request": payload,
    }
    operation = service._command(key, "saveEnvironment", project_id, instance.environment_id, canonical, now)
    authoritative_generation = service.execution_generation_of(instance)
    accepted, replayed = service.environments.accept_operation(operation, retention_request=payload, parent_end=parent_end)
    if replayed and accepted.result is not None:
        if accepted.result.get('phase') in {'completed', 'saved_unlinked'} and instance.state == 'closed' and instance.environment_id:
            service.environments.release_occupancy(instance.environment_id, instance_id)
        return accepted.result, accepted, True
    _reject_replayed_failure(accepted)
    claimed_generation = payload.get("currentExecutionGeneration")
    live_generation = (
        payload['executionGeneration']
        if replayed or parent_end is not None
        else authoritative_generation
        if authoritative_generation is not None
        else (
            claimed_generation
            if type(claimed_generation) is int
            else int(payload["executionGeneration"])
        )
    )
    publication_target = None
    try:
        validate_save(
            mode=mode,
            instance_state=instance.state,
            instance_use_generation=instance.instance_use_generation,
            expected_use_generation=payload["expectedUseGeneration"],
            execution_generation=payload["executionGeneration"],
            current_execution_generation=live_generation,
            source=source,
            expected_content_generation=payload.get("expectedContentGeneration"),
        )
        if mode == "save_as":
            metadata = validate_metadata(payload.get("name") or "保存环境", payload.get("notes") or "")
        else:
            # Update mode publishes onto the instance's existing source.
            if environment is None:
                raise environment_error(
                    "ENVIRONMENT_NOT_FOUND",
                    "Update requires an existing saved environment",
                    404,
                    {"domainCode": "environment_not_found"},
                )
            environment = service.environments.acquire_save_source(
                project_id, instance_id, payload.get('expectedContentGeneration')
            )
            source = environment.ref
            metadata = {"name": environment.name, "notes": environment.notes}
        save_id = accepted.operation_id
        if mode == 'save_as':
            publication_target = service.store.generation_dir(str(uuid5(_SAVE_NAMESPACE, save_id)), 1)
        else:
            assert source is not None  # validate_save rejects update without a source.
            publication_target = service.store.generation_dir(source.environment_id, source.content_generation + 1)
        service.environments.set_instance_state(instance_id, "saving")
        digest = service.store.stage_candidate(save_id, instance_id, identity_package=instance.identity_package)
        service.environments.record_save(
            save_id,
            project_id,
            instance_id,
            instance.environment_id,
            mode,
            "saving",
            payload.get("expectedContentGeneration"),
            None,
            digest,
            metadata.get("name"),
            accepted.operation_id,
            now,
        )
        if mode == "save_as":
            # Derived from the save operation so a retry after a lost response
            # republishes the same environment instead of creating a second one.
            environment_id = str(uuid5(_SAVE_NAMESPACE, save_id))
            generation = 1
            try:
                service.store.publish(environment_id, generation, save_id)
            except FileExistsError:
                digest = (service.store.generation_dir(environment_id, generation) / ".digest").read_text(
                    encoding="utf-8"
                ).strip()
            record = PersistentEnvironment(
                EnvironmentRef(project_id, environment_id, generation, 1),
                metadata["name"],
                metadata.get("notes", ""),
                "ready",
                instance.profile_id,
                None,
                now,
                now,
                identity_package=service.store.generation_identity(environment_id, generation),
            )
            saved = service.environments.create_ready(
                record,
                digest,
                created_from_source=instance.source,
                created_from_task_id=instance.active_task_id,
            )
        else:
            if source is None:
                raise environment_error(
                    "ENVIRONMENT_NOT_FOUND",
                    "Update requires an existing saved environment",
                    404,
                    {"domainCode": "environment_not_found"},
                )
            environment_id = source.environment_id
            generation = source.content_generation + 1
            try:
                service.store.publish(environment_id, generation, save_id)
            except FileExistsError:
                digest = (service.store.generation_dir(environment_id, generation) / ".digest").read_text(
                    encoding="utf-8"
                ).strip()
            saved = service.environments.publish_update(
                project_id, environment_id, digest, generation=generation,
                identity_package=service.store.generation_identity(environment_id, generation)
            )
        service.environments.record_save(
            save_id,
            project_id,
            instance_id,
            saved.ref.environment_id,
            mode,
            "linking",
            payload.get("expectedContentGeneration"),
            saved.ref.content_generation,
            digest,
            saved.name,
            accepted.operation_id,
            datetime.now(UTC),
        )
        outcome = _bind(service, project_id, saved, instance, payload.get("recordTargets") or [])
        service.environments.record_save(
            save_id,
            project_id,
            instance_id,
            saved.ref.environment_id,
            mode,
            outcome["phase"],
            payload.get("expectedContentGeneration"),
            saved.ref.content_generation,
            digest,
            saved.name,
            accepted.operation_id,
            datetime.now(UTC),
        )
        if outcome["phase"] in {"completed", "saved_unlinked"}:
            closed = service.environments.set_instance_state(instance_id, "closed")
            outcome["instance"] = closed.to_dict()
        outcome = _jsonable(outcome)
        done = service.environments.complete_operation(accepted, outcome, None, datetime.now(UTC))
        if instance.environment_id:
            service.environments.release_occupancy(instance.environment_id, instance_id)
        return outcome, done, False
    except (ProjectError, WorkflowRuntimeError, OSError) as cause:
        error: ProjectError | WorkflowRuntimeError
        if isinstance(cause, OSError):
            # Once a generation directory exists, publication may have succeeded.
            # Leave that operation unresolved for original-command reconciliation.
            if publication_target is None or publication_target.exists():
                raise
            error = environment_error(
                'STORAGE_FAILED', '环境文件保存失败，已保留关闭的工作副本', 503,
                {'domainCode': 'storage_failed'},
            )
        else:
            error = cause
        if error.code in {'STORAGE_FAILED', 'SAVE_GENERATION_CONFLICT'}:
            # validate_save proved the identity and the browser was quiescent.
            # Keep the work copy, but release only its own source occupancy.
            instance = service.environments.set_instance_state(instance_id, 'retained_unsaved')
        failed = {
            "phase": "failed",
            "complete": False,
            "instance": instance.to_dict(),
            "source": source.to_dict() if source else None,
            "saved": None,
            "targets": [item.get("recordRef") for item in payload.get("recordTargets") or []],
            "conflicts": [],
            "error": {
                "code": error.code,
                "message": error.message,
                "status": error.status,
                "details": error.details,
            },
        }
        failed = _jsonable(failed)
        done = service.environments.complete_operation(
            accepted, failed, {
                "code": error.code,
                "message": error.message,
                "status": error.status,
                "details": error.details,
            }, datetime.now(UTC)
        )
        if error is cause:
            raise
        raise error from cause


def repair_association(service, project_id: str, key: str, save_operation_id: str, payload: dict[str, Any]):
    service._writable(project_id)
    now = datetime.now(UTC)
    save = service.environments.save_by_operation(save_operation_id)
    if save is None or save["projectId"] != project_id or save["phase"] != "saved_unlinked":
        raise environment_error(
            "END_ACCESS_REVOKED",
            "Only a saved but unlinked result can be repaired",
            409,
            {"domainCode": "end_access_revoked"},
        )
    if not save["environmentId"]:
        raise environment_error("ENVIRONMENT_NOT_FOUND", "Saved environment was not found", 404)
    environment, instance = service.environments.get_with_instance(project_id, save["environmentId"])
    canonical = {
        "scope": "repairEndAssociation",
        "projectId": project_id,
        "saveOperationId": save_operation_id,
        "request": payload,
    }
    operation = service._command(key, "repairEndAssociation", project_id, environment.ref.environment_id, canonical, now)
    accepted, replayed = service.environments.accept_operation(operation)
    if replayed and accepted.result is not None:
        return accepted.result, accepted, True
    _reject_replayed_failure(accepted)
    outcome = _jsonable(_bind(service, project_id, environment, instance, payload.get("recordTargets") or []))
    service.environments.record_save(
        save["id"],
        project_id,
        save["instanceId"],
        environment.ref.environment_id,
        save["mode"],
        outcome["phase"],
        save["expectedContentGeneration"],
        save["publishedContentGeneration"],
        save["candidateDigest"],
        save["name"],
        save["operationId"],
        datetime.now(UTC),
    )
    done = service.environments.complete_operation(accepted, outcome, None, datetime.now(UTC))
    return outcome, done, False


def end_task(service, project_id: str, key: str, payload: dict[str, Any]):
    """Finish a task, saving and linking the environment when requested.

    The End ledger is the recovery authority: a retry after a lost response
    resumes at the recorded phase instead of running the save a second time,
    and never answers with an empty outcome.
    """

    now = datetime.now(UTC)
    retain = payload.get("retainEnvironment") or {"enabled": False}
    wants_retain = bool(retain.get("enabled"))
    targets = retain.get("recordTargets") or []
    canonical = {"scope": "endTask", "projectId": project_id, "request": payload}
    operation = service._command(
        key, "saveEnvironment", project_id, payload.get("instanceId"), canonical, now
    )
    accepted, replayed = service.environments.accept_operation(operation, retention_request=payload)
    if replayed and accepted.result is not None:
        return accepted.result, accepted, True
    _reject_replayed_failure(accepted)

    task_id = payload["taskId"]
    run_id = payload["runId"]
    recorded = service.environments.end_by_operation(accepted.operation_id)
    ledger: dict[str, Any]
    if recorded is None:
        ledger = {
            "id": str(uuid4()),
            "phase": "accepted",
            "saveId": None,
            "association": None,
        }
        service.environments.record_end(
            ledger["id"], project_id, task_id, run_id, "accepted", wants_retain,
            None, retain, targets, None, accepted.operation_id, now,
        )
    else:
        ledger = {
            "id": recorded["id"],
            "phase": recorded["phase"],
            "saveId": recorded["saveOperationId"],
            "association": recorded["associationResult"],
        }

    def record(nxt):
        ledger["phase"] = validate_end_phase(ledger["phase"], nxt)
        service.environments.record_end(
            ledger["id"], project_id, task_id, run_id, ledger["phase"], wants_retain,
            ledger["saveId"], retain, targets, ledger["association"],
            accepted.operation_id, datetime.now(UTC),
        )

    try:
        if not wants_retain:
            if ledger["phase"] not in END_TERMINAL_PHASES:
                if ledger["phase"] == "accepted":
                    record("prechecking")
                if ledger["phase"] == "prechecking":
                    service.quiesce_instance(project_id, payload["instanceId"])
                    record("quiescing")
                current = service.environments.get_instance(project_id, payload["instanceId"])
                service.close_instance(project_id, payload["instanceId"], current.environment_id)
                record("completed")
            outcome = _jsonable(_closed_outcome(service, project_id, payload["instanceId"]))
            done = service.environments.complete_operation(
                accepted, outcome, None, datetime.now(UTC)
            )
            return outcome, done, False

        if ledger["phase"] == "accepted":
            record("prechecking")
        if ledger["phase"] == "prechecking":
            service.quiesce_instance(project_id, payload["instanceId"])
            record("quiescing")
        if ledger["phase"] == "quiescing":
            record("saving")
        instance = service.environments.get_instance(project_id, payload["instanceId"])
        save_payload = {
            "instanceId": instance.instance_id,
            "mode": "save_as" if retain.get("mode") == "saveAs" else retain.get("mode") or "save_as",
            "expectedUseGeneration": payload["expectedUseGeneration"],
            "executionGeneration": payload["executionGeneration"],
            "name": retain.get("name"),
            "notes": retain.get("notes") or "",
            "expectedContentGeneration": retain.get("expectedContentGeneration"),
            "recordTargets": retain.get("recordTargets") or [],
        }
        save_key = f"end-save:{accepted.operation_id}"
        outcome, save_operation, _save_replayed = save_environment(
            service, project_id, save_key, save_payload, parent_end=accepted
        )
        ledger["saveId"] = save_operation.operation_id
        if outcome is None:
            raise environment_error(
                "OPERATION_IN_PROGRESS",
                "环境保存尚未完成，请稍后按原操作查询",
                409,
                {"domainCode": "operation_in_progress"},
            )
        ledger["association"] = {
            "phase": outcome["phase"],
            "conflicts": outcome.get("conflicts"),
        }
        if ledger["phase"] not in END_TERMINAL_PHASES:
            if outcome["phase"] == "completed":
                record("linking")
                record("completed")
            elif outcome["phase"] == "saved_unlinked":
                record("saved_unlinked")
            else:
                record("failed")
        if outcome["phase"] in {"completed", "saved_unlinked"}:
            service.close_instance(project_id, instance.instance_id, instance.environment_id)
            outcome["instance"] = service.environments.get_instance(
                project_id, instance.instance_id
            ).to_dict()
        outcome = _jsonable(outcome)
        done = service.environments.complete_operation(
            accepted,
            outcome,
            None if outcome["complete"] else {
                "code": "SAVED_UNLINKED",
                "message": "Environment saved but association is incomplete",
                "details": {"domainCode": "saved_unlinked"},
            },
            datetime.now(UTC),
        )
        return outcome, done, False
    except (ProjectError, WorkflowRuntimeError) as error:
        if ledger["phase"] not in END_TERMINAL_PHASES:
            record("failed")
        service.environments.complete_operation(
            accepted,
            None,
            {
                "code": error.code,
                "message": error.message,
                "status": error.status,
                "details": error.details,
            },
            datetime.now(UTC),
        )
        raise


def _closed_outcome(service, project_id: str, instance_id: str) -> dict[str, Any]:
    return {
        "phase": "completed",
        "complete": True,
        "instance": service.environments.get_instance(project_id, instance_id).to_dict(),
        "source": None,
        "saved": None,
        "targets": [],
        "conflicts": [],
    }


def _reject_replayed_failure(accepted) -> None:
    """A finished failure keeps its verdict; a retry must not silently succeed."""

    if accepted.status != "failed":
        return
    error = accepted.error or {}
    raise environment_error(
        error.get("code") or "OPERATION_FAILED",
        error.get("message") or "Operation failed",
        error.get("status") or 409,
        error.get("details") or {},
    )



def _bind(service, project_id: str, environment: PersistentEnvironment, instance, requested: list[dict[str, Any]]):
    conflicts = []
    try:
        targets = service.environments.load_bind_targets(project_id, requested)
        results = bind_targets(environment.ref.environment_id, targets)
        service.environments.bind_records(project_id, environment.ref.environment_id, results)
        phase = "completed"
    except (ProjectError, WorkflowRuntimeError) as error:
        if error.code in {"LINK_REVISION_CONFLICT", "ASSOCIATION_REPLACE_FORBIDDEN", "ASSOCIATION_TARGET_MISSING"}:
            details = error.details
            if error.code == "LINK_REVISION_CONFLICT":
                conflicts.append(
                    {
                        "record": details.get("record"),
                        "expectedLinkRevision": details.get("expectedRevision"),
                        "currentLinkRevision": details.get("currentRevision"),
                    }
                )
            phase = "saved_unlinked"
        else:
            raise
    return {
        "phase": phase,
        "complete": phase == "completed",
        "instance": instance.to_dict() if instance is not None else None,
        "source": environment.ref.to_dict() if hasattr(environment.ref, "to_dict") else {
            "projectId": environment.ref.project_id,
            "environmentId": environment.ref.environment_id,
            "contentGeneration": environment.ref.content_generation,
            "metadataRevision": environment.ref.metadata_revision,
        },
        "saved": {
            "projectId": environment.ref.project_id,
            "environmentId": environment.ref.environment_id,
            "contentGeneration": environment.ref.content_generation,
            "metadataRevision": environment.ref.metadata_revision,
        },
        "targets": [item.get("recordRef") for item in requested],
        "conflicts": conflicts,
    }
