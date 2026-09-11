"""Ports for platform-backed secret storage.

Domain and provider code depend on this small protocol instead of a concrete
Windows or macOS implementation. Implementations must never return secrets to
the renderer layer.
"""

from typing import Protocol


class CredentialStore(Protocol):
    """Read/write opaque secret bytes in the host OS credential store."""

    def read(self, key: str) -> bytes | None:
        """Return the secret for *key*, or ``None`` when it does not exist."""

    def write(self, key: str, value: bytes) -> None:
        """Persist *value* under *key* without exposing it to application data."""

    def delete(self, key: str) -> None:
        """Delete *key*; implementations should make this operation idempotent."""
