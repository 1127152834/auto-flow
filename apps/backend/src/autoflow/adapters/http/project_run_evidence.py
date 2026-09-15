from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import Response

from autoflow.application.project_runs.evidence import ProjectRunEvidence

from .project_run_evidence_schemas import (
    NodeAttemptPage,
    RunArtifactPage,
    RunArtifactView,
    RunLogPage,
    RunOutputPage,
)


def project_run_evidence_router(evidence: ProjectRunEvidence) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/tasks/{taskId}")

    @router.get("/node-attempts", response_model=NodeAttemptPage)
    def node_attempts(
        projectId: UUID,
        taskId: UUID,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
    ):
        items, total = evidence.node_attempts(
            str(projectId), str(taskId), page=page, page_size=page_size
        )
        return {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": "createdAt",
        }

    @router.get("/logs", response_model=RunLogPage)
    def logs(
        projectId: UUID,
        taskId: UUID,
        after_sequence: Annotated[int, Query(alias="afterSequence", ge=0)] = 0,
        level: Literal["debug", "info", "warning", "error"] | None = None,
        node_id: Annotated[str | None, Query(alias="nodeId")] = None,
        query: Annotated[str | None, Query(max_length=200)] = None,
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
    ):
        return evidence.logs(
            str(projectId),
            str(taskId),
            after_sequence=after_sequence,
            level=level,
            node_id=node_id,
            query=query,
            page_size=page_size,
        )

    @router.get("/outputs", response_model=RunOutputPage)
    def outputs(
        projectId: UUID,
        taskId: UUID,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
    ):
        items, total = evidence.outputs(
            str(projectId), str(taskId), page=page, page_size=page_size
        )
        return {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": "createdAt",
        }

    @router.get("/artifacts", response_model=RunArtifactPage)
    def artifacts(
        projectId: UUID,
        taskId: UUID,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
    ):
        items, total = evidence.artifacts(
            str(projectId), str(taskId), page=page, page_size=page_size
        )
        return {
            "items": [
                _artifact_view(item, str(projectId), str(taskId)) for item in items
            ],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": "createdAt",
        }

    @router.get("/artifacts/{artifactId}", response_model=RunArtifactView)
    def artifact(projectId: UUID, taskId: UUID, artifactId: str):
        item = evidence.artifact(str(projectId), str(taskId), artifactId)
        return _artifact_view(item, str(projectId), str(taskId))

    @router.get("/artifacts/{artifactId}/content", response_class=Response)
    def artifact_content(projectId: UUID, taskId: UUID, artifactId: str):
        content, media_type = evidence.artifact_content(
            str(projectId), str(taskId), artifactId
        )
        return Response(
            content,
            media_type=media_type,
            headers={
                "Cache-Control": "private, immutable",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router


def _artifact_view(item, project_id: str, task_id: str) -> dict[str, object]:
    content_url = None
    if item.availability == "available":
        content_url = (
            f"/api/v1/projects/{project_id}/tasks/{task_id}/artifacts/"
            f"{item.artifact_id}/content"
        )
    return {
        "artifactId": item.artifact_id,
        "kind": item.kind,
        "purpose": item.purpose,
        "availability": item.availability,
        "nodeId": item.node_id,
        "nodeVisitId": item.node_visit_id,
        "eventSequence": item.event_sequence,
        "executionGeneration": item.execution_generation,
        "mediaType": item.media_type,
        "byteSize": item.byte_size,
        "sha256": item.sha256,
        "createdAt": item.created_at,
        "unavailableReason": item.unavailable_reason,
        "contentUrl": content_url,
    }
