from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ProfileValidationError

_FORBIDDEN = ("--user-data-dir", "--fingerprint", "--remote-debugging-address", "--remote-debugging-port", "--proxy-server", "--load-extension")
_GRANDFATHERED = {
    "art-lojban", "cel-gaulish", "en-gb-oed", "i-ami", "i-bnn", "i-default", "i-enochian", "i-hak",
    "i-klingon", "i-lux", "i-mingo", "i-navajo", "i-pwn", "i-tao", "i-tay", "i-tsu", "no-bok",
    "no-nyn", "sgn-be-fr", "sgn-be-nl", "sgn-ch-de", "zh-guoyu", "zh-hakka", "zh-min", "zh-min-nan",
    "zh-xiang",
}


@dataclass(frozen=True)
class ProfileSpec:
    name: str
    description: str
    start_url: str
    locale: str | None
    timezone: str | None
    geoip: bool
    headless: bool
    humanize: bool
    human_preset: str
    user_agent: str | None
    viewport: dict[str, int] | None
    color_scheme: str | None
    extension_paths: list[str]
    expert_args: list[str]
    browser_version: str
    browser_edition: str
    release_channel: str
    proxy_mode: str
    proxy_id: str | None
    proxy_pool_id: str | None

    @classmethod
    def from_values(cls, values: dict[str, Any]) -> "ProfileSpec":
        data = dict(values)
        name = _string(data.get("name", ""), "name").strip()
        if not 1 <= len(name) <= 120:
            raise ProfileValidationError("name must contain 1-120 characters")
        start_url = _string(data.get("start_url", "about:blank"), "start_url").strip()
        try:
            parsed = urlparse(start_url)
            _ = parsed.hostname, parsed.port
        except ValueError:
            raise ProfileValidationError("start_url must use http, https, or about:blank") from None
        if start_url != "about:blank" and (parsed.scheme not in {"http", "https"} or parsed.hostname is None):
            raise ProfileValidationError("start_url must use http, https, or about:blank")
        locale = data.get("locale")
        if locale is not None and (not isinstance(locale, str) or not _is_bcp47(locale)):
            raise ProfileValidationError("locale is invalid")
        timezone = data.get("timezone")
        if timezone is not None:
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, TypeError, ValueError, OSError):
                raise ProfileValidationError("timezone is invalid") from None
        viewport = data.get("viewport")
        if viewport is not None:
            if not isinstance(viewport, dict):
                raise ProfileValidationError("viewport is invalid")
            try:
                width, height = viewport["width"], viewport["height"]
                if type(width) is not int or type(height) is not int:
                    raise ProfileValidationError("viewport is invalid")
            except KeyError:
                raise ProfileValidationError("viewport is invalid") from None
            if not 320 <= width <= 7680 or not 240 <= height <= 4320:
                raise ProfileValidationError("viewport is invalid")
            viewport = {"width": width, "height": height}
        edition = _enum(data.get("browser_edition", "public"), "browser_edition", {"public", "licensed"})
        channel = _enum(data.get("release_channel", "stable"), "release_channel", {"stable", "preview"})
        if edition == "public" and channel != "stable":
            raise ProfileValidationError("Public edition only supports Stable release channel")
        human_preset = _enum(data.get("human_preset", "default"), "human_preset", {"default", "careful"})
        color_scheme = data.get("color_scheme")
        if color_scheme is not None:
            color_scheme = _enum(color_scheme, "color_scheme", {"light", "dark", "no-preference"})
        browser_version = _string(data.get("browser_version", ""), "browser_version").strip()
        if not browser_version:
            raise ProfileValidationError("browser_version must not be empty")
        mode = _enum(data.get("proxy_mode", "none"), "proxy_mode", {"none", "proxy", "pool"})
        proxy_id = _optional_string(data.get("proxy_id"), "proxy_id") if mode == "proxy" else None
        pool_id = _optional_string(data.get("proxy_pool_id"), "proxy_pool_id") if mode == "pool" else None
        args = [arg.strip() for arg in _string_list(data.get("expert_args", []), "expert_args") if arg.strip()]
        for arg in args:
            normalized = arg.split(maxsplit=1)[0].split("=", 1)[0]
            if normalized in _FORBIDDEN:
                raise ProfileValidationError(f"expert argument {normalized} is forbidden")
        return cls(name, _string(data.get("description", ""), "description"), start_url, locale, timezone,
                   _boolean(data.get("geoip", False), "geoip"), _boolean(data.get("headless", False), "headless"),
                   _boolean(data.get("humanize", False), "humanize"), human_preset,
                   _optional_string(data.get("user_agent"), "user_agent"), viewport, color_scheme,
                   _string_list(data.get("extension_paths", []), "extension_paths"), args, browser_version,
                   edition, channel, mode, proxy_id, pool_id)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ProfileValidationError(f"{field} must be a string")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    return None if value is None else _string(value, field)


def _enum(value: Any, field: str, choices: set[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ProfileValidationError(f"{field} is invalid")
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileValidationError(f"{field} must be a boolean")
    return value


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProfileValidationError(f"{field} must be a list of strings")
    return value


def _is_bcp47(tag: str) -> bool:
    lowered = tag.lower()
    if lowered in _GRANDFATHERED:
        return True
    parts = tag.split("-")
    if not parts or any(not part or len(part) > 8 or not part.isascii() or not part.isalnum() for part in parts):
        return False
    if parts[0].lower() == "x":
        return len(parts) > 1

    language = parts[0]
    if not language.isalpha() or not (2 <= len(language) <= 8):
        return False
    index = 1
    if len(language) <= 3:
        for _ in range(3):
            if index < len(parts) and len(parts[index]) == 3 and parts[index].isalpha():
                index += 1
            else:
                break
    if index < len(parts) and len(parts[index]) == 4 and parts[index].isalpha():
        index += 1
    if index < len(parts) and ((len(parts[index]) == 2 and parts[index].isalpha()) or (len(parts[index]) == 3 and parts[index].isdigit())):
        index += 1

    variants: set[str] = set()
    while index < len(parts) and ((5 <= len(parts[index]) <= 8) or (len(parts[index]) == 4 and parts[index][0].isdigit())):
        variant = parts[index].lower()
        if variant in variants:
            return False
        variants.add(variant)
        index += 1

    extensions: set[str] = set()
    while index < len(parts) and len(parts[index]) == 1 and parts[index].lower() != "x":
        singleton = parts[index].lower()
        if singleton in extensions:
            return False
        extensions.add(singleton)
        index += 1
        start = index
        while index < len(parts) and 2 <= len(parts[index]) <= 8:
            index += 1
        if index == start:
            return False

    if index < len(parts) and parts[index].lower() == "x":
        index += 1
        if index == len(parts):
            return False
        index = len(parts)
    return index == len(parts)


@dataclass(frozen=True)
class Profile:
    id: str
    spec: ProfileSpec
    fingerprint_seed: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ProfileTestBrowserSession:
    id: str
    profile_id: str
    fingerprint_seed: int
    warning: str | None = None


@dataclass(frozen=True)
class ProfileBrowserProxy:
    server: str
    username: str = field(repr=False)
    password: str = field(repr=False)
