from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
from autoflow.domain.models.errors import ModelError
from autoflow.domain.profiles.errors import (
    KernelNotInstalled,
    ProfileDataPathInvalid,
    ProfileDirectoryBusy,
    ProfileNameConflict,
    ProfileNotFound,
    ProfileValidationError,
    ProxyUnavailable,
)

_MODEL_ERROR_MESSAGES = {
    "VALIDATION_ERROR": "Request validation failed",
    "MODEL_PROVIDER_NOT_FOUND": "Model provider was not found",
    "MODEL_NOT_FOUND": "Model was not found",
    "MODEL_PROVIDER_EXISTS": "Model provider already exists",
    "MODEL_EXISTS": "Model already exists",
    "MODEL_PROVIDER_CHANGED": "Model provider changed during the request",
    "MODEL_PROVIDER_MODEL_NOT_DISCOVERED": "Selected model was not discovered",
    "MODEL_PROVIDER_ENDPOINT_NOT_FOUND": "Model provider endpoint was not found",
    "MODEL_PROVIDER_AUTH_FAILED": "Model provider authentication failed",
    "MODEL_PROVIDER_RATE_LIMITED": "Model provider rate limit was reached",
    "MODEL_PROVIDER_REQUEST_FAILED": "Model provider request failed",
    "MODEL_PROVIDER_RESPONSE_INVALID": "Model provider response was invalid",
    "MODEL_PROVIDER_UNREACHABLE": "Model provider is unreachable",
    "MODEL_PROVIDER_BASE_URL_REQUIRED": "Model provider base URL is required",
    "MODEL_PROVIDER_API_KEY_REQUIRED": "Model provider API key is required",
    "MODEL_PROVIDER_BASE_URL_INVALID": "Model provider base URL is invalid",
    "CREDENTIAL_STORE_UNAVAILABLE": "Credential store is unavailable",
    "MODEL_PROVIDER_TIMEOUT": "Model provider request timed out",
}


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


def error_response(
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


def _safe_model_details(details: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    fields = details.get("fields")
    if isinstance(fields, dict):
        safe["fields"] = {str(field): "Invalid value" for field in fields}
    model_keys = details.get("modelKeys")
    if isinstance(model_keys, list) and all(isinstance(value, str) for value in model_keys):
        safe["modelKeys"] = model_keys
    retry_after = details.get("retryAfterSeconds")
    if isinstance(retry_after, int) and not isinstance(retry_after, bool) and retry_after >= 0:
        safe["retryAfterSeconds"] = retry_after
    status = details.get("status")
    if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
        safe["status"] = status
    return safe


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        fields: dict[str, str] = {}
        api_key_required = False
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
            api_key_required = api_key_required or issue["type"] == "model_provider_api_key_required"
        if api_key_required:
            return error_response(
                422,
                "MODEL_PROVIDER_API_KEY_REQUIRED",
                "Model provider API key is required",
                {"fields": {"apiKey": "API key is required"}},
            )
        return error_response(422, "VALIDATION_ERROR", "Request validation failed", {"fields": fields})

    @app.exception_handler(ProfileValidationError)
    async def profile_validation_error(
        _request: Request, error: ProfileValidationError
    ) -> JSONResponse:
        message = str(error)
        field = _domain_validation_field(message)
        return error_response(422, "VALIDATION_ERROR", "Request validation failed", {"fields": {field: message}})

    @app.exception_handler(ModelError)
    async def model_error(_request: Request, error: ModelError) -> JSONResponse:
        return error_response(
            error.status,
            error.code,
            _MODEL_ERROR_MESSAGES.get(error.code, "Model operation failed"),
            _safe_model_details(error.details),
        )

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
            return error_response(status, code, message)

        app.add_exception_handler(exception_type, handler)  # type: ignore[arg-type]

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, _error: Exception) -> JSONResponse:
        return error_response(500, "INTERNAL_ERROR", "Internal server error")
