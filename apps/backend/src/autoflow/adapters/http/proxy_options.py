from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from autoflow.domain.profiles.ports import ProxyOptionsLookup

from .errors import browser_error_responses


class ProxyOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    enabled: bool


class PoolOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str


class ProxyOptionsRead(BaseModel):
    proxies: list[ProxyOption]
    pools: list[PoolOption]


def proxy_options_router(options: ProxyOptionsLookup) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1",
        tags=["proxy-options"],
        responses=browser_error_responses(500),
    )

    @router.get("/proxy-options", response_model=ProxyOptionsRead)
    def list_proxy_options() -> ProxyOptionsRead:
        return ProxyOptionsRead(
            proxies=[ProxyOption.model_validate(row) for row in options.list_proxies() if row.enabled],
            pools=[PoolOption.model_validate(row) for row in options.list_pools()],
        )

    return router
