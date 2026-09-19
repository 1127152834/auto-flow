from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .schemas import ApiModel


class EnvironmentRefView(ApiModel):
    project_id: str
    environment_id: str
    content_generation: int
    metadata_revision: int


class EnvironmentView(ApiModel):
    ref: EnvironmentRefView
    name: str
    notes: str
    state: Literal["ready", "unavailable", "deleting", "deleted"]
    profile_id: str
    unavailable_reason: str | None
    created_at: datetime
    updated_at: datetime
    created_from_source: str | None = None
    created_from_task_id: str | None = None
    linked_record_count: int = 0


class EnvironmentInstanceView(ApiModel):
    instance_id: str
    project_id: str
    environment_id: str | None
    state: str
    source: str
    source_content_generation: int | None
    instance_use_generation: int
    active_task_id: str | None
    active_run_id: str | None
    maintenance_operation_id: str | None
    profile_id: str
    created_at: datetime
    updated_at: datetime


class EnvironmentDetailView(ApiModel):
    environment: EnvironmentView
    active_instance: EnvironmentInstanceView | None
    linked_record_count: int = 0


class EnvironmentDeleteRequest(ApiModel):
    impact_revision: int
    expected_metadata_revision: int
    expected_content_generation: int

    def payload(self):
        return self.model_dump(by_alias=True)


class EnvironmentImpactView(ApiModel):
    impact_revision: int
    impacts: list[dict[str, Any]]
    blockers: list[dict[str, Any]]


class ManualItemView(ApiModel):
    manual_item_id: str
    project_id: str
    task_id: str
    run_id: str
    instance_id: str | None
    checkpoint_revision: int
    status: str
    status_revision: int
    expires_at: datetime | None
    allowed_targets: list[Any]
    resume_started: bool
    reason: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ManualItemPage(ApiModel):
    items: list[ManualItemView]
    page: int
    page_size: int
    total: int


class ManualResumeRequest(ApiModel):
    checkpoint_revision: int
    expected_status_revision: int
    target_node_id: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)


class ManualFinishRequest(ApiModel):
    expected_checkpoint_revision: int
    expected_status_revision: int
    outcome: Literal["succeeded", "failed"]
    reason: str
    retain_environment: dict[str, Any]


class EnvironmentPage(ApiModel):
    items: list[EnvironmentView]
    page: int
    page_size: int
    total: int
    sort: str


class EnvironmentInstancePage(ApiModel):
    items: list[EnvironmentInstanceView]
    page: int
    page_size: int
    total: int
    sort: str


class EnvironmentPatch(ApiModel):
    expected_metadata_revision: int
    name: str | None = None
    notes: str | None = None

    def payload(self) -> dict:
        data: dict[str, Any] = {"expectedMetadataRevision": self.expected_metadata_revision}
        if self.name is not None:
            data["name"] = self.name
        if self.notes is not None:
            data["notes"] = self.notes
        return data


class RecordTargetWrite(ApiModel):
    record_ref: dict[str, Any]
    expected_link_revision: int
    replace_allowed: bool = False


class EnvironmentSaveRequest(ApiModel):
    instance_id: str
    mode: Literal["update", "saveAs"]
    expected_use_generation: int
    execution_generation: int
    # A client may still claim which generation it believes is live. The claim is
    # accepted for compatibility and then ignored: the stored run generation is
    # authoritative, so a revoked generation cannot be revalidated by asking.
    current_execution_generation: int | None = None
    name: str | None = None
    notes: str | None = None
    expected_content_generation: int | None = None
    record_targets: list[RecordTargetWrite] = Field(default_factory=list)

    def payload(self) -> dict:
        return {
            "instanceId": self.instance_id,
            "mode": "save_as" if self.mode == "saveAs" else "update",
            "expectedUseGeneration": self.expected_use_generation,
            "executionGeneration": self.execution_generation,
            "currentExecutionGeneration": self.current_execution_generation,
            "name": self.name,
            "notes": self.notes,
            "expectedContentGeneration": self.expected_content_generation,
            "recordTargets": [
                {
                    "recordRef": item.record_ref,
                    "expectedLinkRevision": item.expected_link_revision,
                    "replaceAllowed": item.replace_allowed,
                }
                for item in self.record_targets
            ],
        }


class EnvironmentOpenRequest(ApiModel):
    expected_use_generation: int

    def payload(self) -> dict:
        return {"expectedUseGeneration": self.expected_use_generation}


class MaintenanceStartRequest(ApiModel):
    expected_content_generation: int


class MaintenanceDiscardRequest(ApiModel):
    maintenance_operation_id: str
    instance_id: str


class EnvironmentEndRequest(ApiModel):
    task_id: str
    run_id: str
    instance_id: str
    expected_use_generation: int
    execution_generation: int
    retain_environment: dict[str, Any]

    def payload(self) -> dict:
        return {
            "taskId": self.task_id,
            "runId": self.run_id,
            "instanceId": self.instance_id,
            "expectedUseGeneration": self.expected_use_generation,
            "executionGeneration": self.execution_generation,
            "retainEnvironment": self.retain_environment,
        }


class EnvironmentRepairRequest(ApiModel):
    record_targets: list[RecordTargetWrite] = Field(default_factory=list)

    def payload(self) -> dict:
        return {
            "recordTargets": [
                {
                    "recordRef": item.record_ref,
                    "expectedLinkRevision": item.expected_link_revision,
                    "replaceAllowed": item.replace_allowed,
                }
                for item in self.record_targets
            ]
        }


class AssociationConflictView(ApiModel):
    record: dict[str, Any]
    expected_link_revision: int
    current_link_revision: int


class EnvironmentOutcomeView(ApiModel):
    phase: str
    complete: bool
    instance: EnvironmentInstanceView | None
    source: EnvironmentRefView | None
    saved: EnvironmentRefView | None
    targets: list[dict[str, Any]]
    conflicts: list[AssociationConflictView]


class EnvironmentOperationSnapshot(ApiModel):
    operation_id: str
    project_id: str | None
    idempotency_key: str
    kind: str
    status: str
    status_revision: int
    resource: dict[str, Any]
    result: dict[str, Any] | None
    error: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class EnvironmentOperationView(ApiModel):
    operation: EnvironmentOperationSnapshot
    outcome: dict[str, Any] | None
