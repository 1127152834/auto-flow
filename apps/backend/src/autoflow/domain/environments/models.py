from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

PersistentEnvironmentState = Literal["ready", "unavailable", "deleting", "deleted"]
InstanceState = Literal[
    "reserved",
    "starting",
    "active",
    "waiting_manual",
    "closing",
    "closed",
    "saving",
    "retained_unsaved",
    "cleaning",
    "cleaned",
    "cleanup_failed",
    "unknown",
]
EnvironmentSource = Literal["newFromProfile", "fixedEnvironment", "inputEnvironment"]
SaveMode = Literal["update", "save_as"]
EndPhase = Literal[
    "accepted",
    "prechecking",
    "quiescing",
    "saving",
    "linking",
    "completed",
    "saved_unlinked",
    "failed",
]
ManualStatus = Literal[
    "waiting",
    "resume_requested",
    "resolved",
    "expired",
    "lost",
    "cancelled",
]
HolderKind = Literal["task", "maintenance"]


@dataclass(frozen=True)
class EnvironmentRef:
    project_id: str
    environment_id: str
    content_generation: int
    metadata_revision: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectId": self.project_id,
            "environmentId": self.environment_id,
            "contentGeneration": self.content_generation,
            "metadataRevision": self.metadata_revision,
        }


@dataclass(frozen=True)
class PersistentEnvironment:
    ref: EnvironmentRef
    name: str
    notes: str
    state: PersistentEnvironmentState
    profile_id: str
    unavailable_reason: str | None
    created_at: datetime
    updated_at: datetime
    # Where the saved copy came from. The directory artboard shows "最近来源",
    # so the list view needs the creating source and task without a second call.
    created_from_source: str = "newFromProfile"
    created_from_task_id: str | None = None
    identity_package: dict[str, Any] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": {
                "projectId": self.ref.project_id,
                "environmentId": self.ref.environment_id,
                "contentGeneration": self.ref.content_generation,
                "metadataRevision": self.ref.metadata_revision,
            },
            "name": self.name,
            "notes": self.notes,
            "state": self.state,
            "profileId": self.profile_id,
            "unavailableReason": self.unavailable_reason,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "createdFromSource": self.created_from_source,
            "createdFromTaskId": self.created_from_task_id,
        }


@dataclass(frozen=True)
class EnvironmentInstance:
    instance_id: str
    project_id: str
    environment_id: str | None
    state: InstanceState
    source: EnvironmentSource
    source_content_generation: int | None
    instance_use_generation: int
    active_task_id: str | None
    active_run_id: str | None
    maintenance_operation_id: str | None
    profile_id: str
    created_at: datetime
    updated_at: datetime

    identity_package: dict[str, Any] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instanceId": self.instance_id,
            "projectId": self.project_id,
            "environmentId": self.environment_id,
            "state": self.state,
            "source": self.source,
            "sourceContentGeneration": self.source_content_generation,
            "instanceUseGeneration": self.instance_use_generation,
            "activeTaskId": self.active_task_id,
            "activeRunId": self.active_run_id,
            "maintenanceOperationId": self.maintenance_operation_id,
            "profileId": self.profile_id,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


@dataclass(frozen=True)
class EnvironmentOccupancy:
    environment_id: str
    instance_id: str
    holder_kind: HolderKind
    holder_id: str


@dataclass(frozen=True)
class ResolvedEnvironmentSource:
    source: EnvironmentSource
    environment_ref: EnvironmentRef | None
    profile_id: str
    identity_package: dict[str, Any]


@dataclass(frozen=True)
class BindTarget:
    record_ref: dict[str, Any]
    expected_link_revision: int
    replace_allowed: bool
    current_environment_id: str | None
    current_link_revision: int


@dataclass(frozen=True)
class BindResult:
    record_ref: dict[str, Any]
    previous_environment_id: str | None
    environment_id: str | None
    link_revision: int
    changed: bool
