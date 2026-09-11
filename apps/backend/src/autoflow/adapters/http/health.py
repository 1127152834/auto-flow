from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    apiVersion: str
    instanceId: str


def health_router(*, api_version: str, instance_id: str) -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", apiVersion=api_version, instanceId=instance_id)

    return router
