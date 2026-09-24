from typing import Annotated, Literal

from pydantic import Field

from .schemas import ApiModel


class SourceDefaultProxy(ApiModel):
    mode: Literal["sourceDefault"]


class NoProxy(ApiModel):
    mode: Literal["none"]


class FixedProxy(ApiModel):
    mode: Literal["fixed"]
    proxy_id: str


class PoolProxy(ApiModel):
    mode: Literal["pool"]
    proxy_pool_id: str


ProjectProxy = Annotated[
    SourceDefaultProxy | NoProxy | FixedProxy | PoolProxy, Field(discriminator="mode")
]

