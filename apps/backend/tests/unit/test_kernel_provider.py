from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from autoflow.domain.credentials import CredentialStoreUnavailableError
from autoflow.domain.kernels.errors import (
    KernelCatalogError,
    KernelCredentialStoreUnavailable,
    KernelPlatformUnsupported,
    LicenseInUse,
    LicenseInvalid,
    LicenseValidationUnavailable,
)
from autoflow.domain.kernels.models import LicenseStatus
from autoflow.infrastructure.credentials.cloakbrowser import CloakBrowserLicenseStore
from autoflow.providers.kernel.catalog import (
    current_platform_tag,
    parse_licensed_catalog,
    parse_public_catalog,
    resolve_installed_kernel,
    scan_installed_kernels,
)
from autoflow.providers.kernel.cloakbrowser import (
    CloakBrowserCatalogProvider,
    CloakBrowserLicenseProvider,
    download_with_wrapper,
    parse_license_status,
    validate_license_with_wrapper,
)

PUBLIC_VERSION = "146.0.7680.177.5"
LICENSED_VERSION = "151.0.7922.108.3"
RESOLVED_VERSION = "152.0.8000.1"


@pytest.fixture
def github_release_payload() -> list[object]:
    return [
        {
            "tag_name": f"chromium-v{PUBLIC_VERSION}",
            "name": "CloakBrowser 146",
            "body": "# Stable **release**",
            "published_at": "2026-09-10T12:00:00Z",
            "prerelease": False,
            "assets": [
                {"name": "cloakbrowser-windows-x64.zip", "size": 100},
                {"name": "cloakbrowser-darwin-arm64.tar.gz", "size": 200},
                {"name": "cloakbrowser-darwin-x64.tar.gz", "size": 300},
            ],
        },
        {
            "tag_name": "chromium-v147.0.7777.1",
            "name": "Preview",
            "prerelease": True,
            "assets": [{"name": "cloakbrowser-darwin-arm64.tar.gz", "size": 400}],
        },
        {
            "tag_name": f"chromium-v{PUBLIC_VERSION}-pro",
            "assets": [{"name": "cloakbrowser-darwin-arm64.tar.gz", "size": 500}],
        },
    ]


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Windows", "AMD64", "windows-x64"),
        ("Windows", "x86_64", "windows-x64"),
        ("Darwin", "arm64", "darwin-arm64"),
        ("Darwin", "x86_64", "darwin-x64"),
    ],
)
def test_platform_detection_supports_only_release_targets(
    system: str, machine: str, expected: str
) -> None:
    assert current_platform_tag(system=system, machine=machine) == expected


def test_platform_detection_rejects_linux() -> None:
    with pytest.raises(KernelPlatformUnsupported) as error:
        current_platform_tag(system="Linux", machine="x86_64")
    assert error.value.code == "KERNEL_PLATFORM_UNSUPPORTED"


def test_catalog_ignores_other_platform_assets(github_release_payload: list[object]) -> None:
    releases = parse_public_catalog(github_release_payload, platform="darwin-arm64")

    assert len(releases) == 1
    assert "darwin-arm64" in (releases[0].archive or "")
    assert releases[0].edition == "public"
    assert releases[0].release_channel == "stable"


def test_public_catalog_rejects_non_list_payload() -> None:
    with pytest.raises(KernelCatalogError) as error:
        parse_public_catalog({"message": "rate limited"}, platform="windows-x64")
    assert error.value.code == "KERNEL_CATALOG_INVALID"


def test_windows_catalog_never_falls_back_to_macos_asset() -> None:
    payload = [
        {
            "tag_name": f"chromium-v{PUBLIC_VERSION}",
            "assets": [{"name": "cloakbrowser-darwin-x64.tar.gz", "size": 1}],
        }
    ]

    assert parse_public_catalog(payload, platform="windows-x64") == []


def test_public_catalog_rejects_version_outside_wrapper_contract() -> None:
    payload = [
        {
            "tag_name": "chromium-v146.0.1",
            "assets": [{"name": "cloakbrowser-windows-x64.zip", "size": 1}],
        }
    ]

    assert parse_public_catalog(payload, platform="windows-x64") == []


def test_licensed_catalog_uses_resolved_channel_and_deduplicates() -> None:
    stable = SimpleNamespace(version=LICENSED_VERSION, resolved_channel="stable")
    preview_fallback = SimpleNamespace(version=LICENSED_VERSION, resolved_channel="stable")

    releases = parse_licensed_catalog([stable, preview_fallback])

    assert [(release.version, release.release_channel) for release in releases] == [
        (LICENSED_VERSION, "stable")
    ]
    assert releases[0].edition == "licensed"
    assert releases[0].published_at is None
    assert releases[0].size is None


@pytest.mark.parametrize(
    "version",
    ["../../escape", "/tmp/x", "151.0.2", "151.0.2.3.4.5", "v151.0.2.3"],
)
def test_licensed_catalog_rejects_versions_outside_wrapper_contract(version: str) -> None:
    info = SimpleNamespace(version=version, resolved_channel="stable")

    assert parse_licensed_catalog([info]) == []


def _make_installed(root: Path, name: str, platform: str, content: bytes = b"browser") -> Path:
    directory = root / name
    executable = (
        directory / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
        if platform.startswith("darwin-")
        else directory / "chrome.exe"
    )
    executable.parent.mkdir(parents=True)
    executable.write_bytes(content)
    return executable


def test_installed_scan_ignores_staging_and_incomplete_directories(tmp_path: Path) -> None:
    public = _make_installed(tmp_path, f"chromium-{PUBLIC_VERSION}", "windows-x64")
    _make_installed(tmp_path, f"chromium-{LICENSED_VERSION}-pro", "windows-x64", b"pro")
    _make_installed(tmp_path / ".staging", "chromium-999.0.0.1", "windows-x64")
    _make_installed(tmp_path, "chromium-155.0.1", "windows-x64")
    (tmp_path / "chromium-155.0.0.1").mkdir()

    installed = scan_installed_kernels(tmp_path, platform="windows-x64")

    assert [(item.version, item.edition) for item in installed] == [
        (LICENSED_VERSION, "licensed"),
        (PUBLIC_VERSION, "public"),
    ]
    assert resolve_installed_kernel(public, installed) == installed[1]


def test_free_plan_sdk_result_resolves_actual_version_from_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import cloakbrowser.download as wrapper_download
    import cloakbrowser.license as wrapper_license

    actual = _make_installed(
        tmp_path, f"chromium-{RESOLVED_VERSION}-pro", "windows-x64"
    )
    received: dict[str, object] = {}

    def ensure_pro_binary(
        key: str,
        *,
        requested_version: str | None,
        plan: str,
        release_channel: str | None,
    ) -> str:
        received.update(
            key=key,
            requested_version=requested_version,
            plan=plan,
            release_channel=release_channel,
        )
        return str(actual)

    monkeypatch.delenv("CLOAKBROWSER_DOWNLOAD_URL", raising=False)
    monkeypatch.setattr(wrapper_download, "get_local_binary_override", lambda: None)
    monkeypatch.setattr(wrapper_license, "resolve_license_key", lambda key: key)
    monkeypatch.setattr(
        wrapper_license,
        "validate_license",
        lambda _key: SimpleNamespace(valid=True, plan="free", expires=None),
    )
    monkeypatch.setattr(wrapper_download, "_ensure_pro_binary", ensure_pro_binary)

    returned_path = download_with_wrapper(
        license_key="test-free-key",
        browser_version=LICENSED_VERSION,
        release_channel="stable",
    )
    installed = scan_installed_kernels(tmp_path, platform="windows-x64")

    resolved = resolve_installed_kernel(returned_path, installed)

    assert resolved is not None
    assert resolved.version == RESOLVED_VERSION
    assert received == {
        "key": "test-free-key",
        "requested_version": None,
        "plan": "free",
        "release_channel": "stable",
    }


class _OfflineClient:
    async def get(self, *_args: object, **_kwargs: object) -> object:
        request = httpx.Request("GET", "https://api.github.invalid/releases")
        raise httpx.ConnectError("private-test-key network detail", request=request)


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> _Response:
        return self

    def json(self) -> object:
        return self.payload


class _OnlineClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    async def get(self, *_args: object, **_kwargs: object) -> _Response:
        return _Response(self.payload)


@pytest.mark.asyncio
async def test_catalog_combines_public_licensed_and_installed(
    tmp_path: Path, github_release_payload: list[object]
) -> None:
    _make_installed(tmp_path, f"chromium-{PUBLIC_VERSION}", "darwin-arm64")
    provider = CloakBrowserCatalogProvider(
        tmp_path,
        platform="darwin-arm64",
        client=_OnlineClient(github_release_payload),
        licensed_catalog=lambda: [
            SimpleNamespace(version=LICENSED_VERSION, resolved_channel="stable")
        ],
    )

    catalog = await provider.catalog()

    assert catalog.catalog_error is None
    assert [(item.edition, item.version, item.installed) for item in catalog.releases] == [
        ("licensed", LICENSED_VERSION, False),
        ("public", PUBLIC_VERSION, True),
    ]


@pytest.mark.asyncio
async def test_catalog_network_failure_returns_installed_fallback(tmp_path: Path) -> None:
    _make_installed(tmp_path, f"chromium-{PUBLIC_VERSION}", "windows-x64")
    provider = CloakBrowserCatalogProvider(
        tmp_path,
        platform="windows-x64",
        client=_OfflineClient(),
        licensed_catalog=list,
    )

    catalog = await provider.catalog()

    assert catalog.catalog_error == "CloakBrowser catalog is unavailable"
    assert [(item.version, item.installed) for item in catalog.releases] == [
        (PUBLIC_VERSION, True)
    ]
    assert "private-test-key" not in (catalog.catalog_error or "")


def test_license_parser_handles_expiry_and_missing_seat_information() -> None:
    expired = parse_license_status(
        SimpleNamespace(valid=True, plan="pro", expires="2026-09-11T00:00:00Z"),
        seats=SimpleNamespace(active=None, limit=None, state="unknown", reason=None),
        configured=True,
        now=datetime(2026, 9, 12, tzinfo=UTC),
    )
    without_seats = parse_license_status(
        SimpleNamespace(valid=True, plan="free", expires=None),
        seats=None,
        configured=True,
        now=datetime(2026, 9, 12, tzinfo=UTC),
    )

    assert expired.valid is False
    assert expired.expires == "2026-09-11T00:00:00Z"
    assert expired.seats is None
    assert without_seats == LicenseStatus(True, True, "free", None, None)


def test_wrapper_none_means_validation_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cloakbrowser

    monkeypatch.setattr(cloakbrowser, "validate_license", lambda _key: None)

    with pytest.raises(LicenseValidationUnavailable):
        validate_license_with_wrapper("private-test-key")


def test_wrapper_invalid_license_remains_distinct_from_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cloakbrowser

    monkeypatch.setattr(
        cloakbrowser,
        "validate_license",
        lambda _key: SimpleNamespace(valid=False, plan="free", expires=None),
    )

    assert validate_license_with_wrapper("test-invalid-key").valid is False


def test_wrapper_expired_license_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    import cloakbrowser
    import cloakbrowser.license

    monkeypatch.setattr(
        cloakbrowser,
        "validate_license",
        lambda _key: SimpleNamespace(
            valid=True, plan="pro", expires="2000-01-01T00:00:00Z"
        ),
    )
    monkeypatch.setattr(
        cloakbrowser.license,
        "get_session_seats",
        lambda _key: SimpleNamespace(active=None, limit=None),
    )

    assert validate_license_with_wrapper("test-expired-key").valid is False


def test_wrapper_validation_exception_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cloakbrowser

    def fail(key: str) -> object:
        raise RuntimeError(f"failed for {key}")

    monkeypatch.setattr(cloakbrowser, "validate_license", fail)

    with pytest.raises(LicenseValidationUnavailable) as error:
        validate_license_with_wrapper("private-test-key")

    assert "private-test-key" not in str(error.value)


class _MemoryCredentialStore:
    def __init__(self, value: bytes | None = None) -> None:
        self.values: dict[str, bytes] = {}
        if value is not None:
            self.values["cloakbrowser-license"] = value

    def read(self, key: str) -> bytes | None:
        return self.values.get(key)

    def write(self, key: str, value: bytes) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


def test_cloakbrowser_license_store_adapts_fixed_generic_credential_key() -> None:
    generic = _MemoryCredentialStore()
    store = CloakBrowserLicenseStore(generic)

    store.write("license-one")

    assert generic.values == {"cloakbrowser-license": b"license-one"}
    assert store.read() == "license-one"
    store.delete()
    assert store.read() is None


def test_cloakbrowser_license_store_maps_shared_store_failure_without_secret() -> None:
    class BrokenStore(_MemoryCredentialStore):
        def write(self, key: str, value: bytes) -> None:
            raise CredentialStoreUnavailableError(f"failed {key} {value!r}")

    store = CloakBrowserLicenseStore(BrokenStore())

    with pytest.raises(KernelCredentialStoreUnavailable) as error:
        store.write("private-test-key")

    assert error.value.code == "CREDENTIAL_STORE_UNAVAILABLE"
    assert "private-test-key" not in str(error.value)


def test_wrapper_unavailable_does_not_replace_existing_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cloakbrowser

    monkeypatch.setattr(cloakbrowser, "validate_license", lambda _key: None)
    generic = _MemoryCredentialStore(b"existing-key")
    provider = CloakBrowserLicenseProvider(
        CloakBrowserLicenseStore(generic), validate_license_with_wrapper
    )

    with pytest.raises(LicenseValidationUnavailable):
        provider.connect("new-test-key")

    assert generic.values["cloakbrowser-license"] == b"existing-key"


def test_invalid_license_does_not_replace_existing_credential() -> None:
    generic = _MemoryCredentialStore(b"existing-key")
    provider = CloakBrowserLicenseProvider(
        CloakBrowserLicenseStore(generic),
        validator=lambda _key: LicenseStatus(True, False, "free", None, None),
    )

    with pytest.raises(LicenseInvalid) as error:
        provider.connect("new-test-key")

    assert error.value.code == "LICENSE_INVALID"
    assert generic.values["cloakbrowser-license"] == b"existing-key"
    assert "new-test-key" not in str(error.value)


def test_validation_failure_is_sanitized_and_preserves_existing_credential() -> None:
    generic = _MemoryCredentialStore(b"existing-key")

    def fail(key: str) -> LicenseStatus:
        raise RuntimeError(f"remote rejected {key}")

    provider = CloakBrowserLicenseProvider(CloakBrowserLicenseStore(generic), fail)

    with pytest.raises(LicenseValidationUnavailable) as error:
        provider.connect("private-test-key")

    assert error.value.code == "LICENSE_VALIDATION_UNAVAILABLE"
    assert generic.values["cloakbrowser-license"] == b"existing-key"
    assert "private-test-key" not in str(error.value)


def test_valid_license_is_saved_only_after_validation() -> None:
    generic = _MemoryCredentialStore(b"existing-key")
    valid = LicenseStatus(True, True, "pro", None, None)
    provider = CloakBrowserLicenseProvider(
        CloakBrowserLicenseStore(generic), validator=lambda _key: valid
    )

    assert provider.connect("replacement-key") == valid
    assert generic.values["cloakbrowser-license"] == b"replacement-key"


def test_disconnect_rejects_active_licensed_operation_without_deleting_key() -> None:
    generic = _MemoryCredentialStore(b"existing-key")
    provider = CloakBrowserLicenseProvider(
        CloakBrowserLicenseStore(generic),
        validator=lambda _key: LicenseStatus(True, True, "pro", None, None),
    )

    with pytest.raises(LicenseInUse) as error:
        provider.disconnect(has_active_licensed_operation=True)

    assert error.value.code == "LICENSE_IN_USE"
    assert generic.values["cloakbrowser-license"] == b"existing-key"


def test_disconnect_deletes_only_the_license_credential() -> None:
    generic = _MemoryCredentialStore(b"existing-key")
    generic.values["proxy-key"] = b"proxy"
    provider = CloakBrowserLicenseProvider(
        CloakBrowserLicenseStore(generic),
        validator=lambda _key: LicenseStatus(True, True, "pro", None, None),
    )

    provider.disconnect(has_active_licensed_operation=False)

    assert generic.values == {"proxy-key": b"proxy"}
