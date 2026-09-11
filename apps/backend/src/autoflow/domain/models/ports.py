from typing import Protocol

from .models import DiscoveryResult, ModelTestResult, ProviderConnection


class ModelGateway(Protocol):
    async def discover(self, connection: ProviderConnection, secret: str) -> DiscoveryResult: ...

    async def test_model(
        self, connection: ProviderConnection, secret: str, model_key: str
    ) -> ModelTestResult: ...
