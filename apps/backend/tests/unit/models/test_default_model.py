from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.models.service import ModelService
from autoflow.domain.models.errors import ModelError
from autoflow.domain.models.models import LocalModel, LocalModelSpec, ModelProvider
from autoflow.infrastructure.database.model_providers import (
    model_repository_transaction,
)
from tests.fixtures.model_management import FakeCredentialStore
from tests.unit.test_model_service import _profile, _service


class NeverReadCredentials(FakeCredentialStore):
    def read(self, key: str) -> bytes | None:
        raise AssertionError("选择默认模型不应读取系统凭据")


@pytest.fixture
def models(tmp_path: Path) -> Iterator[tuple[ModelService, Any]]:
    service, factory = _service(tmp_path, NeverReadCredentials())
    try:
        yield service, factory
    finally:
        factory.dispose()


def _seed(
    factory: Any,
    provider_id: str,
    name: str,
    models: list[tuple[str, str, bool]],
    *,
    enabled: bool = True,
) -> None:
    provider = replace(
        ModelProvider.create(
            replace(
                _profile(),
                name=name,
                enabled=enabled,
                secret_ref=f"private-reference/{provider_id}",
            )
        ),
        id=provider_id,
    )
    with model_repository_transaction(factory) as repository:
        repository.add_provider(provider)
        for model_id, display_name, model_enabled in models:
            model = replace(
                LocalModel.create(
                    provider_id,
                    LocalModelSpec.from_values(
                        model_id,
                        display_name,
                        enabled=model_enabled,
                    ),
                ),
                id=model_id,
            )
            repository.add_model(model)


def test_default_uses_existing_option_order_within_selected_provider_without_secrets(
    models: tuple[ModelService, Any],
) -> None:
    service, factory = models
    _seed(factory, "other", "A other", [("other-first", "000", True)])
    _seed(
        factory,
        "selected",
        "Z selected",
        [
            ("later", "Zulu", True),
            ("tie-b", "Alpha", True),
            ("disabled", "000", False),
            ("tie-a", "Alpha", True),
        ],
    )
    before = service.list_options()
    assert [item.id for item in before] == ["other-first", "tie-a", "tie-b", "later"]

    assert service.default_model_id("selected") == "tie-a"

    assert service.list_options() == before


def test_missing_provider_keeps_standard_not_found_without_other_provider_fallback(
    models: tuple[ModelService, Any],
) -> None:
    service, factory = models
    _seed(factory, "other", "Other", [("available", "Available", True)])

    with pytest.raises(ModelError) as captured:
        service.default_model_id("missing")

    assert captured.value.code == "MODEL_PROVIDER_NOT_FOUND"
    assert captured.value.status == 404


def test_disabled_provider_keeps_standard_error_without_other_provider_fallback(
    models: tuple[ModelService, Any],
) -> None:
    service, factory = models
    _seed(factory, "other", "Other", [("available", "Available", True)])
    _seed(factory, "disabled", "Disabled", [("model", "Model", True)], enabled=False)

    with pytest.raises(ModelError) as captured:
        service.default_model_id("disabled")

    assert captured.value.code == "MODEL_PROVIDER_DISABLED"
    assert captured.value.status == 409


@pytest.mark.parametrize("only_disabled", [False, True])
def test_no_enabled_models_is_explicit_error_without_other_provider_fallback(
    models: tuple[ModelService, Any],
    only_disabled: bool,
) -> None:
    service, factory = models
    _seed(factory, "other", "Other", [("available", "Available", True)])
    _seed(
        factory,
        "selected",
        "Selected",
        [("disabled", "Disabled", False)] if only_disabled else [],
    )

    with pytest.raises(ModelError) as captured:
        service.default_model_id("selected")

    assert captured.value.code == "PROJECT_DEFAULT_MODEL_UNAVAILABLE"
    assert captured.value.status == 409
