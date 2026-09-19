import secrets
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.models.errors import ModelError
from autoflow.domain.models.models import (
    DiscoveryResult,
    LocalModel,
    LocalModelSpec,
    ModelOptionRecord,
    ModelProvider,
    ModelTestResult,
    ProviderConnection,
    ProviderProfile,
    utc_now,
)
from autoflow.domain.models.ports import ModelGateway, ModelRepository
from autoflow.domain.models.validation import validate_connection
from autoflow.domain.projects.ports import ProjectResourceReferences

Transaction = Callable[[], AbstractContextManager[ModelRepository]]


def _new_secret_ref() -> str:
    return f"model-provider/{secrets.token_urlsafe(24)}"


def _read_secret(store: CredentialStore, ref: str | None) -> str:
    if ref is None:
        return ""
    value = store.read(ref)
    if value is None:
        raise CredentialStoreUnavailableError("credential missing")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CredentialStoreUnavailableError("credential invalid") from error


class ModelService:
    def __init__(
        self,
        transaction: Transaction,
        credentials: CredentialStore,
        gateway: ModelGateway,
        references: ProjectResourceReferences | None = None,
    ):
        self._transaction, self._credentials, self._gateway = (
            transaction,
            credentials,
            gateway,
        )
        self._references = references

    def list_providers(self) -> list[ModelProvider]:
        with self._transaction() as repo:
            return repo.list_providers()

    def get_provider(self, provider_id: str) -> ModelProvider:
        with self._transaction() as repo:
            provider = repo.get_provider(provider_id)
        if provider is None:
            raise self._provider_missing()
        return provider

    def list_options(self) -> list[ModelOptionRecord]:
        with self._transaction() as repo:
            return repo.list_options()

    async def preview(self, profile: ProviderProfile, secret: str) -> DiscoveryResult:
        connection, _normalized = self._candidate(profile, secret)
        result = await self._gateway.discover(connection, secret)
        return result

    async def connect(
        self, profile: ProviderProfile, secret: str, specs: list[LocalModelSpec]
    ) -> ModelProvider:
        connection, normalized = self._candidate(profile, secret)
        result = await self._gateway.discover(connection, secret)
        remote = {item.model_key: item for item in result.items}
        missing = [spec.model_key for spec in specs if spec.model_key not in remote]
        if missing:
            raise ModelError(
                "MODEL_PROVIDER_MODEL_NOT_DISCOVERED",
                "所选模型已不在最新目录中",
                409,
                {"modelKeys": missing},
            )
        with self._transaction() as repo:
            if repo.get_provider_by_name(profile.name):
                raise ModelError(
                    "MODEL_PROVIDER_EXISTS",
                    "模型供应商名称已存在",
                    409,
                    {"fields": {"name": "已存在"}},
                )
        secret_ref = self._write_candidate(secret) if secret else None
        now = utc_now()
        saved_profile = replace(profile, base_url=normalized, secret_ref=secret_ref)
        provider = replace(
            ModelProvider.create(saved_profile),
            connection_status="connected",
            last_checked_at=now,
            last_check_latency_ms=float(result.latency_ms),
            last_check_message=result.message,
            updated_at=now,
        )
        models = []
        for spec in specs:
            item = remote[spec.model_key]
            merged = replace(
                spec,
                context_window=spec.context_window
                if spec.context_window is not None
                else item.context_window,
            )
            models.append(LocalModel.create(provider.id, merged))
        provider = replace(provider, models=tuple(models))
        with self._transaction() as repo:
            repo.add_provider(provider)
            for model in models:
                repo.add_model(model)
            if secret_ref:
                repo.remove_cleanup(secret_ref)
        return provider

    async def test_provider(self, provider_id: str) -> DiscoveryResult:
        provider, secret = self._snapshot(provider_id)
        try:
            result = await self._gateway.discover(self._connection(provider), secret)
        except ModelError:
            self._record_test(provider, "failed", None, "连接检查失败")
            raise
        self._record_test(provider, "connected", result.latency_ms, result.message)
        return result

    async def discover(self, provider_id: str) -> DiscoveryResult:
        provider, secret = self._snapshot(provider_id)
        return await self._gateway.discover(self._connection(provider), secret)

    async def test_model(self, provider_id: str, model_key: str) -> ModelTestResult:
        provider, secret = self._snapshot(provider_id)
        return await self._gateway.test_model(
            self._connection(provider), secret, model_key.strip()
        )

    def update_metadata(
        self, provider_id: str, name: str, description: str, enabled: bool
    ) -> ModelProvider:
        old = self.get_provider(provider_id)
        now = utc_now()
        updated = replace(
            old,
            profile=replace(
                old.profile, name=name.strip(), description=description, enabled=enabled
            ),
            updated_at=now,
        )
        with self._transaction() as repo:
            other = repo.get_provider_by_name(updated.name)
            if other and other.id != provider_id:
                raise ModelError(
                    "MODEL_PROVIDER_EXISTS",
                    "模型供应商名称已存在",
                    409,
                    {"fields": {"name": "已存在"}},
                )
            if not repo.update_provider(updated, old.updated_at):
                raise ModelError(
                    "MODEL_PROVIDER_CHANGED", "模型供应商已被修改，请刷新后重试", 409
                )
        return self.get_provider(provider_id)

    async def update_connection(
        self, provider_id: str, profile: ProviderProfile, api_key: str | None
    ) -> ModelProvider:
        old = self.get_provider(provider_id)
        try:
            secret = (
                _read_secret(self._credentials, old.secret_ref)
                if api_key is None
                else api_key
            )
        except CredentialStoreUnavailableError:
            raise ModelError(
                "CREDENTIAL_STORE_UNAVAILABLE", "系统凭据存储当前不可用", 503
            ) from None
        connection, normalized = self._candidate(profile, secret)
        result = await self._gateway.discover(connection, secret)
        new_ref = old.secret_ref
        if api_key is not None:
            new_ref = self._write_candidate(secret) if secret else None
        now = utc_now()
        updated = replace(
            old,
            profile=replace(profile, base_url=normalized, secret_ref=new_ref),
            connection_status="connected",
            last_checked_at=now,
            last_check_latency_ms=float(result.latency_ms),
            last_check_message=result.message,
            updated_at=now,
        )
        with self._transaction() as repo:
            current = repo.get_provider(provider_id)
            if current is None:
                raise self._provider_missing()
            if current.updated_at != old.updated_at:
                raise ModelError(
                    "MODEL_PROVIDER_CHANGED", "模型供应商已被修改，请刷新后重试", 409
                )
            other = repo.get_provider_by_name(updated.name)
            if other and other.id != provider_id:
                raise ModelError(
                    "MODEL_PROVIDER_EXISTS",
                    "模型供应商名称已存在",
                    409,
                    {"fields": {"name": "已存在"}},
                )
            if not repo.update_provider(updated, old.updated_at):
                raise ModelError(
                    "MODEL_PROVIDER_CHANGED", "模型供应商已被修改，请刷新后重试", 409
                )
            if new_ref:
                repo.remove_cleanup(new_ref)
            if old.secret_ref and old.secret_ref != new_ref:
                repo.add_cleanup(old.secret_ref)
        if old.secret_ref and old.secret_ref != new_ref:
            self._cleanup_ref(old.secret_ref)
        return self.get_provider(provider_id)

    def delete_provider(self, provider_id: str) -> None:
        old = self.get_provider(provider_id)
        with self._transaction() as repo:
            current = repo.get_provider(provider_id)
            if current is None:
                raise self._provider_missing()
            if current.updated_at != old.updated_at:
                raise ModelError(
                    "MODEL_PROVIDER_CHANGED", "模型供应商已被修改，请刷新后重试", 409
                )
            if self._references is not None:
                self._references.ensure_unreferenced("modelProvider", provider_id)
            if old.secret_ref:
                repo.add_cleanup(old.secret_ref)
            if not repo.remove_provider(provider_id, old.updated_at):
                raise ModelError(
                    "MODEL_PROVIDER_CHANGED", "模型供应商已被修改，请刷新后重试", 409
                )
        if old.secret_ref:
            self._cleanup_ref(old.secret_ref)

    def create_model(self, provider_id: str, spec: LocalModelSpec) -> LocalModel:
        self.get_provider(provider_id)
        model = LocalModel.create(provider_id, spec)
        with self._transaction() as repo:
            if repo.get_model_by_key(provider_id, spec.model_key):
                raise ModelError(
                    "MODEL_EXISTS",
                    "模型标识已存在",
                    409,
                    {"fields": {"modelKey": "已存在"}},
                )
            repo.add_model(model)
        return model

    def update_model(self, model_id: str, spec: LocalModelSpec) -> LocalModel:
        with self._transaction() as repo:
            old = repo.get_model(model_id)
            if old is None:
                raise self._model_missing()
            if old.model_key != spec.model_key:
                raise ModelError(
                    "VALIDATION_ERROR",
                    "模型标识不可修改",
                    422,
                    {"fields": {"modelKey": "不可修改"}},
                )
            updated = replace(old, spec=spec, updated_at=utc_now())
            repo.update_model(updated)
        return updated

    def delete_model(self, model_id: str) -> None:
        with self._transaction() as repo:
            if not repo.remove_model(model_id):
                raise self._model_missing()

    def recover_credentials(self) -> None:
        with self._transaction() as repo:
            refs = repo.list_cleanup()
        for ref in refs:
            self._cleanup_ref(ref)

    def _snapshot(self, provider_id: str) -> tuple[ModelProvider, str]:
        provider = self.get_provider(provider_id)
        try:
            return provider, _read_secret(self._credentials, provider.secret_ref)
        except CredentialStoreUnavailableError:
            raise ModelError(
                "CREDENTIAL_STORE_UNAVAILABLE", "系统凭据存储当前不可用", 503
            ) from None

    def _candidate(
        self, profile: ProviderProfile, secret: str
    ) -> tuple[ProviderConnection, str]:
        connection = ProviderConnection(
            profile.preset_id, profile.provider_kind, profile.base_url
        )
        return connection, validate_connection(connection, secret)

    @staticmethod
    def _connection(provider: ModelProvider) -> ProviderConnection:
        return ProviderConnection(
            provider.preset_id, provider.provider_kind, provider.base_url
        )

    def _write_candidate(self, secret: str) -> str:
        ref = _new_secret_ref()
        with self._transaction() as repo:
            repo.add_cleanup(ref)
        try:
            self._credentials.write(ref, secret.encode())
        except (CredentialStoreUnavailableError, RuntimeError):
            raise ModelError(
                "CREDENTIAL_STORE_UNAVAILABLE", "系统凭据存储当前不可用", 503
            ) from None
        return ref

    def _cleanup_ref(self, ref: str) -> None:
        with self._transaction() as repo:
            if repo.is_secret_ref_live(ref):
                return
        try:
            self._credentials.delete(ref)
        except (CredentialStoreUnavailableError, RuntimeError):
            return
        with self._transaction() as repo:
            if not repo.is_secret_ref_live(ref):
                repo.remove_cleanup(ref)

    def _record_test(
        self, snapshot: ModelProvider, status: str, latency: float | None, message: str
    ) -> None:
        now = utc_now()
        updated = replace(
            snapshot,
            connection_status=status,
            last_checked_at=now,
            last_check_latency_ms=float(latency) if latency is not None else None,
            last_check_message=message,
            updated_at=now,
        )
        with self._transaction() as repo:
            if repo.get_provider(snapshot.id) is None:
                raise self._provider_missing()
            if not repo.update_provider(updated, snapshot.updated_at):
                raise ModelError(
                    "MODEL_PROVIDER_CHANGED", "模型供应商已被修改，请刷新后重试", 409
                )

    @staticmethod
    def _provider_missing() -> ModelError:
        return ModelError("MODEL_PROVIDER_NOT_FOUND", "模型供应商不存在", 404)

    @staticmethod
    def _model_missing() -> ModelError:
        return ModelError("MODEL_NOT_FOUND", "模型不存在", 404)
