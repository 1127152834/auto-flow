from fastapi import APIRouter


def health_router(*, api_version: str, instance_id: str) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "apiVersion": api_version, "instanceId": instance_id}

    return router
