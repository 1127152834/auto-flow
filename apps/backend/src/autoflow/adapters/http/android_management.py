from fastapi import APIRouter

from autoflow.application.android.diagnostics import (
    EnvironmentCheckResult,
    EnvironmentCheckService,
)

from .android_management_schemas import (
    ManagementCapabilitiesRead,
    ManagementEnvironmentRead,
)


def _environment_response(result: EnvironmentCheckResult) -> ManagementEnvironmentRead:
    legacy = result.legacy
    platform = result.checks["platform"]
    return ManagementEnvironmentRead(
        available=result.capabilities.get("management") is True,
        platform_supported=platform.status == "pass" if platform.status in {"pass", "unsupported"} else None,
        runtime_id=result.runtime_id,
        message=str(legacy.get("message") or platform.message),
        images=list(legacy.get("images") or []),
        cpu_count=int(legacy.get("cpuCount") or 0),
        memory_mb=int(legacy.get("memoryMb") or legacy.get("memoryMB") or 0),
        checked_at=result.checked_at,
        checks={name: check.__dict__ for name, check in result.checks.items()},
        capabilities=result.capabilities,
    )


def android_management_router(check_service: EnvironmentCheckService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/android/management", tags=["android-management"])

    @router.get("/environment", response_model=ManagementEnvironmentRead)
    async def environment() -> ManagementEnvironmentRead:
        return _environment_response(await check_service.check("management-environment"))

    @router.get("/capabilities", response_model=ManagementCapabilitiesRead)
    async def capabilities() -> ManagementCapabilitiesRead:
        result = await check_service.check("management-capabilities")
        return ManagementCapabilitiesRead(
            management=result.capabilities.get("management", "unknown"),
            control=result.capabilities.get("control", "unknown"),
            images=result.capabilities.get("images", "unknown"),
            bulk=False,
            backups=False,
            workflow=False,
            reasons={
                "bulk": "AM3 尚未启用",
                "backups": "AM4 尚未启用",
                "workflow": "安卓管理不通过工作流执行入口",
            },
        )

    return router
