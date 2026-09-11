import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ProfileValidationError

_FORBIDDEN = ("--user-data-dir", "--fingerprint", "--remote-debugging-address", "--remote-debugging-port", "--proxy-server", "--load-extension")
_LOCALE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


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
        parsed = urlparse(start_url)
        if start_url != "about:blank" and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
            raise ProfileValidationError("start_url must use http, https, or about:blank")
        locale = data.get("locale")
        if locale is not None and (not isinstance(locale, str) or _LOCALE.fullmatch(locale) is None):
            raise ProfileValidationError("locale is invalid")
        timezone = data.get("timezone")
        if timezone is not None:
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, TypeError):
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


@dataclass(frozen=True)
class Profile:
    id: str
    spec: ProfileSpec
    fingerprint_seed: int
    created_at: datetime
    updated_at: datetime
