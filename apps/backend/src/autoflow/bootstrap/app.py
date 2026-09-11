from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from autoflow.adapters.http.health import health_router
from autoflow.adapters.http.openapi import configure_openapi
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.filesystem.paths import AppPaths


def create_app(settings: Settings) -> FastAPI:
    paths = AppPaths.from_data_dir(Path(settings.data_dir))
    for directory in (paths.database.parent, paths.logs, paths.workspace, paths.cache, paths.temp):
        directory.mkdir(parents=True, exist_ok=True)

    app = FastAPI()
    configure_openapi(app, api_version=settings.api_version)
    app.state.paths = paths
    app.include_router(health_router(api_version=settings.api_version, instance_id=settings.instance_id))

    @app.middleware("http")
    async def authenticate_api(request: Request, call_next):
        if request.url.path.startswith("/api/v1/") and (
            settings.instance_token is None or request.headers.get("x-autoflow-token") != settings.instance_token
        ):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

    return app
