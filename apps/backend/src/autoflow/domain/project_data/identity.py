from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from autoflow.domain.projects.models import ProjectError

RecordKeyType = Literal["text", "integer", "uuid"]
MAX_SAFE_INTEGER = (2**53) - 1
MAX_TEXT_CODE_POINTS = 8_000


@dataclass(frozen=True)
class RecordKey:
    type: RecordKeyType
    value: str


def _invalid(reason: str) -> ProjectError:
    return ProjectError(
        "INVALID_PROJECT_DATA",
        "Invalid record key",
        422,
        {"field": "recordKey", "reason": reason},
    )


def _has_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def record_key(value: object) -> RecordKey:
    if isinstance(value, str):
        if not value:
            raise _invalid("text keys must not be empty")
        if len(value) > MAX_TEXT_CODE_POINTS:
            raise _invalid("text keys must contain at most 8000 Unicode code points")
        if _has_surrogate(value):
            raise _invalid("text keys must contain valid Unicode scalar values")
        return RecordKey("text", value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid("keys must be text or an integer")
    if abs(value) > MAX_SAFE_INTEGER:
        raise _invalid("integer keys must be JSON-safe integers")
    return RecordKey("integer", str(value))


def system_record_key() -> RecordKey:
    return RecordKey("uuid", str(uuid4()))


def encode_record_key(key: RecordKey) -> str:
    canonical = _canonical_key(key.value, key.type)
    encoded = base64.urlsafe_b64encode(canonical.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def decode_record_key(encoded: str, key_type: str) -> RecordKey:
    if key_type not in {"text", "integer", "uuid"}:
        raise _invalid("key type must be text, integer, or uuid")
    if not isinstance(encoded, str) or not encoded or "=" in encoded:
        raise _invalid("encoded key is not canonical base64url")
    try:
        raw = base64.b64decode(
            encoded + ("=" * (-len(encoded) % 4)), altchars=b"-_", validate=True
        )
        value = raw.decode("utf-8", errors="strict")
    except (binascii.Error, UnicodeDecodeError, ValueError) as error:
        raise _invalid("encoded key is not canonical UTF-8 base64url") from error

    typed_key = RecordKey(key_type, _canonical_key(value, key_type))  # type: ignore[arg-type]
    if encode_record_key(typed_key) != encoded:
        raise _invalid("encoded key is not canonical base64url")
    return typed_key


def _canonical_key(value: str, key_type: RecordKeyType) -> str:
    if key_type == "text":
        return record_key(value).value
    if key_type == "integer":
        if value == "0":
            return value
        if not value or value.startswith(("+", "-0", "0")):
            raise _invalid("integer keys must use canonical decimal notation")
        digits = value.removeprefix("-")
        if not digits.isascii() or not digits.isdigit():
            raise _invalid("integer keys must use canonical decimal notation")
        if len(digits) > len(str(MAX_SAFE_INTEGER)):
            raise _invalid("integer keys must be JSON-safe integers")
        parsed = int(value)
        if abs(parsed) > MAX_SAFE_INTEGER:
            raise _invalid("integer keys must be JSON-safe integers")
        return value
    try:
        parsed_uuid = UUID(value)
    except (ValueError, AttributeError) as error:
        raise _invalid("uuid keys must use standard lowercase UUID notation") from error
    canonical = str(parsed_uuid)
    if value != canonical:
        raise _invalid("uuid keys must use standard lowercase UUID notation")
    return canonical
