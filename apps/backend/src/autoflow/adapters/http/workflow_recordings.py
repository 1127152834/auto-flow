from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import Field, JsonValue

from autoflow.application.workflows.recording import RecordingService
from autoflow.domain.workflows.models import WorkflowError

from .errors import browser_error_responses
from .inspection_schemas import InspectionPage, InspectionTest, InspectionTestResult
from .schemas import ApiModel
from .workflow_schemas import WorkflowEdge, WorkflowNode, WorkflowVariable, WorkflowWrite


class RecordingStart(ApiModel):
    recording_id: UUID
    profile_id: str = Field(min_length=1, max_length=120)
    source_document_id: UUID | None = None


class RecordingRead(ApiModel):
    recording_id: str
    profile_id: str
    profile_name: str
    source_document_id: str | None
    browser_state: Literal['starting', 'ready', 'closing', 'closed', 'failed']
    capture_state: Literal['idle', 'recording', 'pausing', 'paused', 'stopping', 'stopped', 'interrupted']
    revision: int
    last_seq: int
    cutoff_seq: int | None
    pages: list[InspectionPage]
    target_page_id: str | None
    segment: int
    issues: list[dict[str, JsonValue]]
    error: str | None
    created_at: str
    updated_at: str


class RecordingList(ApiModel):
    items: list[RecordingRead]
    next_offset: int | None


class RecordingCommand(ApiModel):
    command_id: UUID
    expected_revision: int = Field(ge=1)
    action: Literal['start', 'pause', 'resume', 'stop', 'page', 'close']
    page_id: str | None = Field(default=None, max_length=120)
    url: str | None = Field(default=None, max_length=8192)
    focus: bool = False


class RecordingCommandRead(ApiModel):
    command_id: str
    state: Literal['accepted', 'applied', 'rejected', 'unknown']
    result: dict[str, JsonValue] | None
    error: str | None


class RecordingStep(ApiModel):
    step_id: str
    seq: int
    position: int = 0
    action: str
    page_id: str
    segment: int
    config: dict[str, JsonValue]
    source_event_ids: list[str]
    issues: list[dict[str, JsonValue]]
    label: str
    excluded: bool
    use_variables: bool
    value_ref: str | None = None


class RecordingSteps(ApiModel):
    items: list[RecordingStep]
    next_after: int | None
    revision: int
    last_seq: int


class RecordingStepEdit(ApiModel):
    step_id: str
    config: dict[str, JsonValue] | None = None
    label: str | None = Field(default=None, max_length=120)
    excluded: bool | None = None
    use_variables: bool | None = None


class RecordingEdit(ApiModel):
    expected_revision: int = Field(ge=1)
    changes: list[RecordingStepEdit] = Field(max_length=10000)
    order: list[str] | None = Field(default=None, max_length=10000)


class RecordingGenerate(ApiModel):
    generation_id: UUID
    expected_revision: int = Field(ge=1)
    target: WorkflowWrite


class RecordingGeneration(ApiModel):
    generation_id: str
    recording_revision: int
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    variables: list[WorkflowVariable]
    issues: list[dict[str, JsonValue]]
    coverage_issues: list[dict[str, JsonValue]]
    mapping: dict[str, list[str]]
    aliases: dict[str, str]


def recording_router(service: RecordingService) -> APIRouter:
    router = APIRouter(prefix='/api/v1/workflows/recordings', tags=['workflow-recordings'], responses=browser_error_responses(401, 404, 409, 422, 500, 503))

    @router.post('', response_model=RecordingRead, status_code=201)
    async def start(body: RecordingStart):
        return service.start(str(body.recording_id), body.profile_id, str(body.source_document_id) if body.source_document_id else None)

    @router.get('', response_model=RecordingList)
    def list_recordings(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        items = service.repository.list_records(offset, limit + 1)
        return {'items': items[:limit], 'nextOffset': offset + limit if len(items) > limit else None}

    @router.get('/{identifier}', response_model=RecordingRead)
    def get(identifier: UUID):
        return service.repository.get(str(identifier))

    @router.post('/{identifier}/commands', response_model=RecordingCommandRead, status_code=202)
    async def command(identifier: UUID, body: RecordingCommand):
        if body.url:
            from .inspection_schemas import InspectionPageCommand
            InspectionPageCommand(page_id=body.page_id or '', url=body.url)
        return service.submit(str(identifier), body.model_dump(by_alias=True, mode='json', exclude_none=True))

    @router.get('/{identifier}/commands/{command_id}', response_model=RecordingCommandRead)
    def read_command(identifier: UUID, command_id: UUID):
        service.repository.get(str(identifier))
        value = service.repository.command(str(identifier), str(command_id))
        if value is None:
            raise WorkflowError('RECORDING_COMMAND_NOT_FOUND', '录制命令不存在', 404)
        return value

    @router.get('/{identifier}/steps', response_model=RecordingSteps)
    def steps(identifier: UUID, after_seq: int = Query(0, alias='afterSeq', ge=0), limit: int = Query(50, ge=1, le=100),
              revision: int | None = None, ordered: bool = False):
        record = service.repository.get(str(identifier))
        if revision is not None and revision != record['revision']:
            raise WorkflowError('RECORDING_REVISION_CONFLICT', '审查分页已过期，请重新加载', 409)
        items = service.repository.steps(str(identifier), after_seq, limit + 1, ordered=ordered)
        return {'items': items[:limit], 'nextAfter': items[limit - 1]['position' if ordered else 'seq'] if len(items) > limit else None,
                'lastSeq': record['lastSeq'], 'revision': record['revision']}

    @router.get('/{identifier}/steps/{step_id}/value', response_model=dict[str, JsonValue])
    def value(identifier: UUID, step_id: UUID):
        step = service.repository.step(str(identifier), str(step_id))
        return service.hydrate(str(identifier), step)['config']

    @router.patch('/{identifier}/steps', response_model=RecordingRead)
    def edit(identifier: UUID, body: RecordingEdit):
        return service.edit(str(identifier), body.expected_revision,
                            [item.model_dump(by_alias=True, exclude_none=True) for item in body.changes], body.order)

    @router.post('/{identifier}/generate', response_model=RecordingGeneration)
    def preview(identifier: UUID, body: RecordingGenerate):
        return service.generate(str(identifier), body.model_dump(by_alias=True, mode='json'))

    @router.post('/{identifier}/test-selector', response_model=InspectionTestResult)
    async def test(identifier: UUID, body: InspectionTest):
        return await service.test(str(identifier), body.model_dump(by_alias=True))

    @router.delete('/{identifier}', status_code=204)
    def delete(identifier: UUID):
        service.delete(str(identifier))

    return router
