from collections.abc import Mapping
from typing import Any


class ModelError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = dict(details or {})
