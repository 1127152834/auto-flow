import base64
import binascii
import sys
from typing import Protocol

import keyring
from keyring.errors import KeyringError

from autoflow.domain.credentials import CredentialStoreUnavailableError

_SERVICE_NAME = "dev.autoflow.credentials"
_SYSTEM_BACKENDS = {
    "darwin": "keyring.backends.macOS",
    "win32": "keyring.backends.Windows",
}


class _KeyringBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


class SystemCredentialStore:
    """Store opaque bytes in the native macOS or Windows credential backend."""

    def __init__(
        self,
        backend: _KeyringBackend | None = None,
        *,
        platform_name: str | None = None,
    ) -> None:
        platform_name = platform_name or sys.platform
        expected_module = _SYSTEM_BACKENDS.get(platform_name)
        if expected_module is None:
            raise CredentialStoreUnavailableError(
                "system credential storage is supported only on macOS and Windows"
            )

        if backend is None:
            try:
                backend = keyring.get_keyring()
            except KeyringError:
                raise CredentialStoreUnavailableError(
                    "system credential storage is unavailable"
                ) from None

        if backend.__class__.__module__ != expected_module:
            raise CredentialStoreUnavailableError(
                "the active credential backend is not the operating-system backend"
            )
        self._backend = backend

    def read(self, key: str) -> bytes | None:
        try:
            encoded = self._backend.get_password(_SERVICE_NAME, key)
            if encoded is None:
                return None
            return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise CredentialStoreUnavailableError(
                "the stored credential cannot be decoded"
            ) from None
        except KeyringError:
            raise CredentialStoreUnavailableError(
                "system credential storage read failed"
            ) from None

    def write(self, key: str, value: bytes) -> None:
        encoded = base64.b64encode(value).decode("ascii")
        try:
            self._backend.set_password(_SERVICE_NAME, key, encoded)
        except KeyringError:
            raise CredentialStoreUnavailableError(
                "system credential storage write failed"
            ) from None

    def delete(self, key: str) -> None:
        try:
            if self._backend.get_password(_SERVICE_NAME, key) is not None:
                self._backend.delete_password(_SERVICE_NAME, key)
        except KeyringError:
            raise CredentialStoreUnavailableError(
                "system credential storage delete failed"
            ) from None
