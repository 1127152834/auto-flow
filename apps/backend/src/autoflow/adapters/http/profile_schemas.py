from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from autoflow.domain.profiles.models import (
    Profile,
    ProfileSpec,
    ProfileTestBrowserSession,
)

from .schemas import ApiModel


class Viewport(ApiModel):
    width: int = Field(ge=320, le=7680)
    height: int = Field(ge=240, le=4320)


class ProfileWrite(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    start_url: str = "about:blank"
    locale: str | None = None
    timezone: str | None = None
    geoip: bool = False
    headless: bool = False
    humanize: bool = False
    human_preset: Literal["default", "careful"] = "default"
    user_agent: str | None = None
    viewport_json: Viewport | None = None
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    extension_paths_json: list[str] = Field(default_factory=list)
    expert_args_json: list[str] = Field(default_factory=list)
    browser_version: str = Field(min_length=1)
    browser_edition: Literal["public", "licensed"] = "public"
    release_channel: Literal["stable", "preview"] = "stable"
    proxy_mode: Literal["none", "proxy", "pool"] = "none"
    proxy_id: str | None = None
    proxy_pool_id: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_proxy_reference(self) -> "ProfileWrite":
        if self.proxy_mode == "proxy" and not self.proxy_id:
            raise ValueError("proxyId is required for proxy mode")
        if self.proxy_mode == "pool" and not self.proxy_pool_id:
            raise ValueError("proxyPoolId is required for pool mode")
        return self

    def to_spec(self) -> ProfileSpec:
        return ProfileSpec.from_values(
            {
                "name": self.name,
                "description": self.description,
                "start_url": self.start_url,
                "locale": self.locale,
                "timezone": self.timezone,
                "geoip": self.geoip,
                "headless": self.headless,
                "humanize": self.humanize,
                "human_preset": self.human_preset,
                "user_agent": self.user_agent,
                "viewport": self.viewport_json.model_dump() if self.viewport_json else None,
                "color_scheme": self.color_scheme,
                "extension_paths": self.extension_paths_json,
                "expert_args": self.expert_args_json,
                "browser_version": self.browser_version,
                "browser_edition": self.browser_edition,
                "release_channel": self.release_channel,
                "proxy_mode": self.proxy_mode,
                "proxy_id": self.proxy_id,
                "proxy_pool_id": self.proxy_pool_id,
            }
        )


class ProfileDuplicate(ApiModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ProfileRead(ProfileWrite):
    id: UUID
    fingerprint_seed: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_profile(cls, profile: Profile) -> "ProfileRead":
        spec = profile.spec
        return cls(
            name=spec.name,
            description=spec.description,
            start_url=spec.start_url,
            locale=spec.locale,
            timezone=spec.timezone,
            geoip=spec.geoip,
            headless=spec.headless,
            humanize=spec.humanize,
            human_preset=spec.human_preset,  # type: ignore[arg-type]
            user_agent=spec.user_agent,
            viewport_json=Viewport(**spec.viewport) if spec.viewport else None,
            color_scheme=spec.color_scheme,  # type: ignore[arg-type]
            extension_paths_json=spec.extension_paths,
            expert_args_json=spec.expert_args,
            browser_version=spec.browser_version,
            browser_edition=spec.browser_edition,  # type: ignore[arg-type]
            release_channel=spec.release_channel,  # type: ignore[arg-type]
            proxy_mode=spec.proxy_mode,  # type: ignore[arg-type]
            proxy_id=spec.proxy_id,
            proxy_pool_id=spec.proxy_pool_id,
            id=UUID(profile.id),
            fingerprint_seed=profile.fingerprint_seed,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )


class ProfileList(ApiModel):
    items: list[ProfileRead]
    total: int


class ProfileTestBrowserRead(ApiModel):
    session_id: UUID
    profile_id: UUID
    fingerprint_seed: int
    warning: str | None = None

    @classmethod
    def from_session(
        cls, session: ProfileTestBrowserSession
    ) -> "ProfileTestBrowserRead":
        return cls(
            session_id=UUID(session.id),
            profile_id=UUID(session.profile_id),
            fingerprint_seed=session.fingerprint_seed,
            warning=session.warning,
        )


class EnvironmentOptionRead(ApiModel):
    value: str
    label: str


class ProfileEnvironmentOptionsRead(ApiModel):
    locales: list[EnvironmentOptionRead]
    timezones: list[EnvironmentOptionRead]
    user_agent_templates: list[EnvironmentOptionRead]
