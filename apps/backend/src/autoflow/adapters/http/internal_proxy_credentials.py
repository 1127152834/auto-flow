from collections.abc import Callable
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from autoflow.domain.proxies.errors import ProxyError

from .proxy_schemas import ApiError


class CopyCredentialRequest(BaseModel):
    proxy_id: UUID
    protocol: Literal["http", "socks5"]
    format: Literal["username", "password", "url"]


def internal_proxy_credentials_router(resolve: Callable[[CopyCredentialRequest], str]) -> APIRouter:
    router = APIRouter(prefix="/internal/proxy-credentials", include_in_schema=False)

    @router.post("/resolve")
    def resolve_credential(body: CopyCredentialRequest):
        try:
            return JSONResponse({"value": resolve(body)}, headers={"Cache-Control": "no-store"})
        except ProxyError as exc:
            error = ApiError(code=exc.code, message=str(exc), request_id=str(uuid4()))
            return JSONResponse(
                {"error": error.model_dump(mode="json")},
                status_code=404 if exc.code == "RESOURCE_NOT_FOUND" else 503,
                headers={"Cache-Control": "no-store"},
            )

    return router
