from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from .schemas import ApiModel
from .workflow_schemas import WorkflowVariable

Text = Annotated[str, Field(strict=True, min_length=1, max_length=8192)]


class InspectionStart(ApiModel):
    session_id: str
    profile_id: str = Field(strict=True, min_length=1, max_length=120)

    @field_validator('session_id')
    @classmethod
    def identifier(cls, value: str) -> str:
        return str(UUID(value))


class InspectionPage(ApiModel):
    page_id: str
    url: str
    title: str
    revision: int


class InspectionTarget(ApiModel):
    selector: str
    frame_path: list[str]
    positional: bool
    tag: str
    text: str


class InspectionPick(ApiModel):
    request_id: str
    page_id: str
    page_revision: int
    state: Literal['pending', 'selected', 'cancelled', 'failed']
    result: InspectionTarget | None = None
    error: str | None = None


class InspectionRead(ApiModel):
    session_id: str
    profile_id: str
    profile_name: str
    state: Literal['starting', 'ready', 'closing', 'closed', 'failed']
    headless: Literal[False]
    pages: list[InspectionPage]
    target_page_id: str | None
    pick: InspectionPick | None
    error: str | None


class InspectionPageCommand(ApiModel):
    page_id: Text
    url: str | None = Field(default=None, max_length=8192, strict=True)
    focus: bool = False

    @field_validator('url')
    @classmethod
    def http_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or any(c.isspace() for c in parsed.netloc):
            raise ValueError('请输入有效 HTTP/HTTPS 地址')
        _ = parsed.port
        return value


class InspectionPickStart(ApiModel):
    request_id: str
    page_id: Text

    @field_validator('request_id')
    @classmethod
    def identifier(cls, value: str) -> str:
        return str(UUID(value))


class InspectionTest(ApiModel):
    page_id: Text
    selector: Text
    frame_path: list[Text] = Field(default_factory=list, max_length=32)
    variables: list[WorkflowVariable] = Field(default_factory=list, max_length=2000)


class InspectionMatch(ApiModel):
    tag: str
    text: str
    visible: bool


class InspectionTestResult(ApiModel):
    page_id: str
    page_revision: int
    selector: str
    frame_path: list[str]
    count: int
    first: InspectionMatch | None
    truncated: bool
