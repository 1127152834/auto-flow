"""Launch a CloakBrowser work copy from an instance directory.

Login files live only under user_data_dir. Cookies, tokens and passwords are
never logged. Expert args must not include --user-data-dir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autoflow.providers.browser.worker import browser_launch_options


def persistent_launch_kwargs(
    user_data_dir: Path, command: dict[str, Any], *, headless: bool
) -> dict[str, Any]:
    directory = Path(user_data_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    launch = {
        "geoip": False,
        "humanize": False,
        "extensionPaths": [],
        "expertArgs": [],
        **command,
    }
    options = browser_launch_options(launch, headless=headless)
    options["user_data_dir"] = str(directory)
    return options


async def launch_persistent_instance(
    user_data_dir: Path, command: dict[str, Any], *, headless: bool
):
    from cloakbrowser import (  # type: ignore[import-untyped]
        launch_persistent_context_async,
    )

    return await launch_persistent_context_async(
        **persistent_launch_kwargs(user_data_dir, command, headless=headless)
    )
