from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from autoflow.application.kernels.operations import KernelOperation
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.kernels.models import InstalledKernel, KernelCatalog, LicenseStatus


class FakeInstalledKernelLookup:
    def __init__(self, installed: set[tuple[str, str]]) -> None:
        self.installed = installed

    def is_installed(self, edition: str, version: str) -> bool:
        return (edition, version) in self.installed


class FakeKernelCatalog:
    def __init__(self, identities: FakeInstalledKernelLookup, root: Path) -> None:
        self.identities = identities
        self.root = root

    def installed(self) -> list[InstalledKernel]:
        return [
            InstalledKernel(edition, version, self.root / _directory(edition, version) / "chrome.exe", 7)
            for edition, version in sorted(self.identities.installed)
        ]

    def is_installed(self, edition: str, version: str) -> bool:
        return self.identities.is_installed(edition, version)

    async def catalog(self) -> KernelCatalog:
        items = tuple(self.installed())
        return KernelCatalog("0.5.9", "windows-x64", (), items, "CloakBrowser catalog is unavailable")


class FakeLicenseProvider:
    def __init__(self) -> None:
        self.key: str | None = None

    async def status(self) -> LicenseStatus:
        return LicenseStatus(self.key is not None, self.key == "valid-license", "pro" if self.key else None, None, None)

    async def connect(self, license_key: str) -> LicenseStatus:
        if license_key != "valid-license":
            from autoflow.domain.kernels.errors import LicenseInvalid

            raise LicenseInvalid()
        self.key = license_key
        return await self.status()

    def disconnect(self, *, has_active_licensed_operation: bool) -> None:
        self.key = None


class FakeLicenseStore:
    def read(self) -> str | None:
        return None

    def write(self, _value: str) -> None: ...
    def delete(self) -> None: ...


class FakeOperations:
    def __init__(self) -> None:
        self.items: list[KernelOperation] = []
        self.busy = False

    async def start(self, job) -> KernelOperation:
        if self.busy:
            from autoflow.infrastructure.process.kernel_worker import (
                KernelWorkerManagerBusy,
            )

            raise KernelWorkerManagerBusy()
        operation = KernelOperation.new(
            operation_id="00000000-0000-0000-0000-000000000001",
            edition=job.edition,
            requested_version=job.requested_version,
            release_channel=job.release_channel,
        )
        self.items.append(operation)
        return operation

    async def cancel(self, operation_id: str) -> KernelOperation:
        from autoflow.infrastructure.process.kernel_worker import (
            KernelOperationNotFound,
        )

        for item in self.items:
            if item.id == operation_id:
                return item
        raise KernelOperationNotFound(operation_id)

    def snapshot(self) -> list[KernelOperation]:
        return list(self.items)


def _directory(edition: str, version: str) -> str:
    return f"chromium-{version}" + ("-pro" if edition == "licensed" else "")


@pytest.fixture
def installed_kernels() -> FakeInstalledKernelLookup:
    return FakeInstalledKernelLookup({("public", "146.0.1.1")})


@pytest.fixture
def client(tmp_path, installed_kernels: FakeInstalledKernelLookup) -> Iterator[TestClient]:
    app = create_app(
        Settings(
            data_dir=str(tmp_path), instance_id="contract", instance_token="secret",
            host_token="host-secret",
        ),
        installed_kernel_lookup=installed_kernels,
    )
    root = app.state.paths.kernels
    for edition, version in installed_kernels.installed:
        executable = root / _directory(edition, version) / "chrome.exe"
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_bytes(b"kernel")
    app.state.kernel_service.catalog_provider = FakeKernelCatalog(installed_kernels, root)
    app.state.kernel_service.license_provider = FakeLicenseProvider()
    app.state.kernel_service.license_store = FakeLicenseStore()
    app.state.kernel_service.operations = FakeOperations()
    with TestClient(app, headers={"x-autoflow-token": "secret"}) as test_client:
        yield test_client


@pytest.fixture
def profile_payload() -> dict[str, Any]:
    return {
        "name": "工作配置",
        "description": "完整契约夹具",
        "startUrl": "https://example.com/start",
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "geoip": True,
        "headless": False,
        "humanize": True,
        "humanPreset": "careful",
        "userAgent": "AutoFlow Contract",
        "viewportJson": {"width": 1280, "height": 720},
        "colorScheme": "dark",
        "extensionPathsJson": ["/opt/autoflow/extensions/example"],
        "expertArgsJson": ["  --lang=zh-CN  ", ""],
        "browserVersion": "146.0.1.1",
        "browserEdition": "public",
        "releaseChannel": "stable",
        "proxyMode": "none",
        "proxyId": None,
        "proxyPoolId": None,
    }
