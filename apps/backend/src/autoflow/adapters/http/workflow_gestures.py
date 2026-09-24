from __future__ import annotations

import asyncio
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException
from pydantic import Field

from autoflow.adapters.http.schemas import ApiModel
from autoflow.infrastructure.gesture import GestureBusyError


class GestureService(Protocol):
    def list_custom_gestures(self) -> list[dict[str, str]]: ...

    def get_status(self) -> dict[str, Any]: ...

    def record_gesture(
        self, gesture_name: str, camera_index: int = 0, timeout: float = 30
    ) -> bool: ...

    def delete_gesture(self, gesture_name: str) -> bool: ...


class RecordGestureRequest(ApiModel):
    gesture_name: str = Field(alias="gesture_name", min_length=1, max_length=100)
    timeout: int = Field(default=30, ge=1, le=300)


def workflow_gesture_router(service: GestureService) -> APIRouter:
    router = APIRouter(prefix="/api/triggers/gesture", tags=["studio-gesture-trigger"])

    @router.get("/status")
    def status() -> dict[str, Any]:
        return {"success": True, "status": service.get_status()}

    @router.get("/custom")
    def custom_gestures() -> dict[str, Any]:
        return {"success": True, "gestures": service.list_custom_gestures()}

    @router.post("/record")
    async def record(request: RecordGestureRequest) -> dict[str, Any]:
        name = request.gesture_name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="手势名称不能为空")
        try:
            success = await asyncio.to_thread(
                service.record_gesture, name, 0, request.timeout
            )
        except GestureBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=500, detail=f"录制手势失败: {error}"
            ) from error
        if not success:
            raise HTTPException(status_code=500, detail="手势录制失败或已取消")
        return {
            "success": True,
            "message": f"手势已录制: {name}",
            "gesture_name": name,
        }

    @router.delete("/custom/{gesture_name}")
    def delete(gesture_name: str) -> dict[str, Any]:
        name = gesture_name.strip()
        if not service.delete_gesture(name):
            raise HTTPException(
                status_code=404, detail=f"自定义手势不存在: {name}"
            )
        return {"success": True, "message": f"已删除自定义手势: {name}"}

    return router
