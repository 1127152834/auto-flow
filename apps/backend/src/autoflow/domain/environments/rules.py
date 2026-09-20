from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from autoflow.domain.environments.models import (
    BindResult,
    BindTarget,
    EndPhase,
    EnvironmentOccupancy,
    EnvironmentRef,
    ManualStatus,
    PersistentEnvironment,
    ResolvedEnvironmentSource,
    SaveMode,
)
from autoflow.domain.projects.models import ProjectError

END_PHASES: tuple[EndPhase, ...] = (
    "accepted",
    "prechecking",
    "quiescing",
    "saving",
    "linking",
    "completed",
    "saved_unlinked",
    "failed",
)
END_ADVANCE = {
    "accepted": "prechecking",
    "prechecking": "quiescing",
    "quiescing": "saving",
    "saving": "linking",
    "linking": "completed",
}
MANUAL_TERMINAL = {"resolved", "expired", "lost", "cancelled"}
LIVE_INSTANCE_STATES = frozenset(
    {
        "reserved",
        "starting",
        "active",
        "waiting_manual",
        "closing",
        "saving",
        "retained_unsaved",
    }
)
OPENABLE_INSTANCE_STATES = frozenset({"reserved", "starting", "active", "waiting_manual"})


def environment_error(
    code: str, message: str, status: int, details: dict[str, Any] | None = None
) -> ProjectError:
    payload = dict(details or {})
    payload.setdefault("domainCode", code.lower())
    payload.setdefault("retryable", False)
    return ProjectError(code, message, status, payload)


def validate_metadata(name: str | None = None, notes: str | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    if name is not None:
        if type(name) is not str:
            raise environment_error(
                "VALIDATION_ERROR", "Invalid environment metadata", 422, {"fields": {"name": "Must be a string"}}
            )
        cleaned = name.strip()
        if not 1 <= len(cleaned) <= 36:
            raise environment_error(
                "VALIDATION_ERROR",
                "Invalid environment metadata",
                422,
                {"fields": {"name": "Must contain 1 to 36 Unicode code points"}},
            )
        result["name"] = cleaned
    if notes is not None:
        if type(notes) is not str:
            raise environment_error(
                "VALIDATION_ERROR",
                "Invalid environment metadata",
                422,
                {"fields": {"notes": "Must be a string"}},
            )
        cleaned = notes.strip()
        if len(cleaned) > 120:
            raise environment_error(
                "VALIDATION_ERROR",
                "Invalid environment metadata",
                422,
                {"fields": {"notes": "Must contain at most 120 Unicode code points"}},
            )
        result["notes"] = cleaned
    if not result:
        raise environment_error(
            "VALIDATION_ERROR",
            "Invalid environment metadata",
            422,
            {"fields": {"form": "At least one change is required"}},
        )
    return result


def resolve_environment_source(
    policy: dict[str, Any],
    *,
    project_id: str,
    project_default_profile_id: str | None,
    inputs: dict[str, dict[str, Any]] | None = None,
    environments: dict[str, PersistentEnvironment] | None = None,
) -> ResolvedEnvironmentSource:
    if not isinstance(policy, dict) or policy.get("source") not in {
        "newFromProfile",
        "fixedEnvironment",
        "inputEnvironment",
    }:
        raise environment_error(
            "VALIDATION_ERROR",
            "Invalid environment source",
            422,
            {"fields": {"environmentPolicy": "Invalid environment source"}},
        )
    source = policy["source"]
    profile_id = policy.get("profileId") or project_default_profile_id
    if source == "newFromProfile":
        if profile_id is None:
            raise environment_error(
                "VALIDATION_ERROR",
                "Browser profile is required",
                422,
                {"fields": {"environmentPolicy.profileId": "请选择浏览器配置"}},
            )
        return ResolvedEnvironmentSource(
            source,
            None,
            _uuid(profile_id, "environmentPolicy.profileId"),
            {"source": source, "profileId": str(UUID(str(profile_id)))},
        )
    if source == "fixedEnvironment":
        environment = _ready_environment(
            policy.get("environmentId"),
            project_id,
            environments or {},
            field="environmentPolicy.environmentId",
        )
        return ResolvedEnvironmentSource(
            source,
            environment.ref,
            environment.profile_id,
            {
                "source": source,
                "environmentId": environment.ref.environment_id,
                "contentGeneration": environment.ref.content_generation,
                "profileId": environment.profile_id,
            },
        )
    input_id = policy.get("inputId")
    snapshots = inputs or {}
    if input_id is None:
        associated = {
            snapshot.get("currentEnvironmentId")
            for snapshot in snapshots.values()
            if snapshot.get("currentEnvironmentId")
        }
        if len(associated) != 1:
            raise environment_error(
                "ENVIRONMENT_SOURCE_AMBIGUOUS",
                "Environment source must be selected explicitly",
                422,
                {"domainCode": "environment_source_ambiguous"},
            )
        input_id = next(
            key
            for key, snapshot in snapshots.items()
            if snapshot.get("currentEnvironmentId") == next(iter(associated))
        )
    if input_id not in snapshots:
        raise environment_error(
            "VALIDATION_ERROR",
            "Environment input is missing",
            422,
            {"fields": {"environmentPolicy.inputId": "Must reference a task input"}},
        )
    environment_id = snapshots[input_id].get("currentEnvironmentId")
    environment = _ready_environment(
        environment_id,
        project_id,
        environments or {},
        field="environmentPolicy.inputId",
    )
    return ResolvedEnvironmentSource(
        source,
        environment.ref,
        environment.profile_id,
        {
            "source": source,
            "inputId": input_id,
            "environmentId": environment.ref.environment_id,
            "contentGeneration": environment.ref.content_generation,
            "profileId": environment.profile_id,
        },
    )


def check_live_capacity(live_count: int, max_live_instances: int) -> None:
    if type(max_live_instances) is not int or max_live_instances < 1:
        raise environment_error(
            "VALIDATION_ERROR",
            "Live instance capacity is invalid",
            422,
            {"fields": {"maxLiveInstances": "Must be a positive integer"}},
        )
    if live_count >= max_live_instances:
        raise environment_error(
            "CAPACITY_EXHAUSTED",
            "Live browser capacity is exhausted",
            429,
            {
                "domainCode": "capacity_exhausted",
                "retryable": True,
                "retryAfterSeconds": 15,
                "liveCount": live_count,
                "maxLiveInstances": max_live_instances,
            },
        )


def validate_open_instance(
    *,
    instance_state: str,
    instance_use_generation: int,
    expected_use_generation: int,
) -> None:
    if instance_use_generation != expected_use_generation:
        raise environment_error(
            "INSTANCE_OWNERSHIP_UNKNOWN",
            "Instance use generation does not match",
            409,
            {"domainCode": "instance_ownership_unknown"},
        )
    if instance_state not in OPENABLE_INSTANCE_STATES:
        raise environment_error(
            "ENVIRONMENT_UNAVAILABLE",
            "Environment instance is not openable",
            409,
            {"domainCode": "environment_unavailable", "state": instance_state},
        )


def occupy_environment(
    environment_id: str,
    instance_id: str,
    holder_kind: str,
    holder_id: str,
    current: EnvironmentOccupancy | None,
) -> EnvironmentOccupancy:
    if current is None:
        return EnvironmentOccupancy(environment_id, instance_id, holder_kind, holder_id)  # type: ignore[arg-type]
    if (
        current.environment_id == environment_id
        and current.instance_id == instance_id
        and current.holder_kind == holder_kind
        and current.holder_id == holder_id
    ):
        return current
    raise environment_error(
        "ENVIRONMENT_BUSY",
        "Saved environment is already in use",
        423,
        {
            "domainCode": "environment_busy",
            "holderKind": current.holder_kind,
            "holderId": current.holder_id,
            "instanceId": current.instance_id,
        },
    )


def validate_save(
    *,
    mode: SaveMode,
    instance_state: str,
    instance_use_generation: int,
    expected_use_generation: int,
    execution_generation: int,
    current_execution_generation: int,
    source: EnvironmentRef | None,
    expected_content_generation: int | None,
) -> None:
    if execution_generation != current_execution_generation:
        raise environment_error(
            "EXECUTION_GENERATION_REVOKED",
            "Stale execution cannot save the environment",
            410,
            {"domainCode": "execution_generation_revoked"},
        )
    if instance_use_generation != expected_use_generation:
        raise environment_error(
            "INSTANCE_OWNERSHIP_UNKNOWN",
            "Instance use generation does not match",
            409,
            {"domainCode": "instance_ownership_unknown"},
        )
    if instance_state not in {"closed", "saving", "retained_unsaved"}:
        raise environment_error(
            "INSTANCE_NOT_QUIESCENT",
            "Environment instance is not still",
            409,
            {"domainCode": "instance_not_quiescent", "state": instance_state},
        )
    if mode == "update":
        if source is None:
            raise environment_error(
                "ENVIRONMENT_NOT_FOUND",
                "Update requires an existing saved environment",
                404,
                {"domainCode": "environment_not_found"},
            )
        if expected_content_generation != source.content_generation:
            raise environment_error(
                "SAVE_GENERATION_CONFLICT",
                "Saved environment content has changed",
                409,
                {
                    "domainCode": "save_generation_conflict",
                    "expectedRevision": expected_content_generation,
                    "currentRevision": source.content_generation,
                },
            )


def bind_targets(
    environment_id: str, targets: Iterable[BindTarget]
) -> list[BindResult]:
    results: list[BindResult] = []
    seen: set[str] = set()
    for target in targets:
        identity = _record_identity(target.record_ref)
        if identity in seen:
            continue
        seen.add(identity)
        if target.current_link_revision != target.expected_link_revision:
            raise environment_error(
                "LINK_REVISION_CONFLICT",
                "Record environment link has changed",
                409,
                {
                    "domainCode": "link_revision_conflict",
                    "expectedRevision": target.expected_link_revision,
                    "currentRevision": target.current_link_revision,
                    "record": target.record_ref,
                },
            )
        if target.current_environment_id == environment_id:
            results.append(
                BindResult(
                    target.record_ref,
                    target.current_environment_id,
                    environment_id,
                    target.current_link_revision,
                    False,
                )
            )
            continue
        if target.current_environment_id not in {None, environment_id} and not target.replace_allowed:
            raise environment_error(
                "ASSOCIATION_REPLACE_FORBIDDEN",
                "Replacing an existing environment link requires explicit authorization",
                403,
                {
                    "domainCode": "association_replace_forbidden",
                    "record": target.record_ref,
                    "currentEnvironmentId": target.current_environment_id,
                },
            )
        results.append(
            BindResult(
                target.record_ref,
                target.current_environment_id,
                environment_id,
                target.current_link_revision + 1,
                True,
            )
        )
    return results


def validate_end_phase(current: EndPhase, nxt: EndPhase) -> EndPhase:
    if current in {"completed", "saved_unlinked", "failed"}:
        if nxt == current:
            return current
        raise environment_error(
            "END_ACCESS_REVOKED",
            "End result is already final",
            403,
            {"domainCode": "end_access_revoked", "phase": current},
        )
    if current == "quiescing" and nxt == "completed":
        return nxt  # No retention requested; confirmed closure is sufficient.
    if nxt == "failed":
        return nxt
    if current == "saving" and nxt == "saved_unlinked":
        return nxt
    if current in END_ADVANCE and nxt == END_ADVANCE[current]:
        return nxt
    if current == nxt:
        return current
    raise environment_error(
        "VALIDATION_ERROR",
        "Invalid end phase transition",
        409,
        {"current": current, "next": nxt},
    )


def validate_manual_transition(
    current: ManualStatus,
    nxt: ManualStatus,
    *,
    resume_started: bool,
) -> ManualStatus:
    if current in MANUAL_TERMINAL:
        if nxt == current:
            return current
        raise environment_error(
            "MANUAL_ALREADY_RESOLVED",
            "Manual item already has an authoritative result",
            409,
            {"domainCode": "manual_already_resolved", "status": current},
        )
    if current == "waiting" and nxt == "resume_requested":
        return nxt
    if current == "resume_requested" and nxt == "resolved" and resume_started:
        return nxt
    if current in {"waiting", "resume_requested"} and nxt in MANUAL_TERMINAL:
        if current == "resume_requested" and resume_started and nxt != "resolved":
            raise environment_error(
                "MANUAL_TRANSITION_LOST",
                "Resume already started",
                409,
                {"domainCode": "manual_transition_lost"},
            )
        return nxt
    if current == nxt:
        return current
    raise environment_error(
        "MANUAL_TRANSITION_LOST",
        "Manual transition lost the race",
        409,
        {"domainCode": "manual_transition_lost", "current": current, "next": nxt},
    )


def next_content_generation(current: int) -> int:
    if current < 1:
        raise environment_error(
            "VALIDATION_ERROR", "contentGeneration must start at 1", 422
        )
    return current + 1


def _ready_environment(
    environment_id: Any,
    project_id: str,
    environments: dict[str, PersistentEnvironment],
    *,
    field: str,
) -> PersistentEnvironment:
    if environment_id is None:
        raise environment_error(
            "ENVIRONMENT_NOT_FOUND",
            "Saved environment was not found",
            404,
            {"domainCode": "environment_not_found", "fields": {field: "Required"}},
        )
    key = _uuid(environment_id, field)
    environment = environments.get(key)
    if environment is None or environment.state == "deleted":
        raise environment_error(
            "ENVIRONMENT_NOT_FOUND",
            "Saved environment was not found",
            404,
            {"domainCode": "environment_not_found"},
        )
    if environment.ref.project_id != project_id:
        raise environment_error(
            "ENVIRONMENT_SCOPE_MISMATCH",
            "Environment does not belong to this project",
            404,
            {"domainCode": "environment_scope_mismatch"},
        )
    if environment.state != "ready":
        raise environment_error(
            "ENVIRONMENT_UNAVAILABLE",
            "Saved environment is not ready",
            409,
            {
                "domainCode": "environment_unavailable",
                "state": environment.state,
                "unavailableReason": environment.unavailable_reason,
            },
        )
    return environment


def _uuid(value: Any, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as error:
        raise environment_error(
            "VALIDATION_ERROR",
            "Invalid identifier",
            422,
            {"fields": {field: "Must be a UUID"}},
        ) from error


def _record_identity(record_ref: dict[str, Any]) -> str:
    key = record_ref.get("recordKey") or {}
    return "|".join(
        [
            str(record_ref.get("projectId") or ""),
            str(record_ref.get("tableId") or ""),
            str(record_ref.get("datasetGeneration") or ""),
            str(key.get("type") or ""),
            str(key.get("value") or ""),
        ]
    )
