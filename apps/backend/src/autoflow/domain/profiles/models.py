from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ProfileValidationError

_FORBIDDEN = ("--user-data-dir", "--fingerprint", "--remote-debugging-address", "--remote-debugging-port", "--proxy-server", "--load-extension")


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
        name = str(data.get("name", "")).strip()
        if not 1 <= len(name) <= 120:
            raise ProfileValidationError("name must contain 1-120 characters")
        start_url = str(data.get("start_url", "about:blank")).strip()
        parsed = urlparse(start_url)
        if start_url != "about:blank" and parsed.scheme not in {"http", "https"}:
            raise ProfileValidationError("start_url must use http, https, or about:blank")
        locale = data.get("locale")
        if locale is not None and (not isinstance(locale, str) or not locale.replace("-", "").isalnum()):
            raise ProfileValidationError("locale is invalid")
        timezone = data.get("timezone")
        if timezone is not None:
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, TypeError):
                raise ProfileValidationError("timezone is invalid") from None
        viewport = data.get("viewport")
        if viewport is not None:
            if not isinstance(viewport, dict) or not (320 <= int(viewport.get("width", 0)) <= 7680) or not (240 <= int(viewport.get("height", 0)) <= 4320):
                raise ProfileValidationError("viewport is invalid")
            viewport = {"width": int(viewport["width"]), "height": int(viewport["height"])}
        edition = data.get("browser_edition", "public")
        channel = data.get("release_channel", "stable")
        if edition == "public" and channel != "stable":
            raise ProfileValidationError("Public edition only supports Stable release channel")
        mode = data.get("proxy_mode", "none")
        if mode not in {"none", "proxy", "pool"}:
            raise ProfileValidationError("proxy_mode is invalid")
        proxy_id = data.get("proxy_id") if mode == "proxy" else None
        pool_id = data.get("proxy_pool_id") if mode == "pool" else None
        args = [str(arg).strip() for arg in data.get("expert_args", []) if str(arg).strip()]
        for arg in args:
            normalized = arg.split("=", 1)[0].strip()
            if normalized in _FORBIDDEN:
                raise ProfileValidationError(f"expert argument {normalized} is forbidden")
        return cls(name, str(data.get("description", "")), start_url, locale, timezone,
                   bool(data.get("geoip", False)), bool(data.get("headless", False)), bool(data.get("humanize", False)),
                   data.get("human_preset", "default"), data.get("user_agent"), viewport, data.get("color_scheme"),
                   [str(path) for path in data.get("extension_paths", [])], args, str(data.get("browser_version", "")),
                   edition, channel, mode, proxy_id, pool_id)


@dataclass(frozen=True)
class Profile:
    id: str
    spec: ProfileSpec
    fingerprint_seed: int
    created_at: datetime
    updated_at: datetime
