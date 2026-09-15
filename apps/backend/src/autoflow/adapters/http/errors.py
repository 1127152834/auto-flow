from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
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
from autoflow.domain.models.errors import ModelError
from autoflow.domain.profiles.errors import (
    KernelNotInstalled,
    ProfileDataPathInvalid,
    ProfileDirectoryBusy,
    ProfileNameConflict,
    ProfileNotFound,
    ProfileTestBrowserBusy,
    ProfileTestBrowserUnavailable,
    ProfileValidationError,
    ProxyUnavailable,
)
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.errors import WorkflowDocumentError
from autoflow.domain.workflows.runs import WorkflowRunError

_MODEL_ERROR_MESSAGES = {
    "VALIDATION_ERROR": "请求参数无效",
    "MODEL_PROVIDER_NOT_FOUND": "模型供应商不存在",
    "MODEL_NOT_FOUND": "模型不存在",
    "MODEL_PROVIDER_EXISTS": "模型供应商已存在",
    "MODEL_EXISTS": "模型已存在",
    "MODEL_PROVIDER_CHANGED": "模型供应商已被修改，请刷新后重试",
    "MODEL_PROVIDER_MODEL_NOT_DISCOVERED": "所选模型不在供应商目录中",
    "MODEL_PROVIDER_ENDPOINT_NOT_FOUND": "供应商接口不存在，请检查服务地址或模型标识",
    "MODEL_PROVIDER_AUTH_FAILED": "供应商认证失败，请检查 API Key",
    "MODEL_PROVIDER_RATE_LIMITED": "供应商触发限流或额度限制，请稍后重试",
    "MODEL_PROVIDER_REQUEST_FAILED": "供应商请求失败",
    "MODEL_PROVIDER_RESPONSE_INVALID": "供应商返回了无效响应",
    "MODEL_PROVIDER_UNREACHABLE": "无法连接模型供应商，请检查网络或服务地址",
    "MODEL_PROVIDER_BASE_URL_REQUIRED": "请输入供应商服务地址",
    "MODEL_PROVIDER_API_KEY_REQUIRED": "请输入供应商 API Key",
    "MODEL_PROVIDER_BASE_URL_INVALID": "供应商服务地址无效",
    "CREDENTIAL_STORE_UNAVAILABLE": "系统凭据存储当前不可用",
    "MODEL_PROVIDER_TIMEOUT": "供应商请求超时，请稍后重试",
}


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
    return {
        status_code: {"model": BrowserErrorEnvelope} for status_code in status_codes
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "requestId": str(uuid4()),
            }
        },
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
    if isinstance(model_keys, list) and all(
        isinstance(value, str) for value in model_keys
    ):
        safe["modelKeys"] = model_keys
    retry_after = details.get("retryAfterSeconds")
    if (
        isinstance(retry_after, int)
        and not isinstance(retry_after, bool)
        and retry_after >= 0
    ):
        safe["retryAfterSeconds"] = retry_after
    status = details.get("status")
    if (
        isinstance(status, int)
        and not isinstance(status, bool)
        and 100 <= status <= 599
    ):
        safe["status"] = status
    return safe


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(WorkflowDocumentError)
    async def workflow_document_error(
        _request: Request, error: WorkflowDocumentError
    ) -> JSONResponse:
        return error_response(
            error.status, error.code, error.message, jsonable_encoder(error.details)
        )

    @app.exception_handler(WorkflowRunError)
    async def workflow_run_error(
        _request: Request, error: WorkflowRunError
    ) -> JSONResponse:
        return error_response(
            error.status, error.code, error.message, jsonable_encoder(error.details)
        )

    @app.exception_handler(ProjectError)
    async def project_error(_request: Request, error: ProjectError) -> JSONResponse:
        details = dict(error.details)
        details.setdefault("domainCode", error.code.lower())
        details.setdefault("retryable", False)
        return error_response(
            error.status, error.code, error.message, jsonable_encoder(details)
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        if _request.url.path.startswith(
            "/api/v1/projects"
        ) or _request.url.path.startswith("/api/v1/workspace/operations"):
            project_fields = {}
            for issue in error.errors():
                location = issue["loc"]
                project_fields[str(location[-1]) if location else "form"] = str(
                    issue["msg"]
                )
            return error_response(
                422,
                "VALIDATION_ERROR",
                "Request validation failed",
                {
                    "fields": project_fields,
                    "domainCode": "validation_error",
                    "retryable": False,
                },
            )
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
            api_key_required = (
                api_key_required or issue["type"] == "model_provider_api_key_required"
            )
        if api_key_required:
            return error_response(
                422,
                "MODEL_PROVIDER_API_KEY_REQUIRED",
                "Model provider API key is required",
                {"fields": {"apiKey": "API key is required"}},
            )
        return error_response(
            422, "VALIDATION_ERROR", "Request validation failed", {"fields": fields}
        )

    @app.exception_handler(ProfileValidationError)
    async def profile_validation_error(
        _request: Request, error: ProfileValidationError
    ) -> JSONResponse:
        message = str(error)
        field = _domain_validation_field(message)
        return error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            {"fields": {field: message}},
        )

    @app.exception_handler(ModelError)
    async def model_error(_request: Request, error: ModelError) -> JSONResponse:
        message = _MODEL_ERROR_MESSAGES.get(error.code, "模型操作失败")
        if (
            error.code == "MODEL_PROVIDER_REQUEST_FAILED"
            and error.details.get("status") == 402
        ):
            message = "供应商余额或额度不足，请充值或调整额度后重试"
        return error_response(
            error.status,
            error.code,
            message,
            _safe_model_details(error.details),
        )

    @app.exception_handler(ProfileNameConflict)
    async def profile_name_conflict(
        _request: Request, _error: ProfileNameConflict
    ) -> JSONResponse:
        message = "Profile name is already in use"
        return error_response(
            409, "PROFILE_NAME_CONFLICT", message, {"fields": {"name": message}}
        )

    mappings: list[tuple[type[Exception], int, str, str]] = [
        (ProfileNotFound, 404, "PROFILE_NOT_FOUND", "Browser profile was not found"),
        (
            ProfileDirectoryBusy,
            409,
            "PROFILE_DIRECTORY_BUSY",
            "Profile data directory is busy",
        ),
        (
            KernelNotInstalled,
            409,
            "KERNEL_NOT_INSTALLED",
            "Selected browser kernel is not installed",
        ),
        (
            ProxyUnavailable,
            409,
            "PROXY_UNAVAILABLE",
            "Selected proxy resource is unavailable",
        ),
        (
            ProfileTestBrowserBusy,
            409,
            "PROFILE_TEST_BROWSER_BUSY",
            "此配置的测试浏览器正在运行或切换状态",
        ),
        (
            ProfileTestBrowserUnavailable,
            503,
            "PROFILE_TEST_BROWSER_UNAVAILABLE",
            "测试浏览器启动失败，请检查内核与配置后重试",
        ),
        (
            ProfileDataPathInvalid,
            500,
            "PROFILE_DATA_PATH_INVALID",
            "Managed profile data path is invalid",
        ),
        (KernelNotFound, 404, "KERNEL_NOT_FOUND", "Installed kernel was not found"),
        (
            KernelOperationNotFound,
            404,
            "KERNEL_OPERATION_NOT_FOUND",
            "Kernel operation was not found",
        ),
        (
            KernelDefaultConflict,
            409,
            "KERNEL_DEFAULT_CONFLICT",
            "Default kernel revision is stale",
        ),
        (KernelBusy, 409, "KERNEL_BUSY", "A kernel installation is already active"),
        (LicenseInUse, 409, "LICENSE_IN_USE", "CloakBrowser license is in use"),
        (
            KernelVersionInvalid,
            422,
            "KERNEL_VERSION_INVALID",
            "CloakBrowser version is invalid",
        ),
        (
            LicenseInvalid,
            422,
            "LICENSE_INVALID",
            "CloakBrowser license is invalid or expired",
        ),
        (
            KernelPlatformUnsupported,
            422,
            "KERNEL_PLATFORM_UNSUPPORTED",
            "CloakBrowser is unavailable on this platform",
        ),
        (
            KernelCredentialStoreUnavailable,
            503,
            "CREDENTIAL_STORE_UNAVAILABLE",
            "System credential storage is unavailable",
        ),
        (
            LicenseValidationUnavailable,
            503,
            "LICENSE_VALIDATION_UNAVAILABLE",
            "CloakBrowser license validation is unavailable",
        ),
        (
            KernelWorkerUnavailable,
            503,
            "KERNEL_WORKER_ERROR",
            "Kernel worker is unavailable",
        ),
        (
            KernelPathInvalid,
            500,
            "KERNEL_PATH_INVALID",
            "Managed kernel path is invalid",
        ),
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
