from dataclasses import replace
from datetime import timedelta

from autoflow.domain.models.models import (
    LocalModel,
    LocalModelSpec,
    ModelProvider,
    ProviderProfile,
)
from autoflow.infrastructure.database.model_providers import (
    model_repository_transaction,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def test_repository_commits_provider_and_models_atomically(tmp_path) -> None:
    database = tmp_path / "model.db"
    migrate_database(database)
    factory = create_session_factory(database)
    provider = ModelProvider.create(
        ProviderProfile(
            "Provider",
            "ollama",
            "openai-compatible",
            "http://localhost:11434/v1",
            None,
            True,
            "",
        )
    )
    model = LocalModel.create(provider.id, LocalModelSpec.from_values("m-1", "M 1"))

    with model_repository_transaction(factory) as repository:
        repository.add_provider(provider)
        repository.add_model(model)

    with model_repository_transaction(factory) as repository:
        loaded = repository.get_provider(provider.id)
        assert loaded is not None
        assert [item.model_key for item in loaded.models] == ["m-1"]
    factory.dispose()


def test_provider_cas_is_an_atomic_conditional_update(tmp_path) -> None:
    database = tmp_path / "cas.db"
    migrate_database(database)
    factory = create_session_factory(database)
    provider = ModelProvider.create(
        ProviderProfile(
            "Original",
            "ollama",
            "openai-compatible",
            "http://localhost:11434/v1",
            None,
            True,
            "",
        )
    )
    with model_repository_transaction(factory) as repository:
        repository.add_provider(provider)
    with model_repository_transaction(factory) as repository:
        first_snapshot = repository.get_provider(provider.id)
    with model_repository_transaction(factory) as repository:
        second_snapshot = repository.get_provider(provider.id)
    assert first_snapshot is not None and second_snapshot is not None
    first = replace(
        first_snapshot,
        profile=replace(first_snapshot.profile, name="First"),
        updated_at=first_snapshot.updated_at + timedelta(seconds=1),
    )
    second = replace(
        second_snapshot,
        profile=replace(second_snapshot.profile, name="Second"),
        updated_at=second_snapshot.updated_at + timedelta(seconds=2),
    )
    with model_repository_transaction(factory) as repository:
        assert repository.update_provider(first, first_snapshot.updated_at)
    with model_repository_transaction(factory) as repository:
        assert not repository.update_provider(second, second_snapshot.updated_at)
    with model_repository_transaction(factory) as repository:
        assert repository.get_provider(provider.id).name == "First"


def test_provider_base_url_query_round_trips_without_mutation(tmp_path) -> None:
    database = tmp_path / "query.db"
    migrate_database(database)
    factory = create_session_factory(database)
    provider = ModelProvider.create(
        ProviderProfile(
            "Query",
            "ollama",
            "openai-compatible",
            "https://example.test/v1?prefix=/",
            None,
            True,
            "",
        )
    )
    with model_repository_transaction(factory) as repository:
        repository.add_provider(provider)
    with model_repository_transaction(factory) as repository:
        assert (
            repository.get_provider(provider.id).base_url
            == "https://example.test/v1?prefix=/"
        )
