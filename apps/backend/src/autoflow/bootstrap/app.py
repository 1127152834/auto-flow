from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from autoflow.adapters.http.health import health_router
from autoflow.bootstrap.config import Settings


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.include_router(health_router(api_version=settings.api_version, instance_id=settings.instance_id))

    @app.middleware("http")
    async def authenticate_api(request: Request, call_next):
        if request.url.path.startswith("/api/v1/"):
            if settings.instance_token is None or request.headers.get("x-autoflow-token") != settings.instance_token:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

    return app
