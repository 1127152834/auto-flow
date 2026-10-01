from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from autoflow.application.settings.execution import (
    AppSettingConflict,
    ExecutionSettingsService,
    ExecutionSettingsView,
)
from autoflow.domain.settings.execution_capacity import GIB, MAX_RUNNING_BROWSERS

from .errors import browser_error_responses, error_response


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


class HardwareRead(_Model):
    logical_cpus: int
    total_memory_gb: float


class ExecutionSettingsRead(_Model):
    max_running_browsers: int | None
    recommended_max_running_browsers: int
    effective_max_running_browsers: int
    max_live_browsers: int
    memory_pressure: bool
    hardware: HardwareRead
    revision: int

    @classmethod
    def from_view(cls, view: ExecutionSettingsView) -> "ExecutionSettingsRead":
        capacity = view.capacity
        return cls(
            max_running_browsers=capacity.configured,
            recommended_max_running_browsers=capacity.recommended,
            effective_max_running_browsers=capacity.effective,
            max_live_browsers=capacity.live,
            memory_pressure=view.memory_pressure,
            hardware=HardwareRead(
                logical_cpus=view.hardware.logical_cpus,
                total_memory_gb=round(view.hardware.total_memory_bytes / GIB, 1),
            ),
            revision=view.revision,
        )


class ExecutionSettingsWrite(_Model):
    max_running_browsers: StrictInt | None = Field(ge=1, le=MAX_RUNNING_BROWSERS)
    expected_revision: StrictInt = Field(ge=0)


def execution_settings_router(service: ExecutionSettingsService) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/settings/execution",
        tags=["settings"],
        responses=browser_error_responses(409, 422, 500, 503),
    )

    @router.get("", response_model=ExecutionSettingsRead, response_model_by_alias=True)
    async def get_execution_settings(response: Response) -> ExecutionSettingsRead:
        response.headers["Cache-Control"] = "no-store"
        return ExecutionSettingsRead.from_view(await service.read())

    @router.put("", response_model=ExecutionSettingsRead, response_model_by_alias=True)
    async def put_execution_settings(body: ExecutionSettingsWrite, response: Response) -> Any:
        response.headers["Cache-Control"] = "no-store"
        try:
            view = await service.update(body.max_running_browsers, body.expected_revision)
        except AppSettingConflict as conflict:
            return error_response(
                409,
                "SETTINGS_REVISION_CONFLICT",
                "设置已被其他操作修改，请刷新后重试",
                {"currentRevision": conflict.current_revision},
            )
        return ExecutionSettingsRead.from_view(view)

    return router
