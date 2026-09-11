from autoflow.domain.credentials import CredentialStoreUnavailableError


class UnavailableCredentialStore:
    def read(self, key: str) -> bytes | None:
        raise CredentialStoreUnavailableError("credential store unavailable")

    def write(self, key: str, value: bytes) -> None:
        raise CredentialStoreUnavailableError("credential store unavailable")

    def delete(self, key: str) -> None:
        raise CredentialStoreUnavailableError("credential store unavailable")
