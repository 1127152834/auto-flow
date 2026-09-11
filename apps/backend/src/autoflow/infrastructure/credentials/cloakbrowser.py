from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.kernels.errors import KernelCredentialStoreUnavailable

_LICENSE_KEY = "cloakbrowser-license"


class CloakBrowserLicenseStore:
    """Bind the shared credential store to CloakBrowser's single UTF-8 secret."""

    def __init__(self, store: CredentialStore) -> None:
        self._store = store

    def read(self) -> str | None:
        try:
            value = self._store.read(_LICENSE_KEY)
            return value.decode("utf-8") if value is not None else None
        except (CredentialStoreUnavailableError, UnicodeDecodeError):
            raise KernelCredentialStoreUnavailable() from None

    def write(self, value: str) -> None:
        try:
            self._store.write(_LICENSE_KEY, value.encode("utf-8"))
        except CredentialStoreUnavailableError:
            raise KernelCredentialStoreUnavailable() from None

    def delete(self) -> None:
        try:
            self._store.delete(_LICENSE_KEY)
        except CredentialStoreUnavailableError:
            raise KernelCredentialStoreUnavailable() from None
