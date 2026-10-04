"""One CloakBrowser process serving consecutive runs, each in a fresh isolated context (M3 R3-07).

``launch_context_async`` launches a browser and opens one context whose ``close()`` also ends
the browser. A pooled worker needs the two halves apart, so this mirrors that function for
cloakbrowser 0.5.9 (pinned in pyproject; ``test_pooled_browser`` fails on another version).
Fingerprint, timezone, locale and proxy are process-wide flags, so a browser is only reused
for an identical launch; anything else closes it and launches anew.
"""

from __future__ import annotations

import json
from typing import Any

from cloakbrowser import browser as cloak  # type: ignore[import-untyped]

SUPPORTED_CLOAKBROWSER = "0.5.9"
_LAUNCH_ONLY = ("proxy", "args", "stealth_args", "timezone", "locale", "geoip", "extension_paths",
                "license_key", "browser_version", "release_channel")
_HUMAN = ("humanize", "human_preset", "human_config")


class PooledBrowser:
    def __init__(self) -> None:
        self.browser: Any = None
        self._key: str | None = None
        self._context_options: dict[str, Any] = {}
        self._human: dict[str, Any] = {}
        # Set by the worker after each run: True only for a clean finish the parent may reuse.
        self.reusable = False

    async def new_context(self, launch: dict[str, Any]) -> Any:
        key = json.dumps(launch, sort_keys=True, default=str)
        if self.browser is not None and (key != self._key or not self.browser.is_connected()):
            await self.close()
        if self.browser is None:
            await self._launch(launch)
            self._key = key
        context = await self.browser.new_context(**self._context_options)
        denial_path = getattr(self.browser, "_cloak_denial_path", None)
        if denial_path:
            cloak._install_license_guard_async(context, denial_path)
        if self._human.get("humanize"):
            import cloakbrowser.human.config as human_config  # type: ignore[import-untyped]
            from cloakbrowser import human  # type: ignore[import-untyped]
            human.patch_context_async(context, human_config.resolve_config(self._human.get("human_preset", "default"), self._human.get("human_config")))
        return context

    async def release(self, context: Any) -> bool:
        """Close a run's context and its pages; True when the browser holds no other context."""
        await context.close()
        return self.browser is not None and self.browser.is_connected() and not self.browser.contexts

    async def close(self) -> None:
        browser, self.browser, self._key = self.browser, None, None
        if browser is not None:
            await browser.close()

    async def _launch(self, launch: dict[str, Any]) -> None:
        options = dict(launch)
        self._human = {key: options.pop(key) for key in _HUMAN if key in options}
        viewport = options.pop("viewport", cloak._VIEWPORT_UNSET)
        user_agent = options.pop("user_agent", None)
        color_scheme = options.pop("color_scheme", None)
        launch_only = {key: options.pop(key) for key in _LAUNCH_ONLY if key in options}
        headless = options.pop("headless", True)
        cloak._check_removed_kwargs(options)
        timezone = cloak._resolve_timezone(launch_only.get("timezone"), options)
        timezone, locale, exit_ip = cloak.maybe_resolve_geoip(
            launch_only.get("geoip", False), launch_only.get("proxy"), timezone, launch_only.get("locale"), launch_only.get("args"),
        )
        args = cloak._append_webrtc_exit_ip(launch_only.get("args"), exit_ip)
        self.browser = await cloak.launch_async(
            headless=headless, proxy=launch_only.get("proxy"), args=args,
            stealth_args=launch_only.get("stealth_args", True), timezone=timezone, locale=locale,
            extension_paths=launch_only.get("extension_paths"), license_key=launch_only.get("license_key"),
            browser_version=launch_only.get("browser_version"), release_channel=launch_only.get("release_channel"),
            _suppress_maximize=(viewport is not cloak._VIEWPORT_UNSET or "no_viewport" in options),
        )
        context_options: dict[str, Any] = {}
        if user_agent:
            context_options["user_agent"] = user_agent
        context_options.update(cloak._resolve_context_viewport(
            viewport, headless,
            cloak.binary_supports_headless_no_viewport(
                launch_only.get("license_key"), launch_only.get("browser_version"), launch_only.get("release_channel"),
            ),
        ))
        if color_scheme:
            context_options["color_scheme"] = color_scheme
        context_options.update(options)
        cloak._drop_conflicting_viewport(context_options, options)
        self._context_options = context_options
