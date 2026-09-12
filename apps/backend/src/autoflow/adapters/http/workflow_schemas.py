from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, JsonValue, field_validator

from .schemas import ApiModel

NodeType = Literal[
    "open_page",
    "click_element",
    "input_text",
    "wait_element",
    "get_element_info",
    "screenshot",
]
Identifier = Annotated[str, Field(min_length=1, max_length=120, strict=True)]


class WorkflowNode(ApiModel):
    id: Identifier
    type: NodeType
    label: str = Field(max_length=120, strict=True)
    config: dict[str, JsonValue]


class WorkflowEdge(ApiModel):
    id: Identifier
    source: Identifier
    target: Identifier
    source_handle: Literal["out"]
    target_handle: Literal["in"]


class WorkflowVariable(ApiModel):
    name: str = Field(max_length=120, strict=True)
    type: Literal["string", "number", "boolean", "array", "object"]
    value: JsonValue


class WorkflowDocument(ApiModel):
    id: str
    name: str = Field(min_length=1, max_length=120, strict=True)
    schema_version: Literal[1]
    nodes: list[WorkflowNode] = Field(max_length=2000)
    edges: list[WorkflowEdge] = Field(max_length=2000)
    variables: list[WorkflowVariable] = Field(max_length=2000)

    @field_validator("id")
    @classmethod
    def canonical_uuid(cls, value: str) -> str:
        return str(UUID(value))

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("不支持的工作流格式版本")
        return value

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请填写工作流名称")
        return value


class WorkflowPosition(ApiModel):
    x: float = Field(allow_inf_nan=False, strict=True)
    y: float = Field(allow_inf_nan=False, strict=True)


class WorkflowViewport(WorkflowPosition):
    zoom: float = Field(gt=0, allow_inf_nan=False, strict=True)


class WorkflowLayout(ApiModel):
    nodes: dict[str, WorkflowPosition]
    viewport: WorkflowViewport


class WorkflowIssue(ApiModel):
    node_id: str | None
    path: list[str]
    code: str
    message: str


class WorkflowWrite(ApiModel):
    document: WorkflowDocument
    layout: WorkflowLayout


class WorkflowUpdate(WorkflowWrite):
    expected_revision: int = Field(ge=1, strict=True)


class WorkflowRead(WorkflowWrite):
    revision: int
    created_at: datetime
    updated_at: datetime
    issues: list[WorkflowIssue]


class WorkflowSummary(ApiModel):
    id: str
    name: str
    revision: int
    updated_at: datetime


class WorkflowList(ApiModel):
    items: list[WorkflowSummary]


class WorkflowNodeDefinition(ApiModel):
    type: NodeType
    title: str
    description: str
    category: str
    default_config: dict[str, JsonValue]
    config_schema: dict[str, JsonValue]
    input_ports: list[Literal["in"]]
    output_ports: list[Literal["out"]]
    runnable: bool


class WorkflowCatalog(ApiModel):
    items: list[WorkflowNodeDefinition]
