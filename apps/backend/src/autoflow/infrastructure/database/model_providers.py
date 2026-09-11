from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from autoflow.domain.models.errors import ModelError
from autoflow.domain.models.models import (
    LocalModel,
    LocalModelSpec,
    ModelOptionRecord,
    ModelProvider,
    ProviderProfile,
    utc_now,
)

from .models import LocalModelRow, ModelCredentialCleanupRow, ModelProviderRow


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class SqlAlchemyModelRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_providers(self) -> list[ModelProvider]:
        rows = self.session.scalars(
            select(ModelProviderRow)
            .options(selectinload(ModelProviderRow.models))
            .order_by(ModelProviderRow.created_at, ModelProviderRow.id)
        ).all()
        return [self._provider(row) for row in rows]

    def get_provider(self, provider_id: str) -> ModelProvider | None:
        row = self.session.scalar(
            select(ModelProviderRow)
            .where(ModelProviderRow.id == provider_id)
            .options(selectinload(ModelProviderRow.models))
        )
        return self._provider(row) if row else None

    def get_provider_by_name(self, name: str) -> ModelProvider | None:
        row = self.session.scalar(
            select(ModelProviderRow)
            .where(ModelProviderRow.name == name)
            .options(selectinload(ModelProviderRow.models))
        )
        return self._provider(row) if row else None

    def add_provider(self, provider: ModelProvider) -> None:
        self.session.add(
            ModelProviderRow(
                id=provider.id,
                name=provider.name,
                preset_id=provider.preset_id,
                provider_kind=provider.provider_kind,
                base_url=provider.base_url,
                secret_ref=provider.secret_ref,
                enabled=provider.enabled,
                description=provider.description,
                connection_status=provider.connection_status,
                last_checked_at=provider.last_checked_at,
                last_check_latency_ms=provider.last_check_latency_ms,
                last_check_message=provider.last_check_message,
                created_at=provider.created_at,
                updated_at=provider.updated_at,
            )
        )

    def update_provider(
        self, provider: ModelProvider, expected_updated_at: datetime | None = None
    ) -> bool:
        statement = update(ModelProviderRow).where(ModelProviderRow.id == provider.id)
        if expected_updated_at is not None:
            statement = statement.where(
                ModelProviderRow.updated_at == expected_updated_at
            )
        result = cast(
            CursorResult[Any],
            self.session.execute(
                statement.values(
                    name=provider.name,
                    preset_id=provider.preset_id,
                    provider_kind=provider.provider_kind,
                    base_url=provider.base_url,
                    secret_ref=provider.secret_ref,
                    enabled=provider.enabled,
                    description=provider.description,
                    connection_status=provider.connection_status,
                    last_checked_at=provider.last_checked_at,
                    last_check_latency_ms=provider.last_check_latency_ms,
                    last_check_message=provider.last_check_message,
                    updated_at=provider.updated_at,
                ).execution_options(synchronize_session=False)
            ),
        )
        return result.rowcount == 1

    def remove_provider(
        self, provider_id: str, expected_updated_at: datetime | None = None
    ) -> bool:
        statement = delete(ModelProviderRow).where(ModelProviderRow.id == provider_id)
        if expected_updated_at is not None:
            statement = statement.where(
                ModelProviderRow.updated_at == expected_updated_at
            )
        result = cast(
            CursorResult[Any],
            self.session.execute(
                statement.execution_options(synchronize_session=False)
            ),
        )
        return result.rowcount == 1

    def get_model(self, model_id: str) -> LocalModel | None:
        row = self.session.get(LocalModelRow, model_id)
        return self._model(row) if row else None

    def get_model_by_key(self, provider_id: str, model_key: str) -> LocalModel | None:
        row = self.session.scalar(
            select(LocalModelRow).where(
                LocalModelRow.provider_id == provider_id,
                LocalModelRow.model_key == model_key,
            )
        )
        return self._model(row) if row else None

    def add_model(self, model: LocalModel) -> None:
        self.session.add(
            LocalModelRow(
                id=model.id,
                provider_id=model.provider_id,
                model_key=model.model_key,
                display_name=model.display_name,
                tags_json=model.tags_json,
                context_window=model.context_window,
                enabled=model.enabled,
                description=model.description,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
        )

    def update_model(self, model: LocalModel) -> None:
        row = self.session.get(LocalModelRow, model.id)
        if row:
            row.display_name, row.tags_json, row.context_window = (
                model.display_name,
                model.tags_json,
                model.context_window,
            )
            row.enabled, row.description, row.updated_at = (
                model.enabled,
                model.description,
                model.updated_at,
            )

    def remove_model(self, model_id: str) -> bool:
        row = self.session.get(LocalModelRow, model_id)
        if not row:
            return False
        self.session.delete(row)
        return True

    def list_options(self) -> list[ModelOptionRecord]:
        rows = self.session.execute(
            select(LocalModelRow, ModelProviderRow)
            .join(ModelProviderRow)
            .where(LocalModelRow.enabled.is_(True), ModelProviderRow.enabled.is_(True))
            .order_by(
                ModelProviderRow.name, LocalModelRow.display_name, LocalModelRow.id
            )
        ).all()
        return [
            ModelOptionRecord(
                m.id,
                m.provider_id,
                p.name,
                m.model_key,
                m.display_name,
                tuple(m.tags_json),
            )
            for m, p in rows
        ]

    def add_cleanup(self, secret_ref: str) -> None:
        if self.session.get(ModelCredentialCleanupRow, secret_ref) is None:
            self.session.add(
                ModelCredentialCleanupRow(secret_ref=secret_ref, created_at=utc_now())
            )

    def remove_cleanup(self, secret_ref: str) -> None:
        row = self.session.get(ModelCredentialCleanupRow, secret_ref)
        if row:
            self.session.delete(row)

    def list_cleanup(self) -> list[str]:
        return list(
            self.session.scalars(
                select(ModelCredentialCleanupRow.secret_ref).order_by(
                    ModelCredentialCleanupRow.created_at
                )
            )
        )

    def is_secret_ref_live(self, secret_ref: str) -> bool:
        return (
            self.session.scalar(
                select(ModelProviderRow.id).where(
                    ModelProviderRow.secret_ref == secret_ref
                )
            )
            is not None
        )

    @staticmethod
    def _model(row: LocalModelRow) -> LocalModel:
        return LocalModel(
            row.id,
            row.provider_id,
            LocalModelSpec.from_values(
                row.model_key,
                row.display_name,
                row.tags_json,
                row.context_window,
                row.enabled,
                row.description,
            ),
            _aware(row.created_at),
            _aware(row.updated_at),
        )

    @classmethod
    def _provider(cls, row: ModelProviderRow) -> ModelProvider:
        profile = ProviderProfile.from_values(
            row.name,
            row.preset_id,
            row.provider_kind,
            row.base_url,
            row.secret_ref,
            row.enabled,
            row.description,
        )
        return ModelProvider(
            row.id,
            profile,
            tuple(cls._model(m) for m in row.models),
            row.connection_status,
            _aware(row.last_checked_at) if row.last_checked_at else None,
            row.last_check_latency_ms,
            row.last_check_message,
            _aware(row.created_at),
            _aware(row.updated_at),
        )


@contextmanager
def model_repository_transaction(
    session_factory: sessionmaker[Session],
) -> Iterator[SqlAlchemyModelRepository]:
    try:
        with session_factory.begin() as session:
            yield SqlAlchemyModelRepository(session)
    except IntegrityError as error:
        message = str(error.orig)
        code = (
            "MODEL_EXISTS"
            if "models.provider_id, models.model_key" in message
            else "MODEL_PROVIDER_EXISTS"
        )
        raise ModelError(
            code,
            "模型标识已存在" if code == "MODEL_EXISTS" else "模型供应商名称已存在",
            409,
            {"fields": {"modelKey" if code == "MODEL_EXISTS" else "name": "已存在"}},
        ) from error
