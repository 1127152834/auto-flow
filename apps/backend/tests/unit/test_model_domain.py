from autoflow.domain.models.models import LocalModelSpec


def test_local_model_spec_normalizes_tags_without_changing_case() -> None:
    spec = LocalModelSpec.from_values(
        model_key=" Model-A ",
        display_name=" Model A ",
        tags_json=[" chat ", "", "Chat", "chat"],
    )

    assert spec.model_key == "Model-A"
    assert spec.display_name == "Model A"
    assert spec.tags_json == ("chat", "Chat")
