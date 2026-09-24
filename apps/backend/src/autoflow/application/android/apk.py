from __future__ import annotations

import io
import re
import struct
import zipfile
import zlib
from collections.abc import Sequence

from autoflow.domain.android.ports import AndroidError

MAX_APK_BYTES = 256 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$")


def parse_apk(data: bytes) -> dict[str, str | int | None]:
    if len(data) > MAX_APK_BYTES:
        _raise("ANDROID_APK_TOO_LARGE", "APK exceeds the 256 MiB limit", 413)
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        _raise("ANDROID_APK_INVALID", f"invalid ZIP archive: {exc}")

    with archive:
        try:
            entries = archive.infolist()
        except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
            _raise("ANDROID_APK_INVALID", f"invalid ZIP directory: {exc}")
        manifests = [entry for entry in entries if entry.filename == "AndroidManifest.xml"]
        if len(manifests) != 1:
            _raise("ANDROID_APK_INVALID", "APK must contain exactly one AndroidManifest.xml")
        total_uncompressed = 0
        for entry in entries:
            if entry.filename.lower().endswith(".apk"):
                _raise("ANDROID_APK_UNSUPPORTED", "nested APK entries are not supported", 422)
            if entry.file_size < 0:
                _raise("ANDROID_APK_INVALID", "negative ZIP entry size")
            total_uncompressed += entry.file_size
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                _raise("ANDROID_APK_TOO_LARGE", "uncompressed APK contents exceed the 256 MiB limit", 413)
        manifest_entry = manifests[0]
        if manifest_entry.file_size > MAX_MANIFEST_BYTES:
            _raise("ANDROID_APK_TOO_LARGE", "AndroidManifest.xml exceeds the 4 MiB limit", 413)
        try:
            bad_entry = archive.testzip()
            if bad_entry is not None:
                _raise("ANDROID_APK_INVALID", f"ZIP CRC check failed for {bad_entry}")
            manifest = archive.read(manifest_entry)
        except AndroidError:
            raise
        except (OSError, KeyError, RuntimeError, ValueError, zipfile.BadZipFile, EOFError, NotImplementedError, zlib.error) as exc:
            _raise("ANDROID_APK_INVALID", f"unable to read APK entries: {exc}")
    if len(manifest) > MAX_MANIFEST_BYTES:
        _raise("ANDROID_APK_TOO_LARGE", "AndroidManifest.xml exceeds the 4 MiB limit", 413)
    return _parse_binary_manifest(manifest)


def _parse_binary_manifest(data: bytes) -> dict[str, str | int | None]:
    if len(data) < 8:
        _raise("ANDROID_APK_INVALID", "manifest is truncated")
    chunk_type, header_size, total_size = struct.unpack_from("<HHI", data)
    if chunk_type != 0x0003 or header_size != 8 or total_size != len(data):
        if data.startswith(b"<"):
            _raise("ANDROID_APK_UNSUPPORTED", "text AndroidManifest.xml is not accepted", 422)
        _raise("ANDROID_APK_INVALID", "manifest is not a complete binary XML document")

    pool = _chunk(data, 8, len(data))
    if pool[0] != 0x0001:
        _raise("ANDROID_APK_INVALID", "binary XML must start with a string pool")
    strings = _parse_string_pool(data, 8, *pool)
    offset = 8 + pool[2]
    stack: list[str] = []
    root_count = 0
    result: dict[str, str | int | None] = {"packageName": "", "versionCode": -1, "versionName": None}
    while offset < len(data):
        chunk_type, chunk_header, chunk_size = _chunk(data, offset, len(data))
        if chunk_type == 0x0102:
            if chunk_header < 16:
                _raise("ANDROID_APK_INVALID", "start element header is truncated")
            if chunk_size < chunk_header:
                _raise("ANDROID_APK_INVALID", "start element size is invalid")
            fields = struct.unpack_from("<IIIIHHHHHH", data, offset + 8)
            _, _, namespace_index, name_index, attribute_start, attribute_size, attribute_count, _, _, _ = fields
            _string_ref(strings, namespace_index)
            name = _string(strings, name_index)
            # attributeStart is relative to ResXMLTree_attrExt (chunk offset + 16),
            # as defined by AOSP ResourceTypes.h.
            attributes_start = 16 + attribute_start
            if attribute_size < 20 or attributes_start < chunk_header:
                _raise("ANDROID_APK_INVALID", "attribute layout is invalid")
            attrs_end = attributes_start + attribute_count * attribute_size
            if attrs_end > chunk_size:
                _raise("ANDROID_APK_INVALID", "attributes exceed the element chunk")
            if name == "uses-split" or name == "split":
                _raise("ANDROID_APK_UNSUPPORTED", "split APK manifests are not supported", 422)
            if name == "manifest":
                root_count += 1
                if root_count != 1 or stack:
                    _raise("ANDROID_APK_INVALID", "manifest must have exactly one root element")
                for index in range(attribute_count):
                    attr_offset = offset + attributes_start + index * attribute_size
                    attr_namespace_index, attr_name_index, raw_value, typed_size, _, value_type, value_data = struct.unpack_from(
                        "<IIIHBBI", data, attr_offset
                    )
                    _string_ref(strings, attr_namespace_index)
                    if typed_size != 8:
                        _raise("ANDROID_APK_INVALID", "attribute typed value size is invalid")
                    attr_name = _string(strings, attr_name_index)
                    if attr_name in {"split", "isFeatureSplit", "configForSplit"}:
                        _raise("ANDROID_APK_UNSUPPORTED", "split APK manifests are not supported", 422)
                    value = _attribute_value(strings, raw_value, value_type, value_data)
                    if attr_name == "package":
                        result["packageName"] = value
                    elif attr_name == "versionCode":
                        result["versionCode"] = _version_code(value, value_type, value_data)
                    elif attr_name == "versionName":
                        result["versionName"] = value
            stack.append(name)
        elif chunk_type == 0x0103:
            if chunk_header < 16 or chunk_size < 24:
                _raise("ANDROID_APK_INVALID", "end element header is truncated")
            _string_ref(strings, struct.unpack_from("<I", data, offset + 16)[0])
            name = _string(strings, struct.unpack_from("<I", data, offset + 20)[0])
            if not stack or stack[-1] != name:
                _raise("ANDROID_APK_INVALID", "element nesting is invalid")
            stack.pop()
        elif chunk_type == 0x0100 or chunk_type == 0x0101:
            if chunk_header < 16 or chunk_size < 24:
                _raise("ANDROID_APK_INVALID", "namespace chunk is truncated")
            _string_ref(strings, struct.unpack_from("<I", data, offset + 16)[0])
            _string_ref(strings, struct.unpack_from("<I", data, offset + 20)[0])
        elif chunk_type == 0x0104:
            if chunk_header < 16 or chunk_size < 28:
                _raise("ANDROID_APK_INVALID", "CDATA chunk is truncated")
            _string_ref(strings, struct.unpack_from("<I", data, offset + 16)[0])
        offset += chunk_size
    if offset != len(data) or stack or root_count != 1:
        _raise("ANDROID_APK_INVALID", "manifest XML structure is incomplete")
    package_name = result["packageName"]
    if not isinstance(package_name, str) or (package_name != "android" and not _PACKAGE_RE.fullmatch(package_name)):
        _raise("ANDROID_APK_INVALID", "manifest package name is invalid")
    if not isinstance(result["versionCode"], int) or result["versionCode"] < 0:
        _raise("ANDROID_APK_INVALID", "manifest versionCode is missing or invalid")
    if result["versionName"] is not None and not isinstance(result["versionName"], str):
        _raise("ANDROID_APK_INVALID", "manifest versionName is invalid")
    return result


def _chunk(data: bytes, offset: int, limit: int) -> tuple[int, int, int]:
    if offset < 0 or offset + 8 > limit:
        _raise("ANDROID_APK_INVALID", "binary XML chunk header is truncated")
    chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, offset)
    if header_size < 8 or chunk_size < header_size or chunk_size % 4 or offset + chunk_size > limit:
        _raise("ANDROID_APK_INVALID", "binary XML chunk bounds are invalid")
    return chunk_type, header_size, chunk_size


def _parse_string_pool(data: bytes, base: int, chunk_type: int, header_size: int, chunk_size: int) -> list[str]:
    if header_size < 28 or chunk_size < header_size:
        _raise("ANDROID_APK_INVALID", "string pool header is invalid")
    string_count, style_count, flags, strings_start, styles_start = struct.unpack_from("<IIIII", data, base + 8)
    offsets_end = 28 + string_count * 4
    if offsets_end > chunk_size or strings_start < offsets_end or strings_start > chunk_size:
        _raise("ANDROID_APK_INVALID", "string pool offsets are invalid")
    if style_count and (styles_start < strings_start or styles_start > chunk_size):
        _raise("ANDROID_APK_INVALID", "string pool styles are invalid")
    utf8 = bool(flags & 0x100)
    strings_end = styles_start if styles_start > strings_start else chunk_size
    values: list[str] = []
    for index in range(string_count):
        relative = struct.unpack_from("<I", data, base + 28 + index * 4)[0]
        start = strings_start + relative
        if start >= strings_end:
            _raise("ANDROID_APK_INVALID", "string pool entry is out of bounds")
        values.append(_decode_string(data, base + start, base + strings_end, utf8))
    return values


def _decode_string(data: bytes, start: int, limit: int, utf8: bool) -> str:
    if utf8:
        utf16_length, cursor = _length8(data, start, limit)
        byte_length, cursor = _length8(data, cursor, limit)
        end = cursor + byte_length
        if end >= limit or data[end] != 0:
            _raise("ANDROID_APK_INVALID", "unterminated UTF-8 string pool entry")
        try:
            value = data[cursor:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            _raise("ANDROID_APK_INVALID", f"invalid UTF-8 string pool entry: {exc}")
        if len(value.encode("utf-16-le")) // 2 != utf16_length:
            _raise("ANDROID_APK_INVALID", "UTF-8 string length is inconsistent")
        return value
    utf16_length, cursor = _length16(data, start, limit)
    end = cursor + utf16_length * 2
    if end + 2 > limit or data[end:end + 2] != b"\x00\x00":
        _raise("ANDROID_APK_INVALID", "unterminated UTF-16 string pool entry")
    try:
        return data[cursor:end].decode("utf-16le")
    except UnicodeDecodeError as exc:
        _raise("ANDROID_APK_INVALID", f"invalid UTF-16 string pool entry: {exc}")


def _length8(data: bytes, offset: int, limit: int) -> tuple[int, int]:
    if offset >= limit:
        _raise("ANDROID_APK_INVALID", "truncated UTF-8 string length")
    first = data[offset]
    if first & 0x80:
        if offset + 1 >= limit:
            _raise("ANDROID_APK_INVALID", "truncated UTF-8 string length")
        return ((first & 0x7F) << 8) | data[offset + 1], offset + 2
    return first, offset + 1


def _length16(data: bytes, offset: int, limit: int) -> tuple[int, int]:
    if offset + 2 > limit:
        _raise("ANDROID_APK_INVALID", "truncated UTF-16 string length")
    first = struct.unpack_from("<H", data, offset)[0]
    if first & 0x8000:
        if offset + 4 > limit:
            _raise("ANDROID_APK_INVALID", "truncated UTF-16 string length")
        second = struct.unpack_from("<H", data, offset + 2)[0]
        return ((first & 0x7FFF) << 16) | second, offset + 4
    return first, offset + 2


def _string(strings: Sequence[str], index: int) -> str:
    if index < 0 or index >= len(strings):
        _raise("ANDROID_APK_INVALID", "string pool index is invalid")
    return strings[index]


def _string_ref(strings: Sequence[str], index: int) -> str | None:
    return None if index == 0xFFFFFFFF else _string(strings, index)


def _attribute_value(strings: Sequence[str], raw_value: int, value_type: int, value_data: int) -> str | int | None:
    if value_type == 0x03:
        return _string(strings, value_data if raw_value == 0xFFFFFFFF else raw_value)
    if raw_value != 0xFFFFFFFF:
        return _string(strings, raw_value)
    if value_type in (0x10, 0x11):
        return value_data
    if value_type == 0x12:
        return value_data != 0
    return None


def _version_code(value: str | int | None, value_type: int, value_data: int) -> int:
    if value_type in (0x10, 0x11):
        return value_data
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    _raise("ANDROID_APK_INVALID", "manifest versionCode is not an integer")


def _raise(code: str, message: str, status: int = 422) -> None:
    raise AndroidError(code, f"{code}: {message}", status)
