from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings


class FakeInstalledKernelLookup:
    def __init__(self, installed: set[tuple[str, str]]) -> None:
        self.installed = installed

    def is_installed(self, edition: str, version: str) -> bool:
        return (edition, version) in self.installed


@pytest.fixture
def installed_kernels() -> FakeInstalledKernelLookup:
    return FakeInstalledKernelLookup({("public", "146.0.1")})


@pytest.fixture
def client(tmp_path, installed_kernels: FakeInstalledKernelLookup) -> Iterator[TestClient]:
    app = create_app(
        Settings(data_dir=str(tmp_path), instance_id="contract", instance_token="secret"),
        installed_kernel_lookup=installed_kernels,
    )
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
        "browserVersion": "146.0.1",
        "browserEdition": "public",
        "releaseChannel": "stable",
        "proxyMode": "none",
        "proxyId": None,
        "proxyPoolId": None,
    }
