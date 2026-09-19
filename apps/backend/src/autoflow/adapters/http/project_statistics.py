from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from autoflow.application.projects.statistics import ProjectStatisticsService

from .errors import browser_error_responses
from .project_run_schemas import TaskPage
from .project_statistics_schemas import ProjectStatistics


def project_statistics_router(statistics: ProjectStatisticsService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.get(
        "/statistics",
        response_model=ProjectStatistics,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def project_statistics(
        projectId: UUID,
        from_: Annotated[datetime | None, Query(alias="from")] = None,
        to: datetime | None = None,
        timezone: str | None = None,
        automationId: UUID | None = None,
        tableId: UUID | None = None,
        interval: Literal["day", "week", "month"] = "day",
    ):
        return statistics.get(
            str(projectId),
            from_=from_,
            to=to,
            timezone=timezone,
            automation_id=str(automationId) if automationId else None,
            table_id=str(tableId) if tableId else None,
            interval=interval,
        )

    @router.get(
        "/statistics/{resultSetId}/tasks",
        response_model=TaskPage,
        responses=browser_error_responses(401, 404, 409, 410, 422),
    )
    def statistics_tasks(
        projectId: UUID,
        resultSetId: str,
        result: Literal["succeeded", "failed", "cancelled", "timed_out", "interrupted"],
        intervalStart: datetime | None = None,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        sort: str = "-createdAt",
    ):
        items, total = statistics.tasks(
            str(projectId),
            resultSetId,
            result=result,
            interval_start=intervalStart,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        return {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": sort,
        }

    return router
