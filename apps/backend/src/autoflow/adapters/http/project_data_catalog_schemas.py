"""Current field/status commands, with business validation in the data service."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue, StrictBool, StrictFloat, StrictInt, StrictStr

from .schemas import ApiModel

Revision = Annotated[int, Field(strict=True, ge=1, le=9_007_199_254_740_991)]


class DataDateScalar(ApiModel):
    kind: Literal["date"]
    precision: Literal["date", "datetime"]
    value: str
    offset: str | None


Scalar = StrictStr | StrictInt | StrictFloat | StrictBool | DataDateScalar | None


class DataFieldRef(ApiModel):
    project_id: str
    table_id: str
    dataset_generation: str
    field_id: str


class FieldResourceLocator(ApiModel):
    type: Literal["field"]
    field_ref: DataFieldRef


class StatusResourceLocator(ApiModel):
    type: Literal["status"]
    project_id: str
    table_id: str
    status_id: str


class DataFieldWrite(ApiModel):
    key: str
    name: str
    type: Literal["string", "number", "boolean", "date"]
    required: StrictBool
    validation: dict[str, JsonValue]


class DataFieldView(DataFieldWrite):
    ref: DataFieldRef
    writable: bool
    formula: bool
    field_revision: Revision


class DataFieldDirectory(ApiModel):
    items: list[DataFieldView]
    table_revision: Revision


class DataFieldCreate(ApiModel):
    definition: DataFieldWrite
    expected_table_revision: Revision
    existing_record_default: Scalar = None
    source_column_policy: Literal["localOnly", "mapped"]


class DataFieldMutationView(ApiModel):
    field: DataFieldView
    table_revision: Revision


class FieldMutationResult(DataFieldMutationView):
    action: Literal["create"]


class DataStatusView(ApiModel):
    status_id: str
    name: str
    color: str
    order: int
    status_revision: Revision


class DataStatusDirectory(ApiModel):
    items: list[DataStatusView]
    table_revision: Revision


class DataStatusCreate(ApiModel):
    name: str
    color: str
    order: Annotated[int, Field(strict=True, ge=0, le=9_007_199_254_740_991)]
    expected_table_revision: Revision


class DataStatusPatch(ApiModel):
    # The handler dumps exclude_unset=True: omitted attributes never enter the
    # command. Factories keep the optional wire properties non-nullable.
    name: str = Field(default_factory=str)
    color: str = Field(default_factory=str)
    order: Annotated[int, Field(strict=True, ge=0, le=9_007_199_254_740_991)] = Field(
        default_factory=int
    )
    expected_table_revision: Revision
    expected_status_revision: Revision


class StatusMutationResult(ApiModel):
    action: Literal["create", "update"]
    status: DataStatusView
    table_revision: Revision
