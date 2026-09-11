from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autoflow.adapters.http.model_schemas import (
    ModelDiscoveryRead,
    ModelInput,
    ModelOption,
    ModelOptionListRead,
    ModelProviderConnectInput,
    ModelProviderConnectionUpdateInput,
    ModelProviderCreateInput,
    ModelProviderListRead,
    ModelProviderMetadataUpdateInput,
    ModelProviderRead,
    ModelRead,
    ModelTestInput,
    ModelTestRead,
    RemoteModel,
)


def test_metadata_update_rejects_connection_fields() -> None:
    with pytest.raises(ValidationError):
        ModelProviderMetadataUpdateInput.model_validate(
            {
                "name": "Local",
                "description": "",
                "enabled": True,
                "baseUrl": "http://127.0.0.1:11434/v1",
            }
        )


@pytest.mark.parametrize("value", [-1, 0, 1.0, 1.5, "1", True, 9_007_199_254_740_992])
def test_context_must_be_a_positive_safe_integer(value: object) -> None:
    with pytest.raises(ValidationError):
        ModelInput.model_validate(
            {"modelKey": "sample", "displayName": "Sample", "contextWindow": value}
        )


def test_model_input_normalizes_names_and_tags() -> None:
    model = ModelInput.model_validate(
        {
            "modelKey": " sample ",
            "displayName": " Sample ",
            "tagsJson": [" text ", "", "text", "Text"],
            "contextWindow": 9_007_199_254_740_991,
        }
    )

    assert model.model_key == "sample"
    assert model.display_name == "Sample"
    assert model.tags_json == ["text", "Text"]
    assert model.model_dump(by_alias=True)["contextWindow"] == 9_007_199_254_740_991


def test_connect_rejects_duplicate_trimmed_model_keys_but_keeps_case_distinct() -> None:
    provider = {"name": "Local", "presetId": "ollama"}
    with pytest.raises(ValidationError):
        ModelProviderConnectInput.model_validate(
            {
                "provider": provider,
                "selectedModels": [
                    {"modelKey": "sample", "displayName": "One"},
                    {"modelKey": " sample ", "displayName": "Two"},
                ],
            }
        )

    valid = ModelProviderConnectInput.model_validate(
        {
            "provider": provider,
            "selectedModels": [
                {"modelKey": "sample", "displayName": "One"},
                {"modelKey": "Sample", "displayName": "Two"},
            ],
        }
    )
    assert len(valid.selected_models) == 2


def test_api_key_is_write_only_rejects_null_and_preserves_omitted_empty_semantics() -> None:
    schema = ModelProviderConnectionUpdateInput.model_json_schema(by_alias=True)
    assert schema["properties"]["apiKey"]["writeOnly"] is True

    common = {
        "name": "Local",
        "presetId": "ollama",
        "providerKind": "openai-compatible",
        "baseUrl": "http://127.0.0.1:11434/v1",
        "enabled": True,
        "description": "",
    }
    omitted = ModelProviderConnectionUpdateInput.model_validate(common)
    cleared = ModelProviderConnectionUpdateInput.model_validate({**common, "apiKey": ""})
    replaced = ModelProviderConnectionUpdateInput.model_validate({**common, "apiKey": "  key  "})

    assert "api_key" not in omitted.model_fields_set
    assert "api_key" in cleared.model_fields_set
    assert cleared.api_key.get_secret_value() == ""
    assert replaced.api_key.get_secret_value() == "  key  "
    with pytest.raises(ValidationError):
        ModelProviderConnectionUpdateInput.model_validate({**common, "apiKey": None})
    with pytest.raises(ValidationError):
        ModelProviderCreateInput.model_validate({"name": "Local", "apiKey": None})


def test_api_key_policy_only_allows_empty_for_optional_key_presets() -> None:
    for preset_id in ("ollama", "custom-openai-compatible"):
        created = ModelProviderCreateInput.model_validate(
            {"name": "Local", "presetId": preset_id, "apiKey": ""}
        )
        assert created.api_key.get_secret_value() == ""

    for preset_id in (None, "openai", "unknown"):
        with pytest.raises(ValidationError):
            ModelProviderCreateInput.model_validate(
                {"name": "Local", "presetId": preset_id, "apiKey": " "}
            )

    common = {
        "name": "Local",
        "presetId": "openai",
        "providerKind": "openai",
        "baseUrl": "https://api.openai.com/v1",
        "enabled": True,
        "description": "",
    }
    assert "api_key" not in ModelProviderConnectionUpdateInput.model_validate(
        common
    ).model_fields_set
    with pytest.raises(ValidationError):
        ModelProviderConnectionUpdateInput.model_validate({**common, "apiKey": ""})


def test_all_model_dtos_use_camel_case_and_forbid_extra_fields() -> None:
    now = datetime.now(UTC)
    provider_id = uuid4()
    model_id = uuid4()
    model = ModelRead(
        id=model_id,
        provider_id=provider_id,
        model_key="sample",
        display_name="Sample",
        tags_json=[],
        context_window=None,
        enabled=True,
        description="",
        created_at=now,
        updated_at=now,
    )
    provider = ModelProviderRead(
        id=provider_id,
        name="Local",
        preset_id="ollama",
        provider_kind="openai-compatible",
        base_url="http://127.0.0.1:11434/v1",
        api_key_configured=False,
        enabled=True,
        description="",
        models=[model],
        connection_status="untested",
        last_checked_at=None,
        last_check_latency_ms=None,
        last_check_message=None,
        created_at=now,
        updated_at=now,
    )
    dumped = provider.model_dump(mode="json", by_alias=True)
    assert "apiKeyConfigured" in dumped
    assert "apiKey" not in dumped
    assert "secretRef" not in dumped
    assert "providerId" in dumped["models"][0]

    instances = [
        ModelProviderListRead(items=[provider], total=1),
        RemoteModel(model_key="sample", display_name="Sample"),
        ModelDiscoveryRead(items=[], total=0, latency_ms=1, endpoint="http://local/models", message="ok"),
        ModelTestInput(model_key="sample"),
        ModelTestRead(model_key="sample", latency_ms=1, output_preview="OK", reasoning_preview="", message="ok"),
        ModelOption(id=model_id, provider_id=provider_id, provider_name="Local", model_key="sample", display_name="Sample", tags_json=[]),
        ModelOptionListRead(items=[], total=0),
    ]
    for instance in instances:
        payload = instance.model_dump(mode="json", by_alias=True)
        with pytest.raises(ValidationError):
            type(instance).model_validate({**payload, "unexpected": True})


def test_read_latency_accepts_fractional_non_negative_values() -> None:
    result = ModelDiscoveryRead(
        items=[], total=0, latency_ms=1.5, endpoint="http://local/models", message="ok"
    )
    assert result.latency_ms == 1.5
    with pytest.raises(ValidationError):
        ModelDiscoveryRead(
            items=[], total=0, latency_ms=-0.1, endpoint="http://local/models", message="ok"
        )
