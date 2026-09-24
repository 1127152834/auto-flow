from __future__ import annotations

import io
import struct
import zipfile

import pytest

from autoflow.application.android.apk import parse_apk
from autoflow.domain.android.ports import AndroidError


def _string_pool(strings: list[str]) -> bytes:
    offsets: list[int] = []
    payload = bytearray()
    for value in strings:
        offsets.append(len(payload))
        raw = value.encode("utf-8")
        payload.extend((len(value.encode("utf-16-le")) // 2, len(raw)))
        payload.extend(raw)
        payload.append(0)
    header_size = 28
    size = header_size + 4 * len(strings) + len(payload)
    return (
        struct.pack("<HHIIIIII", 0x0001, header_size, size, len(strings), 0, 0x100, header_size + 4 * len(strings), 0)
        + b"".join(struct.pack("<I", offset) for offset in offsets)
        + payload
    )


def _start_element(name: int, attrs: list[tuple[int, int, int, int, int]]) -> bytes:
    # ns, name, raw-value, value-type, value-data
    header_size = 16
    body = struct.pack("<IIIIHHHHHH", 1, 0xFFFFFFFF, 0xFFFFFFFF, name, 20, 20, len(attrs), 0, 0, 0)
    for ns, attr_name, raw, value_type, value_data in attrs:
        body += struct.pack("<IIIHBBI", ns, attr_name, raw, 8, 0, value_type, value_data)
    return struct.pack("<HHI", 0x0102, header_size, 8 + len(body)) + body


def _end_element(name: int) -> bytes:
    header_size = 16
    body = struct.pack("<IIII", 1, 0xFFFFFFFF, 0xFFFFFFFF, name)
    return struct.pack("<HHI", 0x0103, header_size, 8 + len(body)) + body


def _manifest(*, package: str = "com.example.app", extra: list[tuple[str, str | None]] | None = None) -> bytes:
    names = ["manifest", "package", package, "versionCode", "versionName", "1.2.3", "feature", "uses-split", "split", "isFeatureSplit", "configForSplit"]
    index = {value: i for i, value in enumerate(names)}
    attrs = [
        (0xFFFFFFFF, index["package"], index[package], 0x03, index[package]),
        (0xFFFFFFFF, index["versionCode"], 0xFFFFFFFF, 0x10, 123),
        (0xFFFFFFFF, index["versionName"], index["1.2.3"], 0x03, index["1.2.3"]),
    ]
    for attr_name, value in extra or []:
        attrs.append((0xFFFFFFFF, index[attr_name], index[value] if value is not None else 0xFFFFFFFF, 0x03, index[value] if value is not None else 0))
    pool = _string_pool(names)
    body = _start_element(index["manifest"], attrs) + _end_element(index["manifest"])
    total = 8 + len(pool) + len(body)
    return struct.pack("<HHI", 0x0003, 8, total) + pool + body


def _apk(manifest: bytes, *, names: list[tuple[str, bytes]] | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", manifest)
        for name, content in names or []:
            archive.writestr(name, content)
    return output.getvalue()


def test_parse_apk_extracts_binary_manifest_identity() -> None:
    assert parse_apk(_apk(_manifest())) == {
        "packageName": "com.example.app",
        "versionCode": 123,
        "versionName": "1.2.3",
    }


def test_parse_apk_rejects_text_manifest() -> None:
    with pytest.raises(AndroidError, match="ANDROID_APK_UNSUPPORTED"):
        parse_apk(_apk(b"<?xml version='1.0'?><manifest package='com.example.app'/>") )


def test_parse_apk_rejects_nested_apk_and_split_manifest() -> None:
    with pytest.raises(AndroidError, match="ANDROID_APK_UNSUPPORTED"):
        parse_apk(_apk(_manifest(), names=[("feature.apk", b"nested")]))
    with pytest.raises(AndroidError, match="ANDROID_APK_UNSUPPORTED"):
        parse_apk(_apk(_manifest(extra=[("split", "feature")])) )


def test_parse_apk_rejects_duplicate_manifest_entries() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("AndroidManifest.xml", _manifest())
        archive.writestr("AndroidManifest.xml", _manifest())
    with pytest.raises(AndroidError, match="ANDROID_APK_INVALID"):
        parse_apk(output.getvalue())


def test_parse_apk_rejects_bad_zip_crc() -> None:
    manifest = _manifest()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("AndroidManifest.xml", manifest)
    corrupted = bytearray(output.getvalue())
    payload_offset = corrupted.find(manifest)
    assert payload_offset >= 0
    corrupted[payload_offset] ^= 0x01
    with pytest.raises(AndroidError, match="ANDROID_APK_INVALID"):
        parse_apk(bytes(corrupted))


def test_parse_apk_rejects_malformed_chunk() -> None:
    manifest = bytearray(_manifest())
    struct.pack_into("<I", manifest, 8 + 4, 0xFFFFFFF0)
    with pytest.raises(AndroidError, match="ANDROID_APK_INVALID"):
        parse_apk(_apk(bytes(manifest)))


def test_parse_apk_rejects_invalid_package_name() -> None:
    with pytest.raises(AndroidError, match="ANDROID_APK_INVALID"):
        parse_apk(_apk(_manifest(package="not a package")))
