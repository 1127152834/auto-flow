from typing import Protocol


class CredentialStoreUnavailableError(RuntimeError):
    """Raised when the operating-system credential store cannot be used."""


class CredentialStore(Protocol):
    def read(self, key: str) -> bytes | None: ...
    def write(self, key: str, value: bytes) -> None: ...
    def delete(self, key: str) -> None: ...
