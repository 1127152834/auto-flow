from fastapi import APIRouter

from autoflow.application.workflows.inspection import InspectionService

from .errors import browser_error_responses
from .inspection_schemas import (
    InspectionPageCommand,
    InspectionPick,
    InspectionPickStart,
    InspectionRead,
    InspectionStart,
    InspectionTest,
    InspectionTestResult,
)


def inspection_router(service: InspectionService) -> APIRouter:
    router = APIRouter(prefix='/api/v1/workflows/inspection-sessions', tags=['workflow-inspection'],
                       responses=browser_error_responses(401, 404, 409, 422, 500, 503))

    @router.post('', response_model=InspectionRead, status_code=201)
    async def start(body: InspectionStart) -> dict:
        return service.start(body.session_id, body.profile_id)

    @router.get('', response_model=InspectionRead | None)
    async def current() -> dict | None:
        return service.current()

    @router.get('/{session_id}', response_model=InspectionRead)
    async def get(session_id: str) -> dict:
        return service.get(session_id)

    @router.post('/{session_id}/page', response_model=InspectionRead)
    async def page(session_id: str, body: InspectionPageCommand) -> dict:
        await service.command(session_id, {'action': 'page', **body.model_dump(by_alias=True)})
        return service.get(session_id)

    @router.post('/{session_id}/picks', response_model=InspectionPick)
    async def pick(session_id: str, body: InspectionPickStart) -> dict:
        return await service.pick(session_id, body.request_id, body.page_id)

    @router.get('/{session_id}/picks/{request_id}', response_model=InspectionPick)
    async def get_pick(session_id: str, request_id: str) -> dict:
        return await service.get_pick(session_id, request_id)

    @router.post('/{session_id}/picks/{request_id}/cancel', response_model=InspectionPick)
    async def cancel(session_id: str, request_id: str) -> dict:
        return await service.cancel(session_id, request_id)

    @router.post('/{session_id}/test-selector', response_model=InspectionTestResult)
    async def test(session_id: str, body: InspectionTest) -> dict:
        return await service.test(session_id, body.page_id, body.selector, body.frame_path,
                                  [v.model_dump(by_alias=True) for v in body.variables])

    @router.post('/{session_id}/close', response_model=InspectionRead)
    async def close(session_id: str) -> dict:
        return await service.close(session_id)

    return router
