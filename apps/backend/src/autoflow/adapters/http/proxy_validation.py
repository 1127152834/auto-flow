from inspect import isawaitable
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .proxy_schemas import ApiError


def configure_proxy_validation(app: FastAPI) -> None:
    """Never echo credentials or request bodies through validation failures."""
    previous_handler = app.exception_handlers.get(
        RequestValidationError, request_validation_exception_handler
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if not request.url.path.startswith((
            "/api/v1/proxy-panel/", "/api/v1/proxies", "/api/v1/proxy-groups",
            "/internal/proxy-credentials/",
        )):
            response = previous_handler(request, exc)
            return await response if isawaitable(response) else response
        fields = {
            ".".join(str(part) for part in error["loc"][1:]) or "form": ["输入内容不符合要求"]
            for error in exc.errors()
        }
        error = ApiError(
            code="VALIDATION_ERROR", message="请检查表单内容", request_id=str(uuid4()),
            field_errors=fields,
        )
        return JSONResponse(
            {"error": error.model_dump(mode="json")}, status_code=422,
            headers={"Cache-Control": "no-store"},
        )
