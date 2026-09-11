import logging
from typing import Literal, Protocol

from autoflow.application.kernels.operations import (
    ACTIVE_OPERATION_STATES,
    KernelInstallJob,
    KernelOperation,
)
from autoflow.domain.kernels.errors import KernelNotFound, LicenseInvalid
from autoflow.domain.kernels.models import (
    DefaultKernel,
    InstalledKernel,
    KernelCatalog,
    KernelRef,
    LicenseStatus,
)
from autoflow.domain.kernels.ports import (
    DefaultKernelRepository,
    KernelCatalogProvider,
    KernelInstallationStore,
    LicenseStore,
)

logger = logging.getLogger(__name__)


class LicenseProvider(Protocol):
    async def status(self) -> LicenseStatus: ...
    async def connect(self, license_key: str) -> LicenseStatus: ...
    def disconnect(self, *, has_active_licensed_operation: bool) -> None: ...


class OperationManager(Protocol):
    async def start(self, job: KernelInstallJob) -> KernelOperation: ...
    async def cancel(self, operation_id: str) -> KernelOperation: ...
    def snapshot(self) -> list[KernelOperation]: ...


class KernelService:
    def __init__(
        self,
        catalog_provider: KernelCatalogProvider,
        license_provider: LicenseProvider,
        license_store: LicenseStore,
        defaults: DefaultKernelRepository,
        installations: KernelInstallationStore,
        operations: OperationManager,
    ) -> None:
        self.catalog_provider = catalog_provider
        self.license_provider = license_provider
        self.license_store = license_store
        self.defaults = defaults
        self.installations = installations
        self.operations = operations

    async def catalog(self) -> KernelCatalog:
        return await self.catalog_provider.catalog()

    def installed(self) -> list[InstalledKernel]:
        return self.catalog_provider.installed()

    async def license_status(self) -> LicenseStatus:
        return await self.license_provider.status()

    async def connect_license(self, license_key: str) -> LicenseStatus:
        return await self.license_provider.connect(license_key)

    def disconnect_license(self) -> None:
        active = any(
            item.edition == "licensed" and item.state in ACTIVE_OPERATION_STATES
            for item in self.operations.snapshot()
        )
        self.license_provider.disconnect(has_active_licensed_operation=active)

    def get_default(self) -> DefaultKernel:
        return self.defaults.get()

    def set_default(self, expected_revision: int, kernel: KernelRef | None) -> DefaultKernel:
        with self.installations.guard():
            if kernel is not None and not self.catalog_provider.is_installed(
                kernel.edition, kernel.version
            ):
                raise KernelNotFound()
            return self.defaults.compare_and_set(expected_revision, kernel)

    async def download(
        self,
        edition: Literal["public", "licensed"],
        version: str,
        release_channel: Literal["stable", "preview"],
    ) -> KernelOperation:
        key = None
        if edition == "licensed":
            key = self.license_store.read()
            if key is None:
                raise LicenseInvalid()
        return await self.operations.start(
            KernelInstallJob(
                edition=edition,
                requested_version=version,
                release_channel=release_channel,
                license_key=key,
            )
        )

    async def cancel(self, operation_id: str) -> KernelOperation:
        return await self.operations.cancel(operation_id)

    def list_operations(self) -> list[KernelOperation]:
        return self.operations.snapshot()

    def remove(self, kernel: KernelRef) -> DefaultKernel:
        with self.installations.guard():
            if not self.catalog_provider.is_installed(kernel.edition, kernel.version):
                raise KernelNotFound()
            token = self.installations.stage(kernel)
            try:
                default = self.defaults.clear_if_matches(kernel)
            except Exception:
                self.installations.restore(token)
                raise
            try:
                self.installations.purge(token)
            except Exception:  # noqa: BLE001 -- committed deletion remains successful.
                logger.warning("kernel cleanup remains pending for token=%s", token)
            return default

    def resolve_installed(self, kernel: KernelRef) -> InstalledKernel:
        for installed in self.catalog_provider.installed():
            if installed.edition == kernel.edition and installed.version == kernel.version:
                return installed
        raise KernelNotFound()
