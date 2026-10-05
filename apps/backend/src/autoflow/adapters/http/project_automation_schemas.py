from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    Field,
    JsonValue,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)

from .project_data_catalog_schemas import DataFieldRef
from .project_data_record_schemas import DataRecordRef
from .schemas import ApiModel

JsonScalar = StrictStr | StrictInt | StrictFloat | StrictBool | None


class InputFieldBinding(ApiModel):
    input_field_id: str
    input_field_alias: str
    field_ref: DataFieldRef
    # Remediation M2 R2-20: the workflow signature field this binding supplies.
    signature_field: StrictStr | None = None


class RecordSlotRelation(ApiModel):
    type: Literal["recordSlot"]
    slot_id: str
    source_input_id: str


class FieldEqualsRelation(ApiModel):
    type: Literal["fieldEquals"]
    source_input_id: str
    source_field_ref: DataFieldRef
    target_field_ref: DataFieldRef


class SameRecordRelation(ApiModel):
    type: Literal["sameRecord"]
    source_input_id: str


InputRelation = Annotated[
    RecordSlotRelation | FieldEqualsRelation | SameRecordRelation,
    Field(discriminator="type"),
]


class InputDefinition(ApiModel):
    input_id: str
    alias: str
    table_id: str
    dataset_generation: str
    mode: Literal["independent", "fixedRecord", "related"]
    required: StrictBool
    fixed_record: DataRecordRef | None = None
    relation: InputRelation | None = None
    field_bindings: list[InputFieldBinding]
    # Remediation M2 R2-20: the workflow signature input this data input supplies.
    signature_input: StrictStr | None = None
    filter: dict[str, JsonValue]
    order_by: list[dict[str, str]]


class InputPlan(ApiModel):
    inputs: list[InputDefinition]
    # Remediation M2 §2: which required input is processed row by row; omitted when unambiguous.
    processing_input_id: StrictStr | None = None


class ParameterDefinition(ApiModel):
    parameter_id: str
    name: str
    description: str = Field(default_factory=str)
    type: Literal["string", "number", "boolean"]
    required: StrictBool
    default_value: JsonScalar = None


class SourceDefaultProxy(ApiModel):
    mode: Literal["sourceDefault"]


class NoProxy(ApiModel):
    mode: Literal["none"]


class FixedProxy(ApiModel):
    mode: Literal["fixed"]
    proxy_id: str


class PoolProxy(ApiModel):
    mode: Literal["pool"]
    proxy_pool_id: str


ProxySelection = Annotated[
    SourceDefaultProxy | NoProxy | FixedProxy | PoolProxy, Field(discriminator="mode")
]


class NewFromProfile(ApiModel):
    source: Literal["newFromProfile"]
    profile_id: str | None = None
    proxy_override: ProxySelection | None = None
    model_provider_id: str | None = None


class FixedEnvironment(ApiModel):
    source: Literal["fixedEnvironment"]
    environment_id: str
    proxy_override: ProxySelection | None = None
    model_provider_id: str | None = None


class InputEnvironment(ApiModel):
    source: Literal["inputEnvironment"]
    input_id: str
    proxy_override: ProxySelection | None = None
    model_provider_id: str | None = None


class InputIdentity(ApiModel):
    """Remediation M4 R4-03: run as the identity linked to the task's input record."""

    source: Literal["inputIdentity"]
    input_id: str
    profile_id: str | None = None
    proxy_override: ProxySelection | None = None
    model_provider_id: str | None = None


EnvironmentPolicy = Annotated[
    NewFromProfile | FixedEnvironment | InputEnvironment | InputIdentity,
    Field(discriminator="source"),
]


class RunPolicy(ApiModel):
    max_tasks: StrictInt = Field(ge=1, le=100)
    concurrency: StrictInt = Field(ge=1)
    max_live_instances: StrictInt = Field(ge=1)
    continue_after_failure: StrictBool
    automatic_execution_timeout_seconds: StrictInt | StrictFloat = Field(gt=0)
    manual_deadline_seconds: StrictInt | StrictFloat = Field(gt=0)
    # Remediation M2 R2-03/R2-04; omitted on automations saved before claim modes (treated as cycle).
    claim_mode: Literal["unprocessed", "cycle", "retryFailed"] | None = None
    retry_budget: StrictInt | None = Field(default=None, ge=1, le=20)
    retry_backoff_seconds: list[StrictInt] | None = Field(default=None, min_length=1, max_length=10)
    failure_policy: Literal["thresholds"] | None = None
    # Remediation M3 R3-07; omitted means perTask.
    session_mode: Literal["perTask", "pool"] | None = None


class CapabilityRequirement(ApiModel):
    capability: str
    required: bool
    available: bool
    reason: str | None = None


class AutomationCreate(ApiModel):
    name: str
    description: str
    input_plan: InputPlan
    parameter_schema: list[ParameterDefinition]
    environment_policy: EnvironmentPolicy
    run_policy: RunPolicy

    def payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_unset=True)


class AutomationWrite(AutomationCreate):
    workflow_id: str


class AutomationUpdate(AutomationWrite):
    expected_management_revision: StrictInt = Field(ge=1)


class AutomationView(AutomationWrite):
    automation_id: str
    project_id: str
    management_revision: int
    capability_requirements: list[CapabilityRequirement] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AutomationPage(ApiModel):
    items: list[AutomationView]
    page: int
    page_size: int
    total: int
    sort: str


class AutomationValidationIssue(ApiModel):
    path: list[str]
    code: str
    message: str
    resource: dict[str, Any] | None = None


class AutomationValidationView(ApiModel):
    status: Literal["ready", "draft", "blocked", "unavailable"]
    valid: bool
    runnable: bool
    issues: list[AutomationValidationIssue]
    capability_requirements: list[CapabilityRequirement]
    checked_at: datetime
    notices: list[AutomationValidationIssue] = Field(default_factory=list)


class AutomationDeleteRequest(ApiModel):
    impact_revision: StrictInt = Field(ge=1)
    expected_management_revision: StrictInt = Field(ge=1)
    workflow_disposition: Literal["unlink", "deleteOwned"]

    def payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)
