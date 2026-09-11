from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def configure_openapi(app: FastAPI, *, api_version: str) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = get_openapi(
                title="AutoFlow API",
                version=api_version,
                routes=app.routes,
            )
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
