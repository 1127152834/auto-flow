from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, inspect, select

from autoflow.application.kernels.operations import ACTIVE_OPERATION_STATES
from autoflow.domain.profiles.errors import ProfileDataPathInvalid, ProfileDirectoryBusy
from autoflow.domain.settings.models import DashboardSnapshot
from autoflow.infrastructure.filesystem.profile_data import FilesystemProfileUsageGuard

from .models import (
    KernelOperationRow,
    LocalModelRow,
    ModelProviderRow,
    ProfileRow,
    ProxyPoolRow,
    ProxyRow,
)
from .proxy_models import ProxyConnectionRow, ProxyOperationRow


class SqlAlchemySettingsRuntimeRepository:
    def __init__(self, session_factory, profiles: Path) -> None:
        self._session_factory = session_factory
        self._profile_guard = FilesystemProfileUsageGuard(profiles)

    def dashboard(self, installed_kernels: int) -> DashboardSnapshot:
        with self._session_factory() as session:
            model_providers: int | None
            models: int | None
            schema = inspect(session.get_bind())
            if schema.has_table(ModelProviderRow.__tablename__) and schema.has_table(LocalModelRow.__tablename__):
                model_providers = _count(session, ModelProviderRow)
                models = _count(session, LocalModelRow)
            else:
                model_providers = models = None
            return DashboardSnapshot(
                profiles=_count(session, ProfileRow),
                enabled_proxies=int(session.scalar(select(func.count()).select_from(ProxyRow).where(ProxyRow.enabled.is_(True))) or 0),
                proxy_groups=_count(session, ProxyPoolRow),
                installed_kernels=installed_kernels,
                model_providers=model_providers,
                models=models,
                generated_at=datetime.now(UTC),
            )

    def blockers(self) -> list[str]:
        blockers: list[str] = []
        with self._session_factory() as session:
            if session.scalar(select(func.count()).select_from(KernelOperationRow).where(KernelOperationRow.status.in_(ACTIVE_OPERATION_STATES))):
                blockers.append("kernel_operation_active")
            if session.scalar(select(func.count()).select_from(ProxyConnectionRow).where(ProxyConnectionRow.sync_token.is_not(None))):
                blockers.append("proxy_sync_active")
            if session.scalar(select(func.count()).select_from(ProxyOperationRow).where(ProxyOperationRow.status.in_(("queued", "running")))):
                blockers.append("proxy_operation_active")
            profile_ids = list(session.scalars(select(ProfileRow.id)))
        for profile_id in profile_ids:
            try:
                with self._profile_guard.guard(profile_id):
                    pass
            except (ProfileDirectoryBusy, ProfileDataPathInvalid, OSError):
                blockers.append("profile_in_use")
                break
        return blockers


def _count(session, row) -> int:
    return int(session.scalar(select(func.count()).select_from(row)) or 0)
