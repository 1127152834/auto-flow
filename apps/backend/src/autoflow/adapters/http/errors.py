from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from autoflow.domain.profiles.errors import (
    KernelNotInstalled,
    ProfileDataPathInvalid,
    ProfileDirectoryBusy,
    ProfileNameConflict,
    ProfileNotFound,
    ProfileValidationError,
    ProxyUnavailable,
)


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


def _response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "details": details or {}, "requestId": str(uuid4())}},
        status_code=status_code,
    )


def _domain_validation_field(message: str) -> str:
    if message.startswith("Public edition"):
        return "releaseChannel"
    if message.startswith("expert argument"):
        return "expertArgsJson"
    field = message.split(maxsplit=1)[0]
    return _camel({"viewport": "viewport_json"}.get(field, field))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        fields: dict[str, str] = {}
        for issue in error.errors():
            location = issue["loc"]
            message = str(issue["msg"])
            if len(location) > 1:
                field = str(location[1])
            elif "proxyId" in message:
                field = "proxyId"
            elif "proxyPoolId" in message:
                field = "proxyPoolId"
            else:
                field = "form"
            fields[field] = message
        return _response(422, "VALIDATION_ERROR", "Request validation failed", {"fields": fields})

    @app.exception_handler(ProfileValidationError)
    async def profile_validation_error(
        _request: Request, error: ProfileValidationError
    ) -> JSONResponse:
        message = str(error)
        field = _domain_validation_field(message)
        return _response(422, "VALIDATION_ERROR", "Request validation failed", {"fields": {field: message}})

    mappings: list[tuple[type[Exception], int, str, str]] = [
        (ProfileNotFound, 404, "PROFILE_NOT_FOUND", "Browser profile was not found"),
        (ProfileNameConflict, 409, "PROFILE_NAME_CONFLICT", "Profile name is already in use"),
        (ProfileDirectoryBusy, 409, "PROFILE_DIRECTORY_BUSY", "Profile data directory is busy"),
        (KernelNotInstalled, 409, "KERNEL_NOT_INSTALLED", "Selected browser kernel is not installed"),
        (ProxyUnavailable, 409, "PROXY_UNAVAILABLE", "Selected proxy resource is unavailable"),
        (ProfileDataPathInvalid, 500, "PROFILE_DATA_PATH_INVALID", "Managed profile data path is invalid"),
    ]
    for exception_type, status, code, message in mappings:
        def handler(
            _request: Request,
            _error: Exception,
            *,
            status: int = status,
            code: str = code,
            message: str = message,
        ) -> JSONResponse:
            return _response(status, code, message)

        app.add_exception_handler(exception_type, handler)  # type: ignore[arg-type]

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, _error: Exception) -> JSONResponse:
        return _response(500, "INTERNAL_ERROR", "Internal server error")
