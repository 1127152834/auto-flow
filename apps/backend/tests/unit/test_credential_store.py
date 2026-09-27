import pytest
from keyring.errors import KeyringError

from autoflow.domain.credentials import CredentialStoreUnavailableError
from autoflow.infrastructure.credentials.redaction import (
    redact_sensitive_text,
    redact_sensitive_value,
)
from autoflow.infrastructure.credentials.system import SystemCredentialStore


class FakeMacBackend:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        del self.values[(service, username)]


FakeMacBackend.__module__ = "keyring.backends.macOS"


class FakeWindowsBackend(FakeMacBackend):
    pass


FakeWindowsBackend.__module__ = "keyring.backends.Windows"


@pytest.mark.parametrize(
    ("platform_name", "backend_type"),
    [("darwin", FakeMacBackend), ("win32", FakeWindowsBackend)],
)
def test_system_backend_round_trips_opaque_bytes(platform_name, backend_type):
    backend = backend_type()
    store = SystemCredentialStore(backend, platform_name=platform_name)
    secret = b"\x00proxy-panel\xff"

    assert store.read("missing") is None
    store.write("proxy-key", secret)
    assert store.read("proxy-key") == secret
    assert secret not in next(iter(backend.values.values())).encode()

    store.delete("proxy-key")
    store.delete("proxy-key")
    assert store.read("proxy-key") is None


def test_non_system_backend_and_unsupported_platform_are_rejected():
    with pytest.raises(CredentialStoreUnavailableError, match="operating-system backend"):
        SystemCredentialStore(FakeMacBackend(), platform_name="win32")

    with pytest.raises(CredentialStoreUnavailableError, match="only on macOS and Windows"):
        SystemCredentialStore(FakeMacBackend(), platform_name="linux")


def test_backend_errors_do_not_expose_secret_or_key():
    class BrokenMacBackend(FakeMacBackend):
        def set_password(self, service: str, username: str, password: str) -> None:
            raise KeyringError(f"failed for {username}: {password}")

    BrokenMacBackend.__module__ = "keyring.backends.macOS"
    store = SystemCredentialStore(BrokenMacBackend(), platform_name="darwin")

    with pytest.raises(CredentialStoreUnavailableError) as error:
        store.write("private-key-name", b"private-secret")

    assert "private-key-name" not in str(error.value)
    assert "private-secret" not in str(error.value)


def test_error_redaction_covers_known_and_structured_credentials():
    message = (
        "Authorization: Bearer live-token "
        "https://user:proxy-pass@example.test/path?api_key=path-token "
        '{"password":"json-pass"} known-secret'
    )

    redacted = redact_sensitive_text(message, ["known-secret"])

    for secret in ("live-token", "proxy-pass", "path-token", "json-pass", "known-secret"):
        assert secret not in redacted
    assert redacted.count("[REDACTED]") == 5


def test_structured_redaction_removes_nested_credentials_without_changing_shape():
    value = {
        "apiKey": "api-secret",
        "nested": {
            "proxyPassword": "proxy-secret",
            "licenseKey": "license-secret",
            "maxTokens": 4096,
            "message": "Authorization: Bearer header-secret",
        },
        "items": [{"password": "password-secret"}, "safe"],
    }

    redacted = redact_sensitive_value(value)

    assert redacted == {
        "apiKey": "[REDACTED]",
        "nested": {
            "proxyPassword": "[REDACTED]",
            "licenseKey": "[REDACTED]",
            "maxTokens": 4096,
            "message": "Authorization: Bearer [REDACTED]",
        },
        "items": [{"password": "[REDACTED]"}, "safe"],
    }
