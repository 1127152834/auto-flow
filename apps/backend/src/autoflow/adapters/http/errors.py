from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from autoflow.domain.kernels.errors import (
    KernelBusy,
    KernelCredentialStoreUnavailable,
    KernelDefaultConflict,
    KernelNotFound,
    KernelOperationNotFound,
    KernelPathInvalid,
    KernelPlatformUnsupported,
    KernelVersionInvalid,
    KernelWorkerUnavailable,
    LicenseInUse,
    LicenseInvalid,
    LicenseValidationUnavailable,
)
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


class BrowserApiError(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class BrowserErrorEnvelope(BaseModel):
    error: BrowserApiError


def browser_error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    return {status_code: {"model": BrowserErrorEnvelope} for status_code in status_codes}


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
        (KernelNotFound, 404, "KERNEL_NOT_FOUND", "Installed kernel was not found"),
        (KernelOperationNotFound, 404, "KERNEL_OPERATION_NOT_FOUND", "Kernel operation was not found"),
        (KernelDefaultConflict, 409, "KERNEL_DEFAULT_CONFLICT", "Default kernel revision is stale"),
        (KernelBusy, 409, "KERNEL_BUSY", "A kernel installation is already active"),
        (LicenseInUse, 409, "LICENSE_IN_USE", "CloakBrowser license is in use"),
        (KernelVersionInvalid, 422, "KERNEL_VERSION_INVALID", "CloakBrowser version is invalid"),
        (LicenseInvalid, 422, "LICENSE_INVALID", "CloakBrowser license is invalid or expired"),
        (KernelPlatformUnsupported, 422, "KERNEL_PLATFORM_UNSUPPORTED", "CloakBrowser is unavailable on this platform"),
        (KernelCredentialStoreUnavailable, 503, "CREDENTIAL_STORE_UNAVAILABLE", "System credential storage is unavailable"),
        (LicenseValidationUnavailable, 503, "LICENSE_VALIDATION_UNAVAILABLE", "CloakBrowser license validation is unavailable"),
        (KernelWorkerUnavailable, 503, "KERNEL_WORKER_ERROR", "Kernel worker is unavailable"),
        (KernelPathInvalid, 500, "KERNEL_PATH_INVALID", "Managed kernel path is invalid"),
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
