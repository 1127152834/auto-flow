from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from autoflow.domain.models import ModelError, ProviderConnection
from autoflow.domain.models.models import ModelInvocationResult

from .http import HttpModelProvider


class WorkflowModelGateway:
    def __init__(
        self,
        bindings: Sequence[Mapping[str, Any]],
        provider: HttpModelProvider | None = None,
    ) -> None:
        self._provider = provider or HttpModelProvider()
        self._bindings: dict[
            str, tuple[ProviderConnection, str, str]
        ] = {}
        for raw in bindings:
            required = ("modelId", "modelKey", "providerKind", "secret")
            if any(not isinstance(raw.get(key), str) for key in required):
                raise ValueError("model binding is invalid")
            model_id = str(raw["modelId"])
            if not model_id or model_id in self._bindings:
                raise ValueError("model binding is invalid")
            preset_id = raw.get("presetId")
            base_url = raw.get("baseUrl")
            if preset_id is not None and not isinstance(preset_id, str):
                raise ValueError("model binding is invalid")
            if base_url is not None and not isinstance(base_url, str):
                raise ValueError("model binding is invalid")
            self._bindings[model_id] = (
                ProviderConnection(preset_id, str(raw["providerKind"]), base_url),
                str(raw["secret"]),
                str(raw["modelKey"]),
            )

    async def invoke(
        self, model_id: str, payload: Mapping[str, Any]
    ) -> ModelInvocationResult:
        binding = self._bindings.get(model_id)
        if binding is None:
            raise ModelError(
                "MODEL_NOT_AVAILABLE_FOR_RUN", "运行快照中没有所选模型", 409
            )
        connection, secret, model_key = binding
        return await self._provider.invoke(connection, secret, model_key, payload)
